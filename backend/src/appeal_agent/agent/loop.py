"""The agent loop: call the model, run the tools it asks for, repeat until done.

Guardrails:
- Step limit: at most `max_steps` LLM calls per run.
- Retries: a turn with malformed or invalid tool calls (or no tool call at all)
  uses one retry; a clean turn resets the budget. Exceeding it fails the run.
- Citations: enforced by the submit tools (only retrieved sections).
- Documents are returned wrapped as untrusted data (see tools.py).
Every LLM call and tool call is stored as a step with tokens, latency and cost.
"""

import hashlib
import json
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from appeal_agent.agent.outputs import Findings
from appeal_agent.agent.prompts import SYSTEM_PROMPT, TASK_PROMPT, system_prompt
from appeal_agent.agent.skills import load_skills
from appeal_agent.agent.tools import TOOL_SPECS, CaseSession
from appeal_agent.config import DATA_DIR, REPO_ROOT, model, settings
from appeal_agent.domain import CaseInputs
from appeal_agent.llm import client
from appeal_agent.pricing import cost_usd
from appeal_agent.store import Store


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMReply:
    content: str | None
    tool_calls: list[ToolCall]
    reasoning: str | None
    finish_reason: str | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


Complete = Callable[[str, list[dict], list[dict], dict], LLMReply]


def openai_complete(model_id: str, messages: list[dict], tools: list[dict], cfg: dict) -> LLMReply:
    resp = client().chat.completions.create(
        model=model_id,
        messages=messages,
        tools=tools,
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
    choice = resp.choices[0]
    msg = choice.message
    usage = resp.usage
    details = getattr(usage, "prompt_tokens_details", None)
    extra = msg.model_extra or {}
    return LLMReply(
        content=msg.content,
        tool_calls=[
            ToolCall(tc.id, tc.function.name, tc.function.arguments or "{}")
            for tc in msg.tool_calls or []
        ],
        reasoning=extra.get("reasoning_content") or extra.get("reasoning"),
        finish_reason=choice.finish_reason,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        cached_tokens=(getattr(details, "cached_tokens", None) or 0) if details else 0,
    )


@dataclass
class RunResult:
    run_id: str
    case_id: str
    model: str
    status: str
    error: str | None = None
    findings: Findings | None = None
    letter: str | None = None
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = 0.0
    latency_ms: int = 0
    loaded_skills: list[str] = field(default_factory=list)


def _git_sha() -> str | None:
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return git("rev-parse", "--short", "HEAD") + (
            "-dirty" if git("status", "--porcelain") else ""
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def prompt_hash() -> str:
    material = SYSTEM_PROMPT + TASK_PROMPT + json.dumps(TOOL_SPECS, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:12]


def load_case(case_id: str) -> CaseInputs:
    path = DATA_DIR / "cases" / case_id / "case.json"
    return CaseInputs.model_validate_json(path.read_text(encoding="utf-8"))


def run_case(
    case_id: str,
    model_id: str | None = None,
    store: Store | None = None,
    complete: Complete = openai_complete,
) -> RunResult:
    cfg = settings()["agent"]
    model_id = model_id or model("agent")
    store = store or Store()
    skills = load_skills()
    session = CaseSession(load_case(case_id), skills, cfg["search_top_k"])
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{case_id}-{uuid.uuid4().hex[:4]}"
    result = RunResult(run_id, case_id, model_id, status="running")
    store.start_run(
        run_id,
        case_id,
        model_id,
        prompt_hash=prompt_hash(),
        git_sha=_git_sha(),
        skill_hashes={name: s.content_hash() for name, s in skills.items()},
        settings=cfg,
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt(skills)},
        {"role": "user", "content": TASK_PROMPT.format(case_id=case_id)},
    ]
    step_idx = 0
    retries_left = cfg["max_retries"]

    def use_retry(reason: str) -> bool:
        nonlocal retries_left
        retries_left -= 1
        if retries_left < 0:
            result.status, result.error = "failed", reason
            return False
        return True

    try:
        while not session.done:
            if result.llm_calls >= cfg["max_steps"]:
                result.status, result.error = "step_limit", f"reached {cfg['max_steps']} LLM calls"
                break
            t0 = time.perf_counter()
            reply = complete(model_id, messages, TOOL_SPECS, cfg)
            latency = int((time.perf_counter() - t0) * 1000)
            cost = cost_usd(
                model_id, reply.prompt_tokens, reply.completion_tokens, reply.cached_tokens
            )
            result.llm_calls += 1
            result.prompt_tokens += reply.prompt_tokens
            result.completion_tokens += reply.completion_tokens
            result.cached_tokens += reply.cached_tokens
            result.latency_ms += latency
            result.cost_usd = (
                None if cost is None or result.cost_usd is None else (result.cost_usd + cost)
            )
            step_idx += 1
            store.add_step(
                run_id,
                step_idx,
                "llm",
                name=model_id,
                output=json.dumps(
                    {
                        "content": reply.content,
                        "finish_reason": reply.finish_reason,
                        "tool_calls": [tc.__dict__ for tc in reply.tool_calls],
                    }
                ),
                reasoning=reply.reasoning,
                prompt_tokens=reply.prompt_tokens,
                completion_tokens=reply.completion_tokens,
                cached_tokens=reply.cached_tokens,
                cost_usd=cost,
                latency_ms=latency,
            )

            assistant: dict = {"role": "assistant", "content": reply.content or ""}
            if reply.tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in reply.tool_calls
                ]
            messages.append(assistant)

            if not reply.tool_calls:
                if not use_retry("model stopped without submitting its work"):
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Continue using tools. Finish by calling submit_findings, then "
                            "submit_appeal_letter if the appeal is viable."
                        ),
                    }
                )
                continue

            turn_invalid = reply.finish_reason == "length"
            for tc in reply.tool_calls:
                t0 = time.perf_counter()
                try:
                    args = json.loads(tc.arguments)
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                except ValueError as e:
                    content, invalid = f"Error: arguments are not valid JSON ({e}).", True
                else:
                    out = session.call(tc.name, args)
                    content, invalid = out.content, out.invalid
                step_idx += 1
                store.add_step(
                    run_id,
                    step_idx,
                    "tool",
                    name=tc.name,
                    input=tc.arguments,
                    output=content,
                    invalid=int(invalid),
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
                turn_invalid |= invalid

            if turn_invalid:
                if not use_retry("too many malformed or invalid tool calls"):
                    break
            else:
                retries_left = cfg["max_retries"]
        else:
            result.status = "completed"
    except Exception as e:  # record provider/network errors on the run, then re-raise
        result.status, result.error = "error", f"{type(e).__name__}: {e}"
        raise
    finally:
        result.findings, result.letter = session.findings, session.letter
        result.loaded_skills = session.loaded_skills
        store.finish_run(
            run_id,
            status=result.status,
            error=result.error,
            llm_calls=result.llm_calls,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cached_tokens=result.cached_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            loaded_skills=json.dumps(session.loaded_skills),
            retrieved=json.dumps(sorted(session.retrieved)),
            findings=session.findings.model_dump_json() if session.findings else None,
            letter=session.letter,
        )
    return result
