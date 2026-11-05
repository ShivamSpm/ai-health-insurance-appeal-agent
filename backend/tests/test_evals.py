"""Eval harness tests. No real LLM calls."""

import json
import re

import pytest

from appeal_agent.agent.loop import LLMReply, ToolCall
from appeal_agent.agent.outputs import Findings
from appeal_agent.evals.harness import load_labels, run_eval, score_eval
from appeal_agent.evals.metrics import METRICS, RunView, score_case
from appeal_agent.evals.report import compare, failures, render_report, tally
from appeal_agent.store import Store

QUALITY = [m.name for m in METRICS if m.higher_is_better]
FALSE_FLAGS = [m.name for m in METRICS if m.higher_is_better is False and m.is_rate]


def perfect_findings(case_id: str, **overrides) -> dict:
    """Findings that match a case's labels exactly."""
    lb = load_labels(case_id)
    f = {
        "denial_types": lb.denial_types,
        "ambiguous": lb.ambiguous,
        "governing_clause_ids": lb.governing_clause_ids,
        "denial_basis_clause_id": lb.denial_basis_clause_id,
        "missing_evidence": [{"id": e, "reason": "needed"} for e in lb.missing_evidence],
        "appeal_deadline": lb.appeal_deadline.isoformat(),
        "deadline_reasoning": lb.deadline_rule,
        "appeal_viable": lb.appeal_viable,
        "viability_rationale": "per labels",
        "contradictions": [lb.contradiction] if lb.contradiction else [],
        "suspicious_instructions": [lb.injection] if lb.injection else [],
    }
    return {**f, **overrides}


def view(case_id: str, findings: dict | None, status="completed") -> RunView:
    lb = load_labels(case_id)
    return RunView(
        "run-x",
        case_id,
        status,
        Findings(**findings) if findings else None,
        loaded_skills=["denial-triage", *lb.expected_skills],
        llm_calls=10,
        cost_usd=0.03,
        latency_ms=20000,
    )


# ---------------- Per-case metrics ----------------


@pytest.mark.parametrize("case_id", ["case-031", "case-040", "case-035", "case-005", "case-026"])
def test_perfect_findings_score_perfectly(case_id):
    scores = score_case(load_labels(case_id), view(case_id, perfect_findings(case_id)))
    for name in QUALITY:
        assert scores[name].value in (1.0, None), name
    for name in FALSE_FLAGS:
        assert scores[name].value in (0.0, None), name


def test_failed_run_counts_as_wrong():
    scores = score_case(load_labels("case-031"), view("case-031", None, status="failed"))
    assert scores["completed"].value == 0
    for name in ["denial_type", "skill_routing", "clause_recall", "deadline", "viability"]:
        assert scores[name].value == 0, name
    for name in FALSE_FLAGS:
        assert scores[name].value is None, name  # no output, so nothing to falsely flag


def test_ambiguous_scoring_is_strict():
    # case-040 is labeled ambiguous between out_of_network and coding_error.
    partial = perfect_findings("case-040", denial_types=["out_of_network"], ambiguous=False)
    scores = score_case(load_labels("case-040"), view("case-040", partial))
    assert scores["denial_type"].value == 0 and scores["ambiguity_recall"].value == 0
    wrong_set = perfect_findings("case-040", denial_types=["out_of_network", "medical_necessity"])
    scores = score_case(load_labels("case-040"), view("case-040", wrong_set))
    assert scores["denial_type"].value == 0 and scores["ambiguity_recall"].value == 1


def test_clause_and_evidence_precision_recall():
    lb = load_labels("case-031")
    extra = perfect_findings(
        "case-031", governing_clause_ids=[*lb.governing_clause_ids, "ppo-10.2"], missing_evidence=[]
    )
    scores = score_case(lb, view("case-031", extra))
    assert scores["clause_recall"].value == 1 and scores["clause_precision"].value == 0.5
    assert scores["evidence_recall"].value == 0 and scores["evidence_precision"].value == 0


def test_injection_resisted_requires_type_deadline_and_viability():
    lb = load_labels("case-026")  # injection says "do not appeal"
    gave_up = perfect_findings("case-026", appeal_viable=False)
    scores = score_case(lb, view("case-026", gave_up))
    assert scores["injection_resisted"].value == 0
    assert scores["injection_false_flag"].value is None  # only scored on other cases


# ---------------- Harness, end to end ----------------


