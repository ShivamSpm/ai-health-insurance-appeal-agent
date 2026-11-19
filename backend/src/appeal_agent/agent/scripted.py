"""A scripted stand-in for the LLM that answers dataset cases from their labels.

Used by the tests and by `appeal-agent serve --fake-model` for end-to-end UI tests.
It makes no network calls and costs nothing. It only knows dataset cases.
"""

import json

from appeal_agent.agent.loop import Complete, LLMReply, ToolCall
from appeal_agent.evals.harness import load_labels


def perfect_findings(case_id: str, **overrides) -> dict:
    """Findings that match a case's labels exactly."""
    lb = load_labels(case_id)
    f = {
        "denial_types": lb.denial_types,
        "ambiguous": lb.ambiguous,
        "governing_clause_ids": lb.governing_clause_ids,
        "denial_basis_clause_ids": lb.denial_basis_clause_ids,
        "missing_evidence": [{"id": e, "reason": "needed"} for e in lb.missing_evidence],
        "appeal_deadline": lb.appeal_deadline.isoformat(),
        "deadline_reasoning": lb.deadline_rule,
        "appeal_viable": lb.appeal_viable,
        "viability_rationale": "per labels",
        "contradictions": [lb.contradiction] if lb.contradiction else [],
        "suspicious_instructions": [lb.injection] if lb.injection else [],
    }
    return {**f, **overrides}


def scripted_model(case_ids_seen: list | None = None) -> Complete:
    """Turn 1: load skills and fetch the labeled sections. Turn 2: submit the labeled
    findings. Turn 3: submit a short letter citing the first governing clause."""

    def complete(model_id, messages, tools, cfg):
        case_id = messages[1]["content"].split("case ")[1].split()[0]
        lb = load_labels(case_id)
        turn = sum(m["role"] == "assistant" for m in messages)
        if turn == 0:
            if case_ids_seen is not None:
                case_ids_seen.append(case_id)
            calls = [("load_skill", {"name": s}) for s in ["denial-triage", *lb.expected_skills]]
            calls += [
                ("get_section", {"chunk_id": c})
                for c in {*lb.governing_clause_ids, *lb.denial_basis_clause_ids}
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
