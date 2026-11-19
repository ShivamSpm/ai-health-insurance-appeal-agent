# AI Health Insurance Appeal Agent

Upload a health insurance denial letter and your plan document. The agent works out why the claim was denied, finds the plan clause that governs it, lists the evidence you still need, computes your appeal deadline, and drafts an appeal letter where every claim cites the plan. A human reviews and edits the draft. The agent never sends anything.

Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design.

## Layout
- `backend/`: Python agent runtime, dataset generator, evals, and the FastAPI API for the UI
- `data/`: synthetic plans and cases from a fictional insurer, with ground-truth labels. No real patient data.
- `skills/`: agent skills (SKILL.md format)
- `frontend/`: Next.js review UI (case inbox and case workspace)

## Setup
```bash
cp .env.example .env   # add your Crusoe API key
cd backend
uv sync
cd ../frontend
npm install
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

## Run evals
```bash
cd backend
uv run appeal-agent eval run --name baseline          # all 40 cases x 3 passes on the main model
uv run appeal-agent eval list
uv run appeal-agent eval failures <eval_id> --metric deadline
uv run appeal-agent eval failures <eval_id> --metric clause_precision --tally   # most common wrong answers
uv run appeal-agent eval compare <eval_a> <eval_b>
uv run appeal-agent eval score <eval_id>              # re-score stored runs after a label change (free)
```
Reports are written to `evals/reports/`.

## Run the review UI
Two terminals:
```bash
cd backend
uv run appeal-agent serve                   # API on http://127.0.0.1:8000
```
```bash
cd frontend
npm run dev                                 # UI on http://localhost:3000
```
Open a case to replay a stored run (free) or start a live run (calls the model, a few cents). Findings link each plan citation to its section, and edits to the draft are saved as versions with a diff against the agent's draft. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if the API runs elsewhere.

```bash
cd frontend
npm run typecheck && npm run lint
npm run test:e2e                            # Playwright smoke test; own API on a fresh DB with the scripted model, no LLM calls
npm run gen:api                             # regenerate TypeScript types after changing API models
```
