"""Command-line runner.

uv run appeal-agent run case-031 [case-005 ...] [--model MODEL_ID]
uv run appeal-agent trace RUN_ID [--full] [--json]
uv run appeal-agent runs [--limit 20]
uv run appeal-agent eval run --name baseline [--model M] [--cases ...] [--repeats N]
uv run appeal-agent eval score|report EVAL_ID
uv run appeal-agent eval compare EVAL_A EVAL_B
uv run appeal-agent eval failures EVAL_ID --metric deadline [--tally]
uv run appeal-agent eval list
"""

import argparse
import json
import sys
import textwrap

from appeal_agent.agent.loop import run_case
from appeal_agent.config import model
from appeal_agent.evals.harness import run_eval, score_eval
from appeal_agent.evals.metrics import METRICS
from appeal_agent.evals.report import compare, failures, render_report, tally, write_report
from appeal_agent.store import Store


def _money(v) -> str:
    return "n/a" if v is None else f"${v:.4f}"


def _clip(text: str | None, n: int, full: bool) -> str:
    text = (text or "").strip()
    return text if full or len(text) <= n else text[:n] + f" ... [{len(text) - n} more chars]"


def cmd_run(args) -> int:
    store = Store()
    model_id = args.model or model("agent")
    failed = 0
    for case_id in args.case_ids:
        print(f"Running {case_id} on {model_id} ...", flush=True)
        r = run_case(case_id, model_id, store)
        failed += r.status != "completed"
        print(
            f"  {r.status}: {r.llm_calls} LLM calls, {r.prompt_tokens:,} in "
            f"({r.cached_tokens:,} cached) / {r.completion_tokens:,} out, "
            f"{_money(r.cost_usd)}, {r.latency_ms / 1000:.1f}s"
        )
        if r.error:
            print(f"  error: {r.error}")
        if r.findings:
            f = r.findings
            print(
                f"  types: {', '.join(f.denial_types)}{' (ambiguous)' if f.ambiguous else ''}"
                f" | clauses: {', '.join(f.governing_clause_ids)} | deadline: "
                f"{f.appeal_deadline} | viable: {f.appeal_viable}"
            )
        print(f"  trace: uv run appeal-agent trace {r.run_id}")
    return 1 if failed else 0


def cmd_trace(args) -> int:
    store = Store()
    run = store.get_run(args.run_id)
    if run is None:
        print(f"No run {args.run_id}", file=sys.stderr)
        return 1
    steps = store.get_steps(args.run_id)
    if args.json:
        print(json.dumps({"run": dict(run), "steps": [dict(s) for s in steps]}, indent=2))
        return 0

    print(
        f"Run {run['id']}\n  case {run['case_id']} | model {run['model']} | {run['status']}"
        + (f" ({run['error']})" if run["error"] else "")
    )
    print(
        f"  {run['llm_calls']} LLM calls | {run['prompt_tokens']:,} in "
        f"({run['cached_tokens']:,} cached) / {run['completion_tokens']:,} out | "
        f"{_money(run['cost_usd'])} | {run['latency_ms'] / 1000:.1f}s"
    )
    print(f"  prompt {run['prompt_hash']} | git {run['git_sha']}")
    print(f"  skills loaded: {', '.join(json.loads(run['loaded_skills'] or '[]')) or 'none'}")
    print(f"  sections retrieved: {', '.join(json.loads(run['retrieved'] or '[]')) or 'none'}\n")

    for s in steps:
        if s["kind"] == "llm":
            out = json.loads(s["output"])
            print(
                f"#{s['idx']:>3} LLM   {s['latency_ms'] / 1000:5.1f}s  in {s['prompt_tokens']:,}"
                f" ({s['cached_tokens']:,} cached) out {s['completion_tokens']:,}  "
                f"{_money(s['cost_usd'])}"
            )
            if s["reasoning"]:
                print(
                    textwrap.indent(
                        "thinking: " + _clip(s["reasoning"], 300, args.full), "        "
                    )
                )
            if out["content"]:
                print(textwrap.indent("says: " + _clip(out["content"], 300, args.full), "        "))
            for tc in out["tool_calls"]:
                print(f"        -> {tc['name']}({_clip(tc['arguments'], 200, args.full)})")
        else:
            flag = "  INVALID" if s["invalid"] else ""
            print(f"#{s['idx']:>3} TOOL  {s['name']}{flag}")
            print(textwrap.indent(_clip(s["output"], 400, args.full), "        "))

    if run["findings"]:
        print(
            "\nFindings:\n"
            + textwrap.indent(json.dumps(json.loads(run["findings"]), indent=2), "  ")
        )
    if run["letter"]:
        print("\nLetter:\n" + textwrap.indent(run["letter"], "  "))
    return 0


