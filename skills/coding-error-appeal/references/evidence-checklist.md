# Evidence checklist: coding error

Report missing evidence using these vocabulary IDs (the full list is in the `submit_findings` tool schema).

| ID | When it's needed |
|---|---|
| `itemized_bill` | Usually. Shows every code and charge as billed. |
| `provider_coding_letter` | When the plan asks for the provider's explanation of the coding or correction. |
| `corrected_claim` | When the provider must resubmit with fixed codes, modifiers or units, or when the plan's appeals section asks for it. |
| `medical_records` | When the dispute depends on what was actually done (e.g. a separately identifiable visit). |
| `eob` | Helpful to show how the claim was processed; required only if the plan asks for it. |

## How to decide what is missing

1. **Required** = items the plan's appeals section lists for coding or billing denials + items the denial letter says were missing.
2. **Has** = items the member already has (the "What I have so far" list in their note). Match by meaning, not exact wording.
3. **Missing** = required − has.
