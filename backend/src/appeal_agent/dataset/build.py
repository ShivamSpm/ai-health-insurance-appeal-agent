"""Turn scenarios into concrete cases: names, dates, IDs and labels.

Everything here is deterministic given the seed, so labels can be rebuilt and
tested without calling an LLM.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from appeal_agent.dataset.plans import PLANS
from appeal_agent.dataset.scenarios import SCENARIOS, Scenario
from appeal_agent.dataset.schema import EVIDENCE, SKILL_FOR_TYPE, CaseLabels

SEED = 20261020

FIRST_NAMES = """
    Maria James Aisha Wei Daniel Fatima Carlos Emily Kwame Sofia Raj Olivia Tomas Mei
    Jamal Hannah Luis Grace Ivan Nadia Ethan Leila Marcus Yuki Patrick Zara Diego Ruth
    Andre Priyanka Samuel Elena Hector Chloe Tariq Megan Noah Amara Viktor Rosa
""".split()
LAST_NAMES = """
    Alvarez Brennan Chen Dubois Eze Fitzgerald Gupta Haddad Ivanova Jensen Kim Lindgren
    Mbeki Novak O'Connell Petrov Quintero Rahman Sato Thompson Usman Vargas Whitfield
    Xu Yilmaz Zielinski Abernathy Bose Castellanos Delgado Ekwueme Foster Gallagher
    Hoang Iqbal Juarez Kowalczyk Larsen Mendoza Nakashima
""".split()


@dataclass(frozen=True)
class Case:
    case_id: str
    scenario: Scenario
    patient_first: str
    patient_last: str
    member_id: str
    claim_number: str
    service_date: date
    notice_date: date
    cites_section: bool
    labels: CaseLabels


def _weekday_between(rng: random.Random, start: date, end: date) -> date:
    while True:
        d = start + timedelta(days=rng.randint(0, (end - start).days))
        if d.weekday() < 5:
            return d


def _required(s: Scenario) -> list[str]:
    plan = PLANS[s.plan]
    ids = {e for t in s.denial_types for e in plan.requirements[t]} | set(s.extra_required)
    return [e.id for e in EVIDENCE if e.id in ids]  # vocabulary order, for stable output


def _member_has(rng: random.Random, s: Scenario, required: list[str]) -> list[str]:
    if s.has is not None:
        return list(s.has)
    # Keep at least one item missing, and sometimes add an unrelated item the member has.
    # Unrelated means no plan asks for it for these denial types, so it can't hint at
    # the answer (e.g. a corrected claim in an ambiguous coding-or-network case).
    has = set(rng.sample(required, rng.randint(0, len(required) - 1)))
    if rng.random() < 0.4:
        related = {e for p in PLANS.values() for t in s.denial_types for e in p.requirements[t]}
        unrelated = [e.id for e in EVIDENCE if e.id not in related | set(required)]
        has.add(rng.choice(unrelated))
    return [e.id for e in EVIDENCE if e.id in has]


def build_cases(seed: int = SEED) -> list[Case]:
    rng = random.Random(seed)
    scenarios = list(SCENARIOS)
    rng.shuffle(scenarios)  # so case IDs don't reveal the case type
    first_names = rng.sample(FIRST_NAMES, len(scenarios))
    last_names = rng.sample(LAST_NAMES, len(scenarios))

    cases = []
    for i, s in enumerate(scenarios):
        case_id = f"case-{i + 1:03d}"
        plan = PLANS[s.plan]
        notice_date = _weekday_between(rng, date(2026, 7, 1), date(2026, 10, 9))
        service_date = notice_date - timedelta(days=rng.randint(12, 45))
        deadline, rule = plan.appeal_deadline(notice_date)
        required = _required(s)
        has = _member_has(rng, s, required)
        cites = s.cites_section if s.cites_section is not None else rng.random() < 0.5
        labels = CaseLabels(
            case_id=case_id,
            scenario=s.key,
            plan_id=s.plan,
            hard_kind=s.hard_kind,
            denial_types=s.denial_types,
            ambiguous=len(s.denial_types) > 1,
            expected_skills=[SKILL_FOR_TYPE[t] for t in s.denial_types],
            governing_clause_ids=[plan.clause_id(c) for c in s.clauses],
            denial_basis_clause_id=plan.clause_id(s.denial_basis_clause),
            required_evidence=required,
            member_has=has,
            missing_evidence=[e for e in required if e not in has],
            notice_date=notice_date,
            appeal_deadline=deadline,
            deadline_rule=rule,
            appeal_viable=s.viable,
            contradiction=s.contradiction,
            injection=s.injection,
            notes=s.notes,
        )
        cases.append(
            Case(
                case_id=case_id,
                scenario=s,
                patient_first=first_names[i],
                patient_last=last_names[i],
                member_id=f"HRH{rng.randint(100000000, 999999999)}",
                claim_number=f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}",
                service_date=service_date,
                notice_date=notice_date,
                cites_section=cites,
                labels=labels,
            )
        )
    return cases
