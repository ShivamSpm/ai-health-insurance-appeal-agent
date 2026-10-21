"""Dataset types: what the agent receives for a case, and the hidden labels."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from appeal_agent.domain import DenialType

HardKind = Literal["ambiguous", "valid_denial", "contradictory", "prompt_injection"]


class CaseInputs(BaseModel):
    """What the agent receives. Never includes labels."""

    case_id: str
    plan_id: str
    plan_file: str
    denial_letter_file: str
    member_note_file: str


class CaseLabels(BaseModel):
    """Ground truth for one case. Hidden from the agent."""

    case_id: str
    scenario: str
    plan_id: str
    hard_kind: HardKind | None
    denial_types: list[DenialType]  # one type, or two or more when ambiguous
    ambiguous: bool
    expected_skills: list[str]
    governing_clause_ids: list[str]  # clauses the appeal relies on
    denial_basis_clause_id: str  # clause the insurer relies on; the letter may cite it
    required_evidence: list[str]
    member_has: list[str]
    missing_evidence: list[str]
    notice_date: date
    appeal_deadline: date
    deadline_rule: str
    appeal_viable: bool
    contradiction: str | None
    injection: str | None
    notes: str
