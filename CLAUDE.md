# AI Health Insurance Appeal Agent

A portfolio project the owner is building to get hired at SF AI startups, for **both full-stack and AI engineer roles**. Read `docs/PLAN.md` for the full agreed plan before doing anything.

## How to work with the owner
- **Ask, don't assume.** The owner explicitly asked to be consulted at every step. If a decision isn't already settled in `docs/PLAN.md`, ask before acting.
- **The owner must be able to defend every decision in interviews.** Present options and tradeoffs for architecture, skill boundaries, and eval labels, and let the owner choose. Claude writes most of the code. The owner runs the evals, does the error analysis, and makes some fixes personally.
- Work in the day-by-day stages in `docs/PLAN.md`. Stop at the end of each stage for review instead of building ahead.
- Make small, meaningful git commits. Interviewers may read the history.

## Environment
- Owner's machine: Windows. The project lives at `G:\Projects\AI-Health-Insurance-Appeal-Agent`.
- LLM provider: Crusoe Managed Inference, OpenAI-compatible. Base URL: `https://api.inference.crusoecloud.com/v1/`
- The API key lives in `.env` as `CRUSOE_API_KEY`. **Never read, print, or commit `.env`.** Commit a `.env.example` instead.
- Crusoe's API does not support the `developer` message role. Use `system`.
- Models available on the owner's account (display names): DeepSeek V4 Flash 0731, DeepSeek V4 Pro, DeepSeek V4.1 Flash, Gemma 4 31B, GLM-5.3, GLM-5.3 Flash, GPT-OSS 120B, Nemotron 3.5 Lightning 30B A3B, Nemotron 3 Nano 30B, Nemotron 3 Super 120B, NVIDIA Nemotron 3.5 Super VL, Qwen3.8 27B. Get the exact model IDs from `client.models.list()`. Keep model choice in config, never hard-coded.
- Budget: about $20/month in total. Keep eval runs small and cache results where possible.

## Status
- [x] Plan agreed (`docs/PLAN.md`)
- [x] Confirm exact model IDs, and test tool calling on the candidate models (2026-10-20)
  - IDs: `deepseek-ai/DeepSeek-V4-Pro` (main), `deepseek-ai/DeepSeek-V4.1-Flash` (cheap comparison), `openai/gpt-oss-120b`, `zai-org/GLM-5.3`. Others: `deepseek-ai/Deepseek-V4-Flash`, `zai-org/GLM-5.3-Flash`, `Qwen/Qwen3.8-27B`, `google/gemma-4-31b-it`, `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B`, `nvidia/Nemotron-3.5-Lightning-30B-A3B`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`, `nvidia/NVIDIA-Nemotron-3.5-Super-VL`.
  - Two-turn test (`search_policy`, then a nested-schema `submit_findings`, `system` role): all four candidates returned valid JSON with the right denial type, clause and deadline.
  - DeepSeek Pro, DeepSeek Flash and GLM emit **parallel tool calls** in one turn, so the runtime must handle several tool calls per step.
  - Free-text `missing_evidence` varied a lot between models (1 to 4 items, different wording), so it can't be scored by exact match.
- [ ] GitHub repo created and linked
- [ ] Day 1: scaffold, synthetic case generator, 40 labeled cases
