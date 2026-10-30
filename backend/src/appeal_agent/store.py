"""SQLite storage for agent runs and their steps (LLM calls and tool calls)."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from appeal_agent.config import REPO_ROOT, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,          -- running | completed | failed | step_limit | error
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    llm_calls INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    prompt_hash TEXT,
    skill_hashes TEXT,             -- JSON {skill name: hash}
    git_sha TEXT,
    settings TEXT,                 -- JSON of the agent settings used
    loaded_skills TEXT,            -- JSON list, in load order
    retrieved TEXT,                -- JSON list of retrieved chunk IDs
    findings TEXT,                 -- JSON, or NULL
    letter TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL REFERENCES runs(id),
    idx INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- llm | tool
    name TEXT,                     -- tool name, or model for llm steps
    input TEXT,                    -- tool arguments (JSON)
    output TEXT,                   -- tool result, or JSON of the model's message
    reasoning TEXT,                -- model reasoning text, if the provider returns it
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cached_tokens INTEGER,
    cost_usd REAL,
    latency_ms INTEGER,
    invalid INTEGER DEFAULT 0,
    started_at TEXT NOT NULL,
    PRIMARY KEY (run_id, idx)
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TEXT NOT NULL,
    model TEXT NOT NULL,
    repeats INTEGER NOT NULL,
    case_ids TEXT NOT NULL,        -- JSON list
    prompt_hash TEXT,
    skill_hashes TEXT,             -- JSON {skill name: hash}
    git_sha TEXT,
    settings TEXT,                 -- JSON of the agent settings used
    labels_hash TEXT,              -- hash of the labels used at the last scoring
    scored_at TEXT,
    summary TEXT                   -- JSON aggregates from the last scoring
);
CREATE TABLE IF NOT EXISTS eval_items (
    eval_id TEXT NOT NULL REFERENCES eval_runs(id),
    case_id TEXT NOT NULL,
    pass INTEGER NOT NULL,         -- 1-based repeat number
    run_id TEXT NOT NULL,
    PRIMARY KEY (eval_id, case_id, pass)
);
CREATE TABLE IF NOT EXISTS eval_results (
    eval_id TEXT NOT NULL REFERENCES eval_runs(id),
    case_id TEXT NOT NULL,
    pass INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,                    -- NULL when the metric doesn't apply to the case
    expected TEXT,                 -- JSON
    actual TEXT,                   -- JSON
    PRIMARY KEY (eval_id, case_id, pass, metric)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, path: Path | None = None):
        path = path or REPO_ROOT / settings()["storage"]["db_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # One connection per thread; WAL and a busy timeout let parallel eval runs write.
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def start_run(self, run_id: str, case_id: str, model: str, **meta) -> None:
        self.db.execute(
            "INSERT INTO runs (id, case_id, model, status, started_at, prompt_hash, "
            "skill_hashes, git_sha, settings) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)",
            (
                run_id,
                case_id,
                model,
                _now(),
                meta["prompt_hash"],
                json.dumps(meta["skill_hashes"]),
                meta["git_sha"],
                json.dumps(meta["settings"]),
            ),
        )
        self.db.commit()

    def add_step(self, run_id: str, idx: int, kind: str, **fields) -> None:
        row = {"run_id": run_id, "idx": idx, "kind": kind, "started_at": _now(), **fields}
        self.db.execute(
            f"INSERT INTO steps ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )
        self.db.commit()

    def finish_run(self, run_id: str, **fields) -> None:
        fields["finished_at"] = _now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(f"UPDATE runs SET {sets} WHERE id = ?", [*fields.values(), run_id])
        self.db.commit()

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()

    def get_steps(self, run_id: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY idx", (run_id,)
        ).fetchall()

    def list_runs(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def citation_rejections(self, run_id: str) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND kind = 'tool' AND invalid = 1 "
            "AND output LIKE '%you have not retrieved%'",
            (run_id,),
        ).fetchone()[0]

    # ---------------- Evals ----------------

    def create_eval(self, eval_id: str, **fields) -> None:
        row = {"id": eval_id, "created_at": _now(), **fields}
        self.db.execute(
            f"INSERT INTO eval_runs ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )
        self.db.commit()

    def add_eval_item(self, eval_id: str, case_id: str, pass_no: int, run_id: str) -> None:
        self.db.execute(
            "INSERT INTO eval_items (eval_id, case_id, pass, run_id) VALUES (?, ?, ?, ?)",
            (eval_id, case_id, pass_no, run_id),
        )
        self.db.commit()

    def get_eval(self, eval_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM eval_runs WHERE id = ?", (eval_id,)).fetchone()

    def list_evals(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def eval_items(self, eval_id: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM eval_items WHERE eval_id = ? ORDER BY pass, case_id", (eval_id,)
        ).fetchall()

    def save_eval_results(self, eval_id: str, rows: list[tuple], **summary_fields) -> None:
        """Replace an eval's scores (rows of case_id, pass, run_id, metric, value, exp, act)."""
        with self.db:
            self.db.execute("DELETE FROM eval_results WHERE eval_id = ?", (eval_id,))
            self.db.executemany(
                "INSERT INTO eval_results (eval_id, case_id, pass, run_id, metric, value, "
                "expected, actual) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(eval_id, *r) for r in rows],
            )
            sets = ", ".join(f"{k} = ?" for k in summary_fields)
            self.db.execute(
                f"UPDATE eval_runs SET {sets}, scored_at = ? WHERE id = ?",
                [*summary_fields.values(), _now(), eval_id],
            )

    def eval_results(self, eval_id: str, metric: str | None = None) -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM eval_results WHERE eval_id = ?", [eval_id]
        if metric:
            sql, args = sql + " AND metric = ?", [*args, metric]
        return self.db.execute(sql + " ORDER BY case_id, pass", args).fetchall()
