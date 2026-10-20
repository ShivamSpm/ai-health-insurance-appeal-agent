"""Label-consistency tests for the synthetic dataset. No LLM calls."""

import re
from collections import Counter
from datetime import date

import pytest

from appeal_agent.dataset.build import build_cases
from appeal_agent.dataset.plans import PLANS, render_plan, section_numbers
from appeal_agent.dataset.prose import DATE_PATTERNS, NOTE_BANNED
from appeal_agent.dataset.scenarios import SCENARIOS
from appeal_agent.dataset.schema import DENIAL_TYPES, EVIDENCE_BY_ID

CASES = build_cases()


def test_case_mix():
    assert len(CASES) == 40
    hard = Counter(c.labels.hard_kind for c in CASES)
    assert hard == {
        None: 28,
        "ambiguous": 3,
        "valid_denial": 3,
        "contradictory": 3,
        "prompt_injection": 3,
    }
    standard = Counter(c.labels.denial_types[0] for c in CASES if c.labels.hard_kind is None)
    assert standard == {t: 7 for t in DENIAL_TYPES}


def test_scenario_keys_unique():
    keys = [s.key for s in SCENARIOS]
    assert len(keys) == len(set(keys))


def test_ambiguity_flag_matches_types():
    for c in CASES:
        lb = c.labels
        assert lb.ambiguous == (lb.hard_kind == "ambiguous")
        assert len(lb.denial_types) == (2 if lb.ambiguous else 1)


def test_only_valid_denials_are_not_viable():
    for c in CASES:
        assert c.labels.appeal_viable == (c.labels.hard_kind != "valid_denial")


def test_clauses_exist_in_plan():
    for c in CASES:
        plan = PLANS[c.labels.plan_id]
        text = render_plan(plan)
        for clause_id in [*c.labels.governing_clause_ids, c.labels.denial_basis_clause_id]:
            number = clause_id.removeprefix(f"{plan.plan_id}-")
            assert number in section_numbers(plan), clause_id
            assert f"### {number} " in text


def test_evidence_labels_consistent():
    for c in CASES:
        lb = c.labels
        for e in lb.required_evidence + lb.member_has:
            assert e in EVIDENCE_BY_ID
        assert lb.missing_evidence == [e for e in lb.required_evidence if e not in lb.member_has]
        for t in lb.denial_types:
            assert set(PLANS[lb.plan_id].requirements[t]) <= set(lb.required_evidence)


def test_unrelated_items_dont_hint_at_denial_type():
    # Items the member has beyond what's required must not be evidence that any plan
    # asks for with these denial types; otherwise they leak the answer.
    for c in CASES:
        lb = c.labels
        related = {e for p in PLANS.values() for t in lb.denial_types for e in p.requirements[t]}
        extras = set(lb.member_has) - set(lb.required_evidence)
        assert not extras & related, (lb.case_id, extras & related)


def test_every_case_has_missing_evidence():
    # Every case should leave the agent something to find.
    assert all(c.labels.missing_evidence for c in CASES)


@pytest.mark.parametrize(
    ("plan_id", "notice", "expected"),
    [
        # PPO: deemed received 5 days later, then 180 days.
        ("ppo", date(2026, 3, 2), date(2026, 9, 3)),
        # HMO: 60 days from the notice date.
        ("hmo", date(2026, 7, 1), date(2026, 8, 30)),
        # EPO: 90 days lands on Sat 2026-10-10, so it rolls to Mon 2026-10-12.
        ("epo", date(2026, 7, 12), date(2026, 10, 12)),
        # EPO: 90 days lands on a Tuesday, no rollover.
        ("epo", date(2026, 7, 1), date(2026, 9, 29)),
    ],
)
def test_appeal_deadline(plan_id, notice, expected):
    assert PLANS[plan_id].appeal_deadline(notice)[0] == expected


def test_epo_weekend_rollover_appears_in_dataset():
    assert any("weekend" in c.labels.deadline_rule for c in CASES)


def test_plan_states_its_deadline_rule():
    for plan in PLANS.values():
        text = render_plan(plan)
        assert f"within {plan.appeal_days} calendar days" in text
        assert ("Saturday or Sunday" in text) == plan.weekend_rollover


def test_injection_and_contradiction_only_on_their_cases():
    for c in CASES:
        lb = c.labels
        assert (lb.injection is not None) == (lb.hard_kind == "prompt_injection")
        assert (lb.contradiction is not None) == (lb.hard_kind == "contradictory")


def test_stories_pass_note_rules():
    # The note prompt forbids these words, so the stories must not need them.
    for s in SCENARIOS:
        assert not NOTE_BANNED.search(s.story), s.key
        assert not any(re.search(p, s.story) for p in DATE_PATTERNS), s.key
