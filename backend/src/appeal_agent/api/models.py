"""Request and response models. The frontend's TypeScript types are generated from these.

Responses never include eval labels: the workspace shows what the agent saw and did.
"""

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from appeal_agent.agent.outputs import Findings

PlanId = Literal["ppo", "hmo", "epo"]
RunStatus = Literal["running", "completed", "failed", "step_limit", "error"]


class PlanSection(BaseModel):
    chunk_id: str
    number: str
    title: str
    page: int
    text: str


class CaseSummary(BaseModel):
    case_id: str
    source: Literal["dataset", "user"]
    plan_id: str
    plan_name: str
    title: str
    run_count: int
    latest_status: RunStatus | None


class CaseDetail(BaseModel):
    case_id: str
    source: Literal["dataset", "user"]
    plan_id: str
    plan_name: str
    title: str
    denial_letter: str
    member_note: str
    plan_sections: list[PlanSection]


class NewCase(BaseModel):
    plan_id: PlanId
    denial_letter: str = Field(min_length=50, max_length=20_000)
    member_note: str = Field(default="", max_length=5_000)
    title: str | None = Field(default=None, max_length=120)


class ModelOption(BaseModel):
    id: str
    role: Literal["agent", "agent_cheap"]
    priced: bool


class StartRun(BaseModel):
    model: str | None = Field(
        default=None, description="Model ID; default is the main agent model."
    )


class RunSummary(BaseModel):
    id: str
    case_id: str
    model: str
    status: RunStatus
    error: str | None
    started_at: str
    finished_at: str | None
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost_usd: float | None
    latency_ms: int
    loaded_skills: list[str]
    retrieved: list[str]
    findings: Findings | None
    letter: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "RunSummary":
        return cls(
            **{
                k: row[k]
                for k in cls.model_fields
                if k not in ("findings", "loaded_skills", "retrieved")
            },
            loaded_skills=json.loads(row["loaded_skills"] or "[]"),
            retrieved=json.loads(row["retrieved"] or "[]"),
            findings=Findings.model_validate_json(row["findings"]) if row["findings"] else None,
        )


class Step(BaseModel):
    idx: int
    kind: Literal["llm", "tool"]
    name: str | None
    input: str | None
    output: str | None
    reasoning: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    invalid: bool
    started_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Step":
        return cls(**{k: row[k] for k in cls.model_fields})


class RunDetail(RunSummary):
    steps: list[Step]


class DraftVersion(BaseModel):
    version: int = Field(description="0 is the agent's letter; 1, 2, ... are saved edits.")
    source: Literal["agent", "user"]
    text: str
    created_at: str | None


class NewDraft(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
