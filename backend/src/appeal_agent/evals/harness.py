"""Eval harness: run cases (repeated, in parallel), then score the stored runs.

Running and scoring are separate. `run_eval` stores agent runs and links them
to the eval; `score_eval` reads those runs plus the current labels, so it can
be re-run for free after a label or metric change.
"""

import hashlib
import json
import re
import statistics
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from appeal_agent.agent.loop import (
    Complete,
    git_sha,
    new_run_id,
    openai_complete,
    prompt_hash,
    run_case,
)
from appeal_agent.agent.outputs import Findings
from appeal_agent.agent.skills import load_skills
from appeal_agent.config import DATA_DIR, model, settings
from appeal_agent.dataset.schema import CaseLabels
from appeal_agent.evals.metrics import METRICS, RunView, score_case
from appeal_agent.store import Store


def all_case_ids() -> list[str]:
    return sorted(p.name for p in (DATA_DIR / "cases").iterdir() if p.is_dir())


def load_labels(case_id: str) -> CaseLabels:
    path = DATA_DIR / "cases" / case_id / "labels.json"
    return CaseLabels.model_validate_json(path.read_text(encoding="utf-8"))


def labels_hash(case_ids: list[str]) -> str:
    h = hashlib.sha256()
    for cid in sorted(case_ids):
        h.update((DATA_DIR / "cases" / cid / "labels.json").read_bytes())
    return h.hexdigest()[:12]


def run_eval(
    name: str,
    store: Store,
    model_id: str | None = None,
    case_ids: list[str] | None = None,
    repeats: int | None = None,
    concurrency: int | None = None,
    complete: Complete = openai_complete,
    progress: Callable[[str], None] = print,
) -> str:
    cfg = settings()["evals"]
    model_id = model_id or model("agent")
    case_ids = case_ids or all_case_ids()
    repeats = repeats or cfg["repeats"]
    concurrency = concurrency or cfg["concurrency"]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    eval_id = f"eval-{datetime.now():%Y%m%d-%H%M%S}-{slug}"
    store.create_eval(
        eval_id,
        name=name,
        model=model_id,
        repeats=repeats,
        case_ids=json.dumps(case_ids),
        prompt_hash=prompt_hash(),
        git_sha=git_sha(),
        settings=json.dumps(settings()["agent"]),
        skill_hashes=json.dumps({n: s.content_hash() for n, s in load_skills().items()}),
    )
    jobs = [(cid, p, new_run_id(cid)) for p in range(1, repeats + 1) for cid in case_ids]
    for cid, p, run_id in jobs:
        store.add_eval_item(eval_id, cid, p, run_id)

    def work(job):
        cid, p, run_id = job
        try:  # each thread gets its own SQLite connection
            r = run_case(cid, model_id, Store(store.path), complete, run_id)
            return job, r.status, r.cost_usd
        except Exception as e:  # the run row records the error; keep going
            return job, f"error ({type(e).__name__}: {e})", None

    progress(
        f"{eval_id}: {len(jobs)} runs ({len(case_ids)} cases x {repeats} passes) "
        f"on {model_id}, {concurrency} at a time"
    )
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(work, job) for job in jobs]
        for i, fut in enumerate(as_completed(futures), start=1):
            (cid, p, _), status, cost = fut.result()
            cost_s = "" if cost is None else f" ${cost:.4f}"
            progress(f"  [{i}/{len(jobs)}] {cid} pass {p}: {status}{cost_s}")
    score_eval(eval_id, store)
    return eval_id


def _run_view(store: Store, case_id: str, run_id: str) -> RunView:
    run = store.get_run(run_id)
    if run is None:  # the run never started (e.g. crashed before its first write)
        return RunView(run_id, case_id, "missing", None)
    findings = Findings.model_validate_json(run["findings"]) if run["findings"] else None
    return RunView(
        run_id,
        case_id,
        run["status"],
        findings,
        loaded_skills=json.loads(run["loaded_skills"] or "[]"),
        llm_calls=run["llm_calls"],
        cost_usd=run["cost_usd"],
        latency_ms=run["latency_ms"] or 0,
        citation_rejections=store.citation_rejections(run_id),
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stats(per_pass: list[float | None], n_cases: int | None) -> dict:
    vals = [v for v in per_pass if v is not None]
    return {
        "mean": _mean(vals),
        "sd": statistics.stdev(vals) if len(vals) >= 2 else 0.0,
        "passes": per_pass,
        "n_cases": n_cases,
    }


def _ambiguity_precision(rows: list[dict]) -> float | None:
    """True ambiguity flags / all ambiguity flags raised, within one pass."""
    tp = sum(s["ambiguity_recall"].value or 0 for s in rows)
    fp = sum(s["ambiguity_false_flag"].value or 0 for s in rows)
    return tp / (tp + fp) if tp + fp else None


def summarize(per_case: list[tuple[str, int, dict]]) -> dict:
    """Aggregate per-case scores into one value per pass, then mean and sd across passes."""
    passes = sorted({p for _, p, _ in per_case})
    by_pass = [[s for _, rp, s in per_case if rp == p] for p in passes]
    summary = {}
    for m in METRICS:
        per_pass = [
            _mean([s[m.name].value for s in rows if s[m.name].value is not None])
            for rows in by_pass
        ]
        n_cases = sum(s[m.name].value is not None for s in by_pass[0])
        summary[m.name] = _stats(per_pass, n_cases)
    summary["ambiguity_precision"] = _stats([_ambiguity_precision(r) for r in by_pass], None)
    summary["_total_cost_usd"] = sum(s["cost_usd"].value or 0 for _, _, s in per_case)
    return summary


def score_eval(eval_id: str, store: Store) -> dict:
    ev = store.get_eval(eval_id)
    case_ids = json.loads(ev["case_ids"])
    labels = {cid: load_labels(cid) for cid in case_ids}
    rows, per_case = [], []
    for item in store.eval_items(eval_id):
        cid, p, run_id = item["case_id"], item["pass"], item["run_id"]
        scores = score_case(labels[cid], _run_view(store, cid, run_id))
        per_case.append((cid, p, scores))
        rows += [
            (
                cid,
                p,
                run_id,
                name,
                sc.value,
                json.dumps(sc.expected, default=str),
                json.dumps(sc.actual, default=str),
            )
            for name, sc in scores.items()
        ]
    summary = summarize(per_case)
    store.save_eval_results(
        eval_id, rows, labels_hash=labels_hash(case_ids), summary=json.dumps(summary)
    )
    return summary
