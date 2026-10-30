# Day 3 error analysis: baseline

> Owner-written. Fill this in after running the baseline. Keep claims tied to evidence: case IDs, run IDs, trace excerpts.

## 1. Setup

- **Eval ID:**
- **Model:**
- **Passes:**
- **Git SHA / prompt hash / labels hash:** (copy from the report header)
- **Total cost:**
- **Label review status:** (Day 1 review of 10 cases done? Any label changes since? If labels change later, re-score with `uv run appeal-agent eval score <eval_id>`.)

## 2. Headline numbers

Copy the key rows from the report. Note anything with a large ± (run-to-run noise).

| Metric | Score | Notes |
|---|---|---|
| completed | | |
| denial_type | | |
| clause_recall / clause_precision | | |
| evidence_recall / evidence_precision | | |
| deadline | | |
| viability / valid_denial_caught | | |
| injection_resisted / injection_detected | | |
| contradiction_flagged / contradiction_false_flag | | |
| cost_usd / llm_calls | | |

## 3. Failure categories

Read failing traces (`uv run appeal-agent eval failures <eval_id> --metric <name>`, then `uv run appeal-agent trace <run_id>`). Group failures by **root cause**, not by metric. One failure can show up in several metrics.

| # | Category (root cause) | Metrics affected | Cases (passes) | Count | Example run |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

For each category:

### Category 1: <name>
- **What happens:** (one or two sentences, with a trace excerpt)
- **Why (hypothesis):** prompt? skill content? tool design? retrieval miss? label problem? model limit?
- **Is the label right?** (if not, fix it in `scenarios.py` and re-score; it's a label bug, not an agent bug)
- **Proposed fix:** (the smallest change; which file)
- **How we'll know it worked:** (which metric should move, by roughly how much)

## 4. Label issues found

Cases where the agent's answer was defensible and the label was wrong or debatable.

| Case | Field | Label says | Should be | Reason |
|---|---|---|---|---|

## 5. Things that worked

Behaviors worth keeping. Protect them when making fixes.

## 6. Fix plan for Day 6

Ranked by expected impact / effort. Include the backlog item already scheduled ("Before you send" checklist, from case-040).

| Rank | Fix | Category | Expected metric change | Owner or Claude |
|---|---|---|---|---|
