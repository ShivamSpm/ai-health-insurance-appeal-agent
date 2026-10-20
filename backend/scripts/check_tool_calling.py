"""Smoke-test tool calling on candidate models.

Two turns: the model must call search_policy, then, given the result, call
submit_findings with a nested schema. Run from backend/:

    uv run python scripts/check_tool_calling.py [model_id ...]
"""

import json
import sys
import time

from appeal_agent.llm import client

DEFAULT_MODELS = [
    "deepseek-ai/DeepSeek-V4-Pro",
    "deepseek-ai/DeepSeek-V4.1-Flash",
    "openai/gpt-oss-120b",
    "zai-org/GLM-5.3",
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search the plan document. Returns matching sections with chunk IDs.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_findings",
            "description": "Submit final structured findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "denial_type": {
                        "type": "string",
                        "enum": [
                            "medical_necessity",
                            "prior_authorization",
                            "out_of_network",
                            "coding_error",
                        ],
                    },
                    "governing_clause_ids": {"type": "array", "items": {"type": "string"}},
                    "missing_evidence": {"type": "array", "items": {"type": "string"}},
                    "appeal_deadline": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": [
                    "denial_type",
                    "governing_clause_ids",
                    "missing_evidence",
                    "appeal_deadline",
                ],
            },
        },
    },
]

SYSTEM = (
    "You analyze health insurance denials. Use search_policy to find the governing clause, "
    "then call submit_findings. Only cite chunk IDs returned by search_policy."
)
USER = (
    "Denial letter dated 2026-03-02: 'Claim for lumbar MRI denied: no prior authorization "
    "was obtained before the service.' Find the governing clause and submit findings."
)
TOOL_RESULT = json.dumps(
    [
        {
            "chunk_id": "plan-4.2",
            "page": 12,
            "text": "4.2 Prior Authorization. Advanced imaging (MRI, CT, PET) requires prior authorization. "
            "Members may appeal within 180 days of the denial notice. Appeals must include the "
            "ordering physician's notes and the date of service.",
        }
    ]
)
EXPECTED = {
    "denial_type": "prior_authorization",
    "governing_clause_ids": ["plan-4.2"],
    "appeal_deadline": "2026-08-29",
}


def check(model: str) -> dict:
    out: dict = {"model": model}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    t = time.time()
    r1 = client().chat.completions.create(model=model, messages=msgs, tools=TOOLS, max_tokens=2000)
    out["turn1_s"] = round(time.time() - t, 1)
    m1 = r1.choices[0].message
    calls = m1.tool_calls or []
    out["turn1_calls"] = [c.function.name for c in calls]
    if not calls or calls[0].function.name != "search_policy":
        out["fail"] = f"no search_policy call: {(m1.content or '')[:200]}"
        return out
    msgs.append(m1.model_dump(exclude_none=True))
    for c in calls:  # several models issue parallel calls; answer every one
        msgs.append({"role": "tool", "tool_call_id": c.id, "content": TOOL_RESULT})
    t = time.time()
    r2 = client().chat.completions.create(model=model, messages=msgs, tools=TOOLS, max_tokens=2000)
    out["turn2_s"] = round(time.time() - t, 1)
    calls2 = r2.choices[0].message.tool_calls or []
    if not calls2 or calls2[0].function.name != "submit_findings":
        out["fail"] = "no submit_findings call"
        return out
    try:
        args = json.loads(calls2[0].function.arguments)
    except json.JSONDecodeError:
        out["fail"] = "invalid JSON arguments"
        return out
    out["correct"] = all(args.get(k) == v for k, v in EXPECTED.items())
    out["missing_evidence"] = args.get("missing_evidence")
    return out


if __name__ == "__main__":
    for m in sys.argv[1:] or DEFAULT_MODELS:
        try:
            print(json.dumps(check(m)))
        except Exception as e:  # keep testing the other models
            print(json.dumps({"model": m, "error": f"{type(e).__name__}: {str(e)[:300]}"}))
