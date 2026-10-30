"""Eval reports (Markdown), comparisons between evals, and the failure browser."""

import json
from collections import defaultdict
from pathlib import Path

from appeal_agent.config import REPO_ROOT, settings
from appeal_agent.evals.harness import load_labels
from appeal_agent.evals.metrics import METRICS, METRICS_BY_NAME, Metric
from appeal_agent.store import Store

AMBIGUITY_PRECISION = Metric("ambiguity_precision", "Ambiguity flags that were correct", True)
# Report order: the derived ambiguity precision sits next to its recall.
REPORT_METRICS = [*METRICS[:3], AMBIGUITY_PRECISION, *METRICS[3:]]


def _fmt(metric: Metric, value: float | None) -> str:
    if value is None:
        return "n/a"
    if metric.name == "cost_usd":
        return f"${value:.4f}"
    return f"{value:.0%}" if metric.is_rate else f"{value:.2f}"


def _fmt_stat(metric: Metric, stat: dict) -> str:
    if stat["mean"] is None:
        return "n/a"
    sd = stat["sd"]
    spread = f" ± {sd * 100:.0f}" if metric.is_rate else f" ± {sd:.2f}"
    return _fmt(metric, stat["mean"]) + (spread if sd else "")


def _direction(metric: Metric) -> str:
    return {True: "higher", False: "lower", None: ""}[metric.higher_is_better]


def _is_failure(metric: Metric, value: float | None) -> bool:
    if value is None or metric.higher_is_better is None:
        return False
    return value < 1 if metric.higher_is_better else value > 0


def render_report(eval_id: str, store: Store) -> str:
    ev = store.get_eval(eval_id)
    summary = json.loads(ev["summary"])
    case_ids = json.loads(ev["case_ids"])
    n_runs = len(case_ids) * ev["repeats"]
    completed = summary["completed"]["mean"] or 0
    lines = [
        f"# Eval `{eval_id}`",
        "",
        f"- **Name:** {ev['name']}",
        f"- **Model:** `{ev['model']}`",
        f"- **Cases:** {len(case_ids)} x {ev['repeats']} passes = {n_runs} runs",
        f"- **Created:** {ev['created_at']} | **Scored:** {ev['scored_at']}",
        f"- **Versions:** git `{ev['git_sha']}` | prompt `{ev['prompt_hash']}` | "
        f"labels `{ev['labels_hash']}`",
        "- **Skills:** "
        + ", ".join(f"{k} `{v}`" for k, v in json.loads(ev["skill_hashes"]).items()),
        f"- **Total cost:** ${summary['_total_cost_usd']:.2f} | **Completed:** {completed:.0%}",
        "",
        "## Metrics",
        "",
        "Mean across passes, ± standard deviation in percentage points (rates) or units. "
        "Failed runs count as wrong.",
        "",
        "| Metric | Score | Cases | Better | What it measures |",
        "|---|---|---|---|---|",
    ]
    for m in REPORT_METRICS:
        stat = summary[m.name]
        n = "" if stat["n_cases"] is None else str(stat["n_cases"])
        lines.append(
            f"| `{m.name}` | {_fmt_stat(m, stat)} | {n} | {_direction(m)} | {m.description} |"
        )

    # Per-case failures, counted across passes.
    fails: dict[str, dict[str, int]] = defaultdict(dict)
    for r in store.eval_results(eval_id):
        m = METRICS_BY_NAME[r["metric"]]
        if _is_failure(m, r["value"]):
            fails[r["case_id"]][m.name] = fails[r["case_id"]].get(m.name, 0) + 1
    lines += [
        "",
        "## Cases with failures",
        "",
        f"Failing metrics per case, as failed passes / {ev['repeats']}.",
        "",
        "| Case | Kind | Scenario | Failing metrics |",
        "|---|---|---|---|",
    ]
    for cid in sorted(fails):
        lb = load_labels(cid)
        detail = ", ".join(f"{name} {n}/{ev['repeats']}" for name, n in fails[cid].items())
        lines.append(f"| {cid} | {lb.hard_kind or 'standard'} | {lb.scenario} | {detail} |")
    if not fails:
        lines.append("| (none) | | | |")
    lines += [
        "",
        "## Explore",
        "",
        "```bash",
        f"uv run appeal-agent eval failures {eval_id} --metric deadline",
        "uv run appeal-agent trace <run_id>",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_report(eval_id: str, store: Store) -> Path:
    out_dir = REPO_ROOT / settings()["evals"]["reports_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{eval_id}.md"
    path.write_text(render_report(eval_id, store), encoding="utf-8", newline="\n")
    return path


def compare(eval_a: str, eval_b: str, store: Store) -> str:
    a, b = store.get_eval(eval_a), store.get_eval(eval_b)
    sa, sb = json.loads(a["summary"]), json.loads(b["summary"])
    lines = [
        f"A: {eval_a} ({a['model']}, prompt {a['prompt_hash']}, git {a['git_sha']})",
        f"B: {eval_b} ({b['model']}, prompt {b['prompt_hash']}, git {b['git_sha']})",
        "",
        "| Metric | A | B | Change |",
        "|---|---|---|---|",
    ]
    for m in REPORT_METRICS:
        ma, mb = sa[m.name]["mean"], sb[m.name]["mean"]
        if ma is None or mb is None:
            change = ""
        else:
            delta = mb - ma
            better = (
                m.higher_is_better is not None and delta != 0 and (delta > 0) == m.higher_is_better
            )
            worse = m.higher_is_better is not None and delta != 0 and not better
            size = f"{delta * 100:+.0f} pts" if m.is_rate else f"{delta:+.2f}"
            change = size + (" better" if better else " worse" if worse else "")
        lines.append(
            f"| `{m.name}` | {_fmt_stat(m, sa[m.name])} | {_fmt_stat(m, sb[m.name])} | {change} |"
        )

    # Cases whose pass rate moved, per quality metric.
    def rates(eval_id):
        acc = defaultdict(list)
        for r in store.eval_results(eval_id):
            if r["value"] is not None and METRICS_BY_NAME[r["metric"]].higher_is_better:
                acc[(r["case_id"], r["metric"])].append(r["value"])
        return {k: sum(v) / len(v) for k, v in acc.items()}

    ra, rb = rates(eval_a), rates(eval_b)
    moved = sorted((k, ra[k], rb[k]) for k in ra.keys() & rb.keys() if abs(ra[k] - rb[k]) > 1e-9)
    lines += ["", "Case-level changes (mean score per case across passes):", ""]
    lines += [f"  {cid} {metric}: {va:.0%} -> {vb:.0%}" for (cid, metric), va, vb in moved]
    if not moved:
        lines.append("  (none)")
    return "\n".join(lines)


def failures(eval_id: str, metric_name: str, store: Store) -> str:
    metric = METRICS_BY_NAME[metric_name]
    rows = [r for r in store.eval_results(eval_id, metric_name) if _is_failure(metric, r["value"])]
    lines = [f"{len(rows)} failing runs for `{metric_name}` ({metric.description})", ""]
    for r in rows:
        lb = load_labels(r["case_id"])
        lines += [
            f"{r['case_id']} pass {r['pass']} | {lb.hard_kind or 'standard'} | {lb.scenario} "
            f"| score {_fmt(metric, r['value'])}",
            f"  expected: {r['expected']}",
            f"  actual:   {r['actual']}",
            f"  trace:    uv run appeal-agent trace {r['run_id']}",
            "",
        ]
    return "\n".join(lines)
