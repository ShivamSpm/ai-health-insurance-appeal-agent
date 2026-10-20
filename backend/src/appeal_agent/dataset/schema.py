"""Dataset types: denial types, the evidence vocabulary, and case labels.

The evidence vocabulary is the eval contract for "missing evidence". It is
independent of the agent's skills; skill checklists must use these IDs.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

DenialType = Literal["medical_necessity", "prior_authorization", "out_of_network", "coding_error"]
HardKind = Literal["ambiguous", "valid_denial", "contradictory", "prompt_injection"]

DENIAL_TYPES: list[str] = list(DenialType.__args__)

SKILL_FOR_TYPE: dict[str, str] = {
    "medical_necessity": "medical-necessity-appeal",
    "prior_authorization": "prior-authorization-appeal",
    "out_of_network": "out-of-network-appeal",
    "coding_error": "coding-error-appeal",
}


class EvidenceItem(BaseModel):
    id: str
    name: str
    description: str
    # How a member might describe having this item. Used in member notes.
    member_phrases: list[str]


EVIDENCE: list[EvidenceItem] = [
    EvidenceItem(
        id="letter_of_medical_necessity",
        name="Letter of medical necessity",
        description="A letter from the treating provider explaining why the service is "
        "medically necessary for this patient.",
        member_phrases=[
            "a letter from my doctor explaining why I need this",
            "my doctor's signed letter saying this treatment is necessary for me",
        ],
    ),
    EvidenceItem(
        id="medical_records",
        name="Relevant medical records",
        description="Clinical notes, history and records relevant to the service.",
        member_phrases=[
            "copies of my medical records from my doctor's office",
            "my chart notes from my recent visits",
        ],
    ),
    EvidenceItem(
        id="conservative_treatment_records",
        name="Records of prior treatments tried",
        description="Documentation of less intensive treatments or drugs tried first, "
        "and their results.",
        member_phrases=[
            "records of the other treatments I tried first and how they went",
            "notes documenting the earlier treatments that didn't work for me",
        ],
    ),
    EvidenceItem(
        id="diagnostic_test_results",
        name="Diagnostic test results",
        description="Imaging, lab, monitoring or other test results supporting the diagnosis.",
        member_phrases=[
            "my test results",
            "copies of my lab and test results",
        ],
    ),
    EvidenceItem(
        id="clinical_guidelines",
        name="Clinical guidelines or published studies",
        description="Published clinical guidelines or peer-reviewed studies supporting "
        "the treatment.",
        member_phrases=[
            "a printout of the medical guidelines my doctor follows for this",
            "some published studies my doctor gave me about this treatment",
        ],
    ),
    EvidenceItem(
        id="ordering_physician_order",
        name="Physician's order for the service",
        description="The treating provider's order documenting the service and why it was ordered.",
        member_phrases=[
            "the written order my doctor gave me for this",
            "my doctor's order form",
        ],
    ),
    EvidenceItem(
        id="prior_auth_request_record",
        name="Prior authorization request record",
        description="Proof that a prior authorization request was submitted or approved "
        "(confirmation, reference number, fax receipt).",
        member_phrases=[
            "the confirmation my doctor's office got when they sent the authorization request",
            "the reference number from the authorization request",
        ],
    ),
    EvidenceItem(
        id="urgency_documentation",
        name="Documentation of urgency",
        description="Records showing the service was urgent and could not wait for prior "
        "authorization.",
        member_phrases=[
            "a note from my doctor explaining why it couldn't wait",
            "my doctor's note saying it was urgent",
        ],
    ),
    EvidenceItem(
        id="emergency_records",
        name="Emergency or urgent care records",
        description="Emergency department or urgent care records showing the condition "
        "that was treated.",
        member_phrases=[
            "the discharge paperwork from that visit",
            "the records from the emergency room or urgent care",
        ],
    ),
    EvidenceItem(
        id="pcp_referral",
        name="Primary care referral",
        description="A referral from the member's primary care physician.",
        member_phrases=[
            "the referral from my primary care doctor",
            "my PCP's referral",
        ],
    ),
    EvidenceItem(
        id="network_status_proof",
        name="Proof of provider network status",
        description="A provider directory listing or plan confirmation showing the "
        "provider's network status when care was scheduled or received.",
        member_phrases=[
            "a screenshot of the plan's online provider directory listing for that provider",
            "a printout from the insurer's website listing the provider as in-network",
        ],
    ),
    EvidenceItem(
        id="network_adequacy_evidence",
        name="Evidence no network provider was available",
        description="Documentation that no network provider could provide the service "
        "within the plan's access standards (distance or wait time).",
        member_phrases=[
            "my notes from calling every in-network provider on the list",
            "a list of the in-network offices I called and what they told me",
        ],
    ),
    EvidenceItem(
        id="eob",
        name="Explanation of Benefits",
        description="The plan's Explanation of Benefits statement for the claim.",
        member_phrases=[
            "the Explanation of Benefits statement",
            "my EOB from the insurance company",
        ],
    ),
    EvidenceItem(
        id="itemized_bill",
        name="Itemized bill",
        description="The provider's itemized bill listing each billed code and charge.",
        member_phrases=[
            "the itemized bill from the provider",
            "an itemized statement listing every charge",
        ],
    ),
    EvidenceItem(
        id="corrected_claim",
        name="Corrected claim",
        description="The provider's corrected claim with fixed codes, modifiers or units.",
        member_phrases=[
            "a copy of the corrected claim the billing office resubmitted",
            "the corrected claim form from the provider",
        ],
    ),
    EvidenceItem(
        id="provider_coding_letter",
        name="Letter from the provider's billing office",
        description="A letter from the provider's billing office explaining the codes used "
        "and any correction.",
        member_phrases=[
            "a letter from the billing office explaining the codes they used",
            "an email from the provider's billing department about the coding",
        ],
    ),
]

EVIDENCE_BY_ID: dict[str, EvidenceItem] = {e.id: e for e in EVIDENCE}


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
