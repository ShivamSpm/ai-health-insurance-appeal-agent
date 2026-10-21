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
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, path: Path | None = None):
        path = path or REPO_ROOT / settings()["storage"]["db_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
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
