# AI Health Insurance Appeal Agent

Upload a health insurance denial letter and your plan document. The agent works out why the claim was denied, finds the plan clause that governs it, lists the evidence you still need, computes your appeal deadline, and drafts an appeal letter where every claim cites the plan. A human reviews and edits the draft. The agent never sends anything.

Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design.

## Layout
- `backend/`: Python agent runtime, dataset generator, evals (FastAPI comes later)
- `data/`: synthetic plans and cases from a fictional insurer, with ground-truth labels. No real patient data.
- `skills/`: agent skills (SKILL.md format)
- `frontend/`: Next.js review UI (coming later)

## Setup
```bash
cp .env.example .env   # add your Crusoe API key
cd backend
uv sync
```

## Run the agent
```bash
cd backend
uv run appeal-agent run case-031            # main model from config.toml
uv run appeal-agent run case-031 --model deepseek-ai/DeepSeek-V4.1-Flash
uv run appeal-agent trace <run_id>          # step-by-step trace; --full, --json
uv run appeal-agent runs                    # recent runs
uv run pytest                               # tests, no LLM calls
```
