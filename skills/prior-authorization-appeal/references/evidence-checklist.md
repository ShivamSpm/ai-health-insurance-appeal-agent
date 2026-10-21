# Evidence checklist: prior authorization

Report missing evidence using these vocabulary IDs (the full list is in the `submit_findings` tool schema).

| ID | When it's needed |
|---|---|
| `ordering_physician_order` | Usually. Shows what was ordered and why. |
| `medical_records` | Usually. Shows the clinical situation at the time. |
| `prior_auth_request_record` | When the member or provider says a request was submitted or approved but the insurer has no record. |
| `urgency_documentation` | When arguing the service was urgent and couldn't wait for approval. |
| `emergency_records` | When the service was emergency care. |

## How to decide what is missing

1. **Required** = items the plan's appeals section lists for prior authorization denials + items the denial letter says were missing + the item that proves the exception you rely on (e.g. urgency or emergency records).
2. **Has** = items the member already has (the "What I have so far" list in their note). Match by meaning, not exact wording.
3. **Missing** = required − has.
