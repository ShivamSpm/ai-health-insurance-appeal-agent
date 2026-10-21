# Evidence checklist: medical necessity

Report missing evidence using these vocabulary IDs (the full list is in the `submit_findings` tool schema).

| ID | When it's needed |
|---|---|
| `letter_of_medical_necessity` | Almost always. The treating provider explains why this patient needs this service. |
| `medical_records` | Almost always. Notes and history showing the condition and its severity. |
| `conservative_treatment_records` | When the denial says earlier or less intensive treatment wasn't tried or documented (physical therapy, medications, injections, a step-therapy drug). |
| `diagnostic_test_results` | When criteria depend on test results (labs, imaging, monitoring logs, a prior test that was inconclusive), or when the plan's appeals section lists test results. |
| `clinical_guidelines` | Helpful when arguing the service is standard of care; required only if the plan asks for it. |

## How to decide what is missing

1. **Required** = items the plan's appeals section lists for medical necessity denials + items the denial letter says were missing or insufficient.
2. **Has** = items the member says they already have (the "What I have so far" list in their note). Match by meaning, not exact wording.
3. **Missing** = required − has. Don't list things the member already has. Don't list nice-to-have items as missing unless the plan or the letter calls for them.
