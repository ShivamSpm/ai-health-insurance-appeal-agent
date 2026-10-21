"""Plan document sections and BM25 search over them.

Plans are Markdown with `<!-- page N -->` markers and `### N.N Title` sections.
Each section becomes one chunk with a stable ID like `ppo-6.4`.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

PAGE_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
SECTION_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+)$")
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
STOPWORDS = set(
    "a an and are as at be by for from has have if in is it its of on or that the this "
    "to was were will with you your we our not may any".split()
)


@dataclass(frozen=True)
class Section:
    chunk_id: str
    number: str
    title: str
    page: int
    text: str

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "page": self.page,
            "text": self.text,
        }


def parse_plan(markdown: str, plan_id: str) -> list[Section]:
    sections: list[Section] = []
    page, current, lines = 0, None, []

    def flush():
        if current:
            number, title, sec_page = current
            sections.append(
                Section(f"{plan_id}-{number}", number, title, sec_page, "\n".join(lines).strip())
            )

    for line in markdown.splitlines():
        if m := PAGE_RE.match(line.strip()):
            page = int(m.group(1))
        elif m := SECTION_RE.match(line):
            flush()
            current, lines = (m.group(1), m.group(2).strip(), page), []
        elif line.startswith("## ") or line.startswith("# "):
            flush()
            current, lines = None, []
        elif current:
            lines.append(line)
    flush()
    return sections


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class PolicyIndex:
    """Okapi BM25 over plan sections. Title and section number are indexed with the text."""

    def __init__(self, sections: list[Section], k1: float = 1.5, b: float = 0.75):
        self.sections = sections
        self.by_id = {s.chunk_id: s for s in sections}
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(f"{s.number} {s.title} {s.text}")) for s in sections]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths)
        df = Counter(term for d in self.docs for term in d)
        n = len(sections)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int) -> list[Section]:
        terms = tokenize(query)
        scored = []
        for i, doc in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
            score = sum(
                self.idf[t] * doc[t] * (self.k1 + 1) / (doc[t] + norm) for t in terms if t in doc
            )
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [self.sections[i] for _, i in scored[:k]]

    def get(self, chunk_id: str) -> Section | None:
        return self.by_id.get(chunk_id.strip().lower())
