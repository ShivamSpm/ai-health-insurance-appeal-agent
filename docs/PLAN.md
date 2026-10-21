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

### Dataset decisions (agreed on Day 1)
| Area | Decision | Why |
|---|---|---|
| Generation | Python builds each case from a structured spec, so labels are correct by construction. A cheap model writes only the letter and note prose. Code checks that the key facts appear in the text, and any injection line is inserted by code. | Reliable labels with varied text. |
| Inputs per case | Denial letter, plan document, and a short **member note** saying what the member already has | Makes "missing evidence" a reading task, not a lookup |
| Missing evidence | `required − member_has`. `required` = what the plan's appeals section lists for that denial type, plus anything the denial letter says was lacking. Labels use IDs from a fixed vocabulary (`data/evidence_vocabulary.json`). The agent outputs IDs plus a free-text reason for each. | IDs are scored in code (precision/recall). The free text is checked by the letter-quality judge. Free text alone varied too much between models in the model check. |
| Ambiguous denials | The agent must output `ambiguous: true` and the candidate types. Ambiguous cases are labeled with ≥2 `denial_types`. | Tests whether the agent knows when it's unsure, instead of just guessing |
| Case mix | 28 standard (7 per denial type) + 12 hard (3 each: ambiguous, valid denial, contradictory documents, prompt injection) | |
| Plans | One fictional insurer with 3 plans (PPO, HMO, EPO). Section numbering is the same across plans, but the rules differ: appeal window, prior-auth list, network rules. | The agent must read the right plan instead of memorizing one |
| Deadlines | Each plan sets its own appeal window and starting point (date on the notice or date received), and one plan has a weekend rule | Deadline accuracy tests reading the plan, not knowing the ACA default |
| Format | Markdown. Plans have `<!-- page N -->` markers and numbered `###` sections, which give chunk IDs like `ppo-7.1`. | Stable citations, easy highlighting in the UI |

### Runtime decisions (agreed on Day 2)
| Area | Decision |
|---|---|
| Document access | Tools: `get_denial_letter()` and `get_member_note()`. Content is returned wrapped as untrusted document data. |
| Policy retrieval | `search_policy(query)`: BM25 over plan sections, top 4, full section text with chunk ID, title and page. `get_section(id)` fetches one section by ID, for cross-references. Anything returned counts as retrieved. |
| Deadline math | `date_calc(start, add_days)` returns the date and its weekday. The agent must still read the plan's rule. |
| Output | Two tools. `submit_findings` is validated first, then `submit_appeal_letter`, with inline citations like `[ppo-6.4]` that must have been retrieved. |
| Findings fields | Denial type(s), `ambiguous`, governing clauses, `denial_basis_clause`, missing evidence (vocabulary ID + reason), deadline with reasoning, `appeal_viable` + rationale, `contradictions`, `suspicious_instructions` |
| Weak appeals | If `appeal_viable` is false, the agent explains why and writes no letter |
| Skill content | General real-world appeal knowledge and evidence checklists using the vocabulary IDs. Never this insurer's section numbers or rules. |
| Ambiguous denials | Load the appeal skill for every candidate type. The letter addresses each reading. |
| Workflow gates | None. The system prompt describes the workflow, and the evals measure whether it was followed. |
| Letter gaps | Known facts are filled in. Unknown details become `[bracketed placeholders]` for the human. |
| Limits | 25 steps (one step = one LLM call), 2 retries for malformed or invalid tool calls, temperature 0 |
| Traces | SQLite from Day 2 (runs and steps tables), with a CLI trace viewer and a JSON export |
| Cost | Per-token prices from Crusoe's public pricing page, kept in `config.toml` with source and date |
| Versioning | Each run stores a content hash of the system prompt and of each skill folder, plus the git commit SHA |

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
