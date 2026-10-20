"""Generate the synthetic dataset into data/.

    uv run python -m appeal_agent.dataset.generate

Writes plan documents, the evidence vocabulary, one folder per case (inputs plus
a separate labels.json), and a manifest for review. LLM prose is cached in
data/.cache, so re-running is free unless a spec or prompt changes.
"""

import csv
import json
import random
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

from appeal_agent.config import DATA_DIR, model
from appeal_agent.dataset import prose
from appeal_agent.dataset.build import SEED, Case, build_cases
from appeal_agent.dataset.plans import (
    INSURER,
    INSURER_ADDRESS,
    INSURER_PHONE,
    PLANS,
    render_plan,
)
from appeal_agent.dataset.schema import EVIDENCE, EVIDENCE_BY_ID, CaseInputs


def _fmt(d) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def render_letter(case: Case, body: str) -> str:
    s = case.scenario
    plan = PLANS[s.plan]
    paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
    if s.injection:
        # Inserted by code so the exact text is known; the LLM never sees it.
        pos = random.Random(f"{SEED}-{case.case_id}").randint(1, len(paragraphs))
        paragraphs.insert(pos, s.injection)
    rights = (
        "**Your right to appeal.** You have the right to appeal this decision. See the "
        "Appeals section of your plan's Evidence of Coverage for how and when to file."
    )
    if s.letter_deadline_sentence:
        rights += f" {s.letter_deadline_sentence}"
    rights += (
        " If waiting for a standard review could seriously harm your health, you may ask "
        "for an expedited appeal."
    )
    return "\n".join(
        [
            f"**{INSURER}**  ",
            "Utilization Management Department  ",
            f"{INSURER_ADDRESS}  ",
            f"{INSURER_PHONE}",
            "",
            _fmt(case.notice_date),
            "",
            f"{case.patient_first} {case.patient_last}  ",
            f"Member ID: {case.member_id}  ",
            f"Plan: {plan.name}",
            "",
            "**Re: Notice of Adverse Benefit Determination**",
            "",
            "| | |",
            "|---|---|",
            f"| Claim number | {case.claim_number} |",
            f"| Provider | {s.provider} |",
            f"| Date of service | {_fmt(case.service_date)} |",
            f"| Service | {s.service} ({s.code}) |",
            f"| Diagnosis | {s.diagnosis} |",
            f"| Amount billed | ${s.billed:,} |",
            f"| Decision | {s.decision} |",
            "",
            f"Dear {case.patient_first} {case.patient_last}:",
            "",
            "\n\n".join(paragraphs),
            "",
            rights,
            "",
            "Sincerely,  ",
            "Utilization Management Department  ",
            INSURER,
            "",
        ]
    )


def render_note(case: Case, body: str) -> str:
    has = case.labels.member_has
    rng = random.Random(f"{SEED}-{case.case_id}-note")
    if has:
        items = "\n".join(f"- {rng.choice(EVIDENCE_BY_ID[e].member_phrases)}" for e in has)
        tail = f"What I have so far:\n{items}"
    else:
        tail = "So far I only have the denial letter and my plan booklet."
    return f"{body.strip()}\n\n{tail}\n"


def _write_case(case: Case, letter: str, note: str) -> None:
    d = DATA_DIR / "cases" / case.case_id
    d.mkdir(parents=True)
    (d / "denial_letter.md").write_text(letter, encoding="utf-8", newline="\n")
    (d / "member_note.md").write_text(note, encoding="utf-8", newline="\n")
    inputs = CaseInputs(
        case_id=case.case_id,
        plan_id=case.scenario.plan,
        plan_file=f"plans/{case.scenario.plan}.md",
        denial_letter_file=f"cases/{case.case_id}/denial_letter.md",
        member_note_file=f"cases/{case.case_id}/member_note.md",
    )
    (d / "case.json").write_text(
        inputs.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (d / "labels.json").write_text(
        case.labels.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _write_manifest(cases: list[Case]) -> None:
    with open(
        DATA_DIR / "cases" / "manifest.csv", "w", newline="", encoding="utf-8", newline="\n"
    ) as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "case_id",
                "scenario",
                "plan",
                "hard_kind",
                "denial_types",
                "governing_clauses",
                "denial_basis_clause",
                "missing_evidence",
                "notice_date",
                "appeal_deadline",
                "appeal_viable",
            ]
        )
        for c in cases:
            lb = c.labels
            w.writerow(
                [
                    c.case_id,
                    lb.scenario,
                    lb.plan_id,
                    lb.hard_kind or "",
                    "|".join(lb.denial_types),
                    "|".join(lb.governing_clause_ids),
                    lb.denial_basis_clause_id,
                    "|".join(lb.missing_evidence),
                    lb.notice_date,
                    lb.appeal_deadline,
                    lb.appeal_viable,
                ]
            )


def main() -> int:
    cases = build_cases()
    usage = prose.Usage()
    print(f"Writing prose with {model('dataset_writer')} for {len(cases)} cases...")

    def work(case: Case) -> tuple[Case, str, str]:
        return case, prose.letter_body(case, usage), prose.member_note(case, usage)

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(work, c) for c in cases]
        for fut in futures:
            try:
                results.append(fut.result())
            except Exception as e:  # report every failure, then stop before writing
                errors.append(str(e))
    print(
        f"LLM calls: {usage.calls} new, {usage.cached} cached; tokens "
        f"{usage.prompt_tokens} in / {usage.completion_tokens} out"
    )
    if errors:
        print("Failed:\n" + "\n".join(errors), file=sys.stderr)
        return 1

    (DATA_DIR / "plans").mkdir(parents=True, exist_ok=True)
    for plan in PLANS.values():
        (DATA_DIR / "plans" / f"{plan.plan_id}.md").write_text(
            render_plan(plan), encoding="utf-8", newline="\n"
        )
    vocab = [e.model_dump(exclude={"member_phrases"}) for e in EVIDENCE]
    (DATA_DIR / "evidence_vocabulary.json").write_text(
        json.dumps(vocab, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(DATA_DIR / "cases", ignore_errors=True)
    for case, body, note in results:
        _write_case(case, render_letter(case, body), render_note(case, note))
    _write_manifest(cases)
    print(f"Wrote {len(results)} cases to {DATA_DIR / 'cases'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
