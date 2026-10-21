"""Skill discovery and loading (agentskills.io format).

Level 1: name + description, listed in the system prompt.
Level 2: the full SKILL.md, returned by load_skill.
Level 3: files under the skill folder, returned by read_skill_file.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from appeal_agent.config import REPO_ROOT

SKILLS_DIR = REPO_ROOT / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path

    def body(self) -> str:
        return _split_frontmatter((self.path / "SKILL.md").read_text(encoding="utf-8"))[1]

    def files(self) -> list[str]:
        return sorted(
            p.relative_to(self.path).as_posix()
            for p in self.path.rglob("*")
            if p.is_file() and p.name != "SKILL.md"
        )

    def read_file(self, rel_path: str) -> str | None:
        """Contents of a file inside the skill folder, or None if outside or missing."""
        target = (self.path / rel_path).resolve()
        if not target.is_relative_to(self.path.resolve()) or not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for p in sorted(self.path.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(self.path).as_posix().encode())
                h.update(p.read_bytes())
        return h.hexdigest()[:12]


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body.strip()


def load_skills(skills_dir: Path = SKILLS_DIR) -> dict[str, Skill]:
    skills = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        meta, _ = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
        if meta["name"] != skill_md.parent.name:
            raise ValueError(f"{skill_md}: name {meta['name']!r} must match its folder")
        skills[meta["name"]] = Skill(meta["name"], meta["description"], skill_md.parent)
    return skills
