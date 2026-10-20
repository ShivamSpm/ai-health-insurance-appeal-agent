"""LLM-written prose for denial letters and member notes, with validation.

The LLM writes only free text. Code checks that the text says what the spec
requires and nothing that would change a label (dates, deadlines, extra
documents). Failed checks are fed back to the model for a retry.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field

from appeal_agent.config import DATA_DIR, model
from appeal_agent.dataset.build import Case
from appeal_agent.dataset.plans import INSURER, PLANS
from appeal_agent.llm import client

CACHE_DIR = DATA_DIR / ".cache" / "prose"
MAX_ATTEMPTS = 4
TEMPERATURE = 0.9

SYSTEM = (
    "You write realistic synthetic documents for a software test dataset. All people, "
    "providers and companies are fictional. Output only the requested text: no preamble, "
    "no headings, no Markdown formatting, no placeholders in brackets."
)

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_PATTERNS = [
    rf"\b({MONTHS})\b",
    r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b",
    r"\b20\d{2}\b",
]


@dataclass
class Usage:
    calls: int = 0
    cached: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    failures: list[str] = field(default_factory=list)


def _complete(messages: list[dict], usage: Usage) -> str:
    payload = {"model": model("dataset_writer"), "messages": messages, "t": TEMPERATURE}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        usage.cached += 1
        return json.loads(path.read_text(encoding="utf-8"))["content"]
    resp = client().chat.completions.create(
        model=payload["model"], messages=messages, temperature=TEMPERATURE, max_tokens=1500
    )
    content = (resp.choices[0].message.content or "").strip()
    usage.calls += 1
    if resp.usage:
        usage.prompt_tokens += resp.usage.prompt_tokens
        usage.completion_tokens += resp.usage.completion_tokens
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"content": content}), encoding="utf-8")
    return content


def _generate(prompt: str, validate, usage: Usage, label: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    for _ in range(MAX_ATTEMPTS):
        text = _complete(messages, usage)
        problems = validate(text)
        if not problems:
            return text
        messages = messages + [
            {"role": "assistant", "content": text},
            {
                "role": "user",
                "content": "Rewrite it to fix these problems:\n- " + "\n- ".join(problems),
            },
        ]
    usage.failures.append(f"{label}: {problems}")
    raise ValueError(f"{label} failed validation after {MAX_ATTEMPTS} attempts: {problems}")


def _word_count(text: str) -> int:
    return len(text.split())


def _common_problems(text: str, lo: int, hi: int) -> list[str]:
    problems = []
    n = _word_count(text)
    if not lo <= n <= hi:
        problems.append(f"Length must be {lo}-{hi} words; it is {n}.")
    if any(re.search(p, text) for p in DATE_PATTERNS):
        problems.append("Remove all dates, months and years.")
    if re.search(r"[\[\]{}]", text):
        problems.append("Remove bracketed placeholders.")
    if re.search(r"^\s*#|\*\*", text, re.M):
        problems.append("Use plain prose with no Markdown.")
    return problems


def letter_body(case: Case, usage: Usage) -> str:
    s = case.scenario
    plan = PLANS[s.plan]
    section = s.denial_basis_clause
    cite_rule = (
        f"Refer to Section {section} of the member's plan as the basis for the decision."
        if case.cites_section
        else "Do not mention any section numbers of the plan."
    )
    prompt = f"""Write the body of a health insurance denial letter (a notice of adverse benefit determination) from {INSURER} to a member of the {plan.name}.

Facts:
- Service: {s.service} ({s.code})
- Provider: {s.provider}
- Decision: {s.decision}
- Reason for the decision: {s.reason}

Requirements:
- 2 to 4 short paragraphs, 90 to 220 words, in a formal insurer tone.
- State the reason faithfully. Do not add other reasons, and do not soften or change it.
- {cite_rule}
- Do not include a greeting, sign-off, letterhead or signature.
- Do not include any dates, deadlines, numbers of days, or appeal instructions, and do not use the word "appeal". Those are added separately."""

    def validate(text: str) -> list[str]:
        problems = _common_problems(text, 80, 260)
        low = text.lower()
        for group in s.must_mention:
            if not any(phrase in low for phrase in group):
                problems.append(f"Mention {' or '.join(repr(p) for p in group)}.")
        if re.search(r"\bappeal", low):
            problems.append('Do not use the word "appeal".')
        if re.search(r"\b\d+\s+(calendar\s+|business\s+)?days?\b", low):
            problems.append("Do not mention numbers of days.")
        if re.search(r"^\s*(dear|sincerely)\b", low, re.M):
            problems.append("Remove the greeting or sign-off.")
        cited = re.findall(r"\bsection\s+(\d+(?:\.\d+)?)", low)
        if case.cites_section and section not in cited:
            problems.append(f"Refer to Section {section} of the plan.")
        if not case.cites_section and cited:
            problems.append("Do not mention section numbers.")
        if case.cites_section and any(c != section for c in cited):
            problems.append(f"Refer only to Section {section}, no other sections.")
        return problems

    return _generate(prompt, validate, usage, f"{case.case_id} letter")


NOTE_BANNED = re.compile(
    r"\b(documents?|paperwork|screenshots?|records?|bills?|billing|EOB|explanation of "
    r"benefits|cop(y|ies)|printouts?|receipts?|letters?|referrals?|orders?|notes?|"
    r"forms?|statements?|deadlines?)\b",
    re.I,
)


def member_note(case: Case, usage: Usage) -> str:
    s = case.scenario
    prompt = f"""Write a short note in the first person from {case.patient_first}, a member of a health plan whose claim was denied. They are writing it for an assistant that will help them appeal.

What happened: {s.story}
The denied service: {s.service}

Requirements:
- 50 to 120 words, plain and conversational, like a real person typing quickly.
- Describe the situation and how they feel about the denial.
- Do not mention any documents, records, bills, letters, referrals, forms or paperwork they have or could get. That list is added separately.
- Do not mention any dates, months, years or deadlines."""

    def validate(text: str) -> list[str]:
        problems = _common_problems(text, 40, 150)
        banned = sorted({m.group(0).lower() for m in NOTE_BANNED.finditer(text)})
        if banned:
            problems.append(f"Do not use these words: {', '.join(banned)}.")
        return problems

    return _generate(prompt, validate, usage, f"{case.case_id} note")
