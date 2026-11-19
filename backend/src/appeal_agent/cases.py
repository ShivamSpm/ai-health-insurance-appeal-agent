"""Case inputs: the 40 dataset cases, plus cases created in the UI.

A user case is a pasted denial letter and member note against one of the
existing plans. It is stored as files, like a dataset case, but in a
gitignored folder, and it has no labels.
"""

import json
import os
import re
import uuid
from pathlib import Path

from appeal_agent.config import DATA_DIR, REPO_ROOT, settings
from appeal_agent.domain import CaseInputs

DATASET_ID_RE = re.compile(r"^case-\d{3}$")
USER_ID_RE = re.compile(r"^user-[0-9a-f]{8}$")
SERVICE_RE = re.compile(r"^\|\s*Service\s*\|\s*(.+?)\s*\|\s*$", re.M)


class UnknownCase(LookupError):
    pass


def user_cases_dir() -> Path:
    """Overridable with APPEAL_USER_CASES_DIR (tests use a temporary folder)."""
    override = os.environ.get("APPEAL_USER_CASES_DIR")
    return Path(override) if override else REPO_ROOT / settings()["storage"]["user_cases_dir"]


def dataset_case_ids() -> list[str]:
    return sorted(p.name for p in (DATA_DIR / "cases").iterdir() if DATASET_ID_RE.match(p.name))


def user_case_ids() -> list[str]:
    root = user_cases_dir()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if USER_ID_RE.match(p.name))


def source(case_id: str) -> str:
    return "user" if USER_ID_RE.match(case_id) else "dataset"


def load_case(case_id: str) -> CaseInputs:
    """The agent's inputs for a case. Paths are relative to DATA_DIR, or absolute."""
    if DATASET_ID_RE.match(case_id):
        path = DATA_DIR / "cases" / case_id / "case.json"
        if path.exists():
            return CaseInputs.model_validate_json(path.read_text(encoding="utf-8"))
    elif USER_ID_RE.match(case_id):
        folder = user_cases_dir() / case_id
        meta_path = folder / "case.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return CaseInputs(
                case_id=case_id,
                plan_id=meta["plan_id"],
                plan_file=f"plans/{meta['plan_id']}.md",
                denial_letter_file=str(folder / "denial_letter.md"),
                member_note_file=str(folder / "member_note.md"),
            )
    raise UnknownCase(case_id)


def read_inputs(case: CaseInputs) -> tuple[str, str, str]:
    """(denial letter, member note, plan Markdown)."""
    return tuple(  # type: ignore[return-value]
        (DATA_DIR / f).read_text(encoding="utf-8")
        for f in (case.denial_letter_file, case.member_note_file, case.plan_file)
    )


def title(case_id: str, denial_letter: str) -> str:
    """A short label for the inbox: the user's title, the letter's Service row, or its start."""
    if USER_ID_RE.match(case_id):
        meta = json.loads((user_cases_dir() / case_id / "case.json").read_text(encoding="utf-8"))
        if meta.get("title"):
            return meta["title"]
    if m := SERVICE_RE.search(denial_letter):
        return m.group(1)
    first = next((ln.strip(" #*") for ln in denial_letter.splitlines() if ln.strip()), "")
    return first[:80] or case_id


def create_user_case(plan_id: str, denial_letter: str, member_note: str, title: str | None) -> str:
    case_id = f"user-{uuid.uuid4().hex[:8]}"
    folder = user_cases_dir() / case_id
    folder.mkdir(parents=True)
    for name, text in [("denial_letter.md", denial_letter), ("member_note.md", member_note)]:
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    meta = {"plan_id": plan_id, "title": (title or "").strip() or None}
    (folder / "case.json").write_text(json.dumps(meta, indent=2), encoding="utf-8", newline="\n")
    return case_id
