"""Command-line runner.

uv run appeal-agent run case-031 [case-005 ...] [--model MODEL_ID]
uv run appeal-agent trace RUN_ID [--full] [--json]
uv run appeal-agent runs [--limit 20]
"""

import argparse
import json
import sys
import textwrap

from appeal_agent.agent.loop import run_case
from appeal_agent.config import model
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