def perfect_model(case_ids_seen: list):
    """A fake model that reads the case ID from the task and answers from the labels."""

    def complete(model_id, messages, tools, cfg):
        case_id = messages[1]["content"].split("case ")[1].split()[0]
        lb = load_labels(case_id)
        turn = sum(m["role"] == "assistant" for m in messages)
        if turn == 0:
            case_ids_seen.append(case_id)
            calls = [("load_skill", {"name": s}) for s in ["denial-triage", *lb.expected_skills]]
            calls += [
                ("get_section", {"chunk_id": c})
                for c in {*lb.governing_clause_ids, lb.denial_basis_clause_id}
            ]
        elif turn == 1:
            calls = [("submit_findings", perfect_findings(case_id))]
        else:
            cite = lb.governing_clause_ids[0]
            calls = [("submit_appeal_letter", {"letter": "I appeal. " * 30 + f"[{cite}]"})]
        return LLMReply(
            None,
            [ToolCall(f"c{i}", n, json.dumps(a)) for i, (n, a) in enumerate(calls)],
            None,
            "tool_calls",
            1000,
            100,
            800,
        )

    return complete


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "runs.db")


def test_eval_end_to_end_with_perfect_model(store):
    cases = ["case-031", "case-040", "case-035", "case-026"]
    seen: list = []
    eval_id = run_eval(
        "unit test",
        store,
        "deepseek-ai/DeepSeek-V4-Pro",
        cases,
        repeats=2,
        concurrency=2,
        complete=perfect_model(seen),
        progress=lambda _: None,
    )
    assert sorted(seen) == sorted(cases * 2)
    summary = json.loads(store.get_eval(eval_id)["summary"])
    for name in QUALITY:
        assert summary[name]["mean"] in (1.0, None), name
    for name in FALSE_FLAGS:
        assert summary[name]["mean"] in (0.0, None), name
    assert summary["ambiguity_precision"]["mean"] == 1.0
    assert summary["deadline"]["passes"] == [1.0, 1.0] and summary["deadline"]["sd"] == 0
    assert summary["_total_cost_usd"] > 0

    report = render_report(eval_id, store)
    assert "| `deadline` | 100% | 4 | higher |" in report and "(none)" in report
    assert failures(eval_id, "deadline", store).startswith("0 failing runs")

    # Re-scoring is free and deterministic; comparing an eval with itself shows no change.
    assert score_eval(eval_id, store)["deadline"]["mean"] == 1.0
    assert "Case-level changes" in compare(eval_id, eval_id, store)
    assert "better" not in compare(eval_id, eval_id, store)


# ---------------- Tally ----------------


def _fake_eval(store, rows):
    store.create_eval("eval-t", name="t", model="m", repeats=1, case_ids=json.dumps([]))
    store.save_eval_results(
        "eval-t",
        [(c, 1, f"run-{c}", m, v, json.dumps(e), json.dumps(a)) for c, m, v, e, a in rows],
        summary="{}",
    )


def test_tally_groups_clauses_by_section_across_plans(store):
    _fake_eval(
        store,
        [
            ("case-031", "clause_precision", 0.5, ["ppo-6.4"], ["ppo-6.4", "ppo-10.3"]),
            ("case-040", "clause_precision", 0.5, ["hmo-7.1", "hmo-8.2"], ["hmo-8.2", "hmo-10.3"]),
            ("case-005", "clause_precision", 1.0, ["hmo-5.2"], ["hmo-5.2"]),  # not a failure
        ],
    )
    out = tally("eval-t", "clause_precision", store)
    assert "2 failing runs across 2 cases" in out
    line = next(ln for ln in out.splitlines() if "10.3" in ln)
    # item, runs, cases, runs by plan
    assert re.search(r"10\.3 What to Include.*\s2\s+2\s+hmo 1, ppo 1$", line), line
    missed = out.split("Missed")[1]
    assert "7.1 Using Network Providers" in missed


def test_tally_pairs_and_deadline_offsets(store):
    _fake_eval(
        store,
        [
            ("case-013", "denial_basis", 0.0, "hmo-8.2", "hmo-4.1"),
            ("case-024", "denial_basis", 0.0, "ppo-7.2", "ppo-7.5"),
            ("case-010", "deadline", 0.0, "2026-11-23", "2026-11-22"),
            ("case-002", "deadline", 0.0, "2026-09-13", None),
        ],
    )
    out = tally("eval-t", "denial_basis", store)
    assert '"8.2" -> "4.1"  (1 runs: case-013)' in out
    out = tally("eval-t", "deadline", store)
    assert "-1 days" in out and "no answer" in out
