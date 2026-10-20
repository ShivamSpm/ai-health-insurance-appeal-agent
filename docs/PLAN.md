# Project Plan: AI Health Insurance Appeal Agent

## Why this project
SF AI startups, many of them YC-backed in insurance, legal and healthcare, build vertical AI agents. Their full-stack and AI engineer postings ask for agent orchestration and tool use, human review UIs (review queues, diff views, agent chat), observability, and **evals**. This project shows all of those in one product. It's close to the domain of agentic insurance brokerages, since it uses skill files, Hermes and evals, but it isn't a copy of any company's product.

## What it does
A user uploads a health insurance **denial letter** and their **plan document**. The agent:
1. Classifies the denial reason.
2. Loads the matching skill.
3. Finds the governing policy clause.
4. Lists the missing evidence.
5. Computes the appeal deadline.
6. Drafts an appeal letter where every claim cites the policy.

A human reviews and edits the draft. The agent never sends anything.

## Agreed decisions
| Area | Decision |
|---|---|
| Backend | Python, FastAPI, Pydantic, SQLite |
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| LLM | Crusoe Managed Inference through the OpenAI SDK. Model set in config. |
| Agent runtime | Custom, about 400 lines of Python. No agent framework. |
| Skills | SKILL.md files in agentskills.io format, so they work with Hermes Agent too |
| Hermes | Short demo of Hermes Agent running the same `skills/` on Crusoe |
| Budget | About $20/month. Public demo replays saved runs; live mode sits behind a password. |
| Version control | Git and GitHub from day one |

## Architecture

### Agent runtime
- OpenAI SDK pointed at Crusoe. Model ID read from config.
- **Skills load in three levels.** The system prompt holds only the skill names and descriptions. The `load_skill(name)` tool returns the full SKILL.md. The `read_skill_file(name, path)` tool returns a reference file.
- **Domain tools:**
  - `search_policy(query)`: search over the plan document split into sections. Returns chunk IDs and page numbers for citations.
  - `get_denial_letter()`
  - `submit_findings(...)`: structured output, validated with Pydantic.
- **Guardrails:** step limit; retries on malformed output; a clause can only be cited if it was actually retrieved; text inside documents is treated as data, not instructions.
- Every LLM and tool call is logged with tokens, latency and cost, for traces and evals.

### Skills (`skills/`)
- `denial-triage`: router that classifies the denial
- `medical-necessity-appeal`
- `prior-authorization-appeal`
- `out-of-network-appeal`
- `coding-error-appeal`
- `appeal-letter-writing`: format, tone and deadline rules

Each skill has a `references/` folder for things like evidence checklists.

### Backend
REST endpoints for cases and runs. Server-sent events stream agent steps live to the UI. Runs, steps and eval results are stored in SQLite.

### Frontend
- **Case inbox:** upload documents, see case status.
- **Case workspace:** documents with cited passages highlighted; findings; editable appeal draft; trace timeline showing skills loaded, tool calls, tokens, latency and cost.
- **Eval dashboard:** list of runs, scores per metric, side-by-side diff of two runs, failure browser.

### Dataset
About 40 synthetic cases from a fictional insurer and its plans. No real patient data. Each case has ground-truth labels: denial type, governing clause, missing evidence, deadline.

Deliberately hard cases:
- an ambiguous denial reason
- a valid denial, where the right answer is "appeal unlikely to succeed"
- contradictory documents
- a prompt-injection line hidden in a denial letter

### Evals
- **Code-checked:** denial-type accuracy, skill-routing accuracy, clause retrieval recall, citation validity, deadline accuracy, output validity, steps per case.
- **LLM-as-judge:** appeal quality against a rubric (grounded, addresses the denial reason, no invented facts). Calibrated against about 15 letters hand-labeled by the owner; the agreement rate is reported.
- **Regression tracking:** each run records the model, prompt version and skill versions. Any two runs can be compared.
- **Model comparison:** two Crusoe models compared on accuracy, cost and latency.

### Model candidates (to confirm with a quick tool-calling test)
- Main model: DeepSeek V4 Pro
- Cheaper comparison: DeepSeek V4.1 Flash. Same family, so the comparison is clean.
- Optional third: GPT-OSS 120B or GLM-5.3, to compare across model families.

## Build plan (about 1 week)
| Day | Claude builds | Owner does |
|---|---|---|
| 1 | Scaffold, dataset generator, 40 cases | Review 10 cases and fix labels |
| 2 | Runtime, skills, tools, command-line runner | Run 5 cases and read the traces |
| 3 | Eval harness and baseline run | Write the error analysis |
| 4 | FastAPI streaming and case workspace UI | Test the flow, give UX feedback |
| 5 | Eval dashboard and trace view | Hand-label 15 letters for judge calibration |
| 6 | Skill fixes and model comparison | Fix 2–3 failure types personally; Hermes demo |
| 7 | Deploy; README with diagram and results | Record a 2-minute demo video |

## Deployment
Frontend on Vercel's free tier. Backend on Render or Fly.