def cmd_runs(args) -> int:
    for r in Store().list_runs(args.limit):
        print(
            f"{r['id']}  {r['model']:<34} {r['status']:<10} {r['llm_calls']:>3} calls  "
            f"{_money(r['cost_usd'])}"
        )
    return 0


def _known_eval(store: Store, eval_id: str) -> bool:
    if store.get_eval(eval_id) is None:
        print(f"No eval {eval_id}", file=sys.stderr)
        return False
    return True


def cmd_eval_run(args) -> int:
    store = Store()
    eval_id = run_eval(args.name, store, args.model, args.cases, args.repeats, args.concurrency)
    path = write_report(eval_id, store)
    print(f"\n{render_report(eval_id, store)}\nReport written to {path}")
    return 0


def cmd_eval_score(args) -> int:
    store = Store()
    if not _known_eval(store, args.eval_id):
        return 1
    score_eval(args.eval_id, store)
    print(f"Re-scored. Report written to {write_report(args.eval_id, store)}")
    return 0


def cmd_eval_report(args) -> int:
    store = Store()
    if not _known_eval(store, args.eval_id):
        return 1
    print(render_report(args.eval_id, store))
    return 0


def cmd_eval_compare(args) -> int:
    store = Store()
    if not (_known_eval(store, args.eval_a) and _known_eval(store, args.eval_b)):
        return 1
    print(compare(args.eval_a, args.eval_b, store))
    return 0


def cmd_eval_failures(args) -> int:
    store = Store()
    if not _known_eval(store, args.eval_id):
        return 1
    print((tally if args.tally else failures)(args.eval_id, args.metric, store))
    return 0


def cmd_eval_list(args) -> int:
    for e in Store().list_evals(args.limit):
        summary = json.loads(e["summary"] or "{}")
        cost = summary.get("_total_cost_usd")
        print(
            f"{e['id']}  {e['model']:<34} {e['repeats']} passes  "
            f"{len(json.loads(e['case_ids']))} cases  {_money(cost)}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="appeal-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Run the agent on one or more cases.")
    p.add_argument("case_ids", nargs="+")
    p.add_argument("--model", help="Model ID (default: [models].agent in config.toml).")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("trace", help="Show a run's step-by-step trace.")
    p.add_argument("run_id")
    p.add_argument("--full", action="store_true", help="Don't truncate long text.")
    p.add_argument("--json", action="store_true", help="Print the raw run and steps as JSON.")
    p.set_defaults(func=cmd_trace)

    p = sub.add_parser("runs", help="List recent runs.")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_runs)

    ev = sub.add_parser("eval", help="Run, score and inspect evals.")
    esub = ev.add_subparsers(dest="eval_command", required=True)

    p = esub.add_parser("run", help="Run cases (repeated) and score them.")
    p.add_argument("--name", required=True, help="Short label, e.g. 'baseline'.")
    p.add_argument("--model", help="Model ID (default: [models].agent in config.toml).")
    p.add_argument("--cases", nargs="+", help="Case IDs (default: all cases).")
    p.add_argument("--repeats", type=int, help="Passes per case (default: config).")
    p.add_argument("--concurrency", type=int, help="Parallel runs (default: config).")
    p.set_defaults(func=cmd_eval_run)

    p = esub.add_parser("score", help="Re-score stored runs (free; use after label changes).")
    p.add_argument("eval_id")
    p.set_defaults(func=cmd_eval_score)

    p = esub.add_parser("report", help="Print an eval's report.")
    p.add_argument("eval_id")
    p.set_defaults(func=cmd_eval_report)

    p = esub.add_parser("compare", help="Compare two evals.")
    p.add_argument("eval_a")
    p.add_argument("eval_b")
    p.set_defaults(func=cmd_eval_compare)

    p = esub.add_parser("failures", help="List failing runs for one metric.")
    p.add_argument("eval_id")
    p.add_argument("--metric", required=True, choices=[m.name for m in METRICS])
    p.add_argument("--tally", action="store_true", help="Count the most common wrong answers.")
    p.set_defaults(func=cmd_eval_failures)

    p = esub.add_parser("list", help="List recent evals.")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_eval_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
