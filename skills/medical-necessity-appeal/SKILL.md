---
name: medical-necessity-appeal
description: Build the case for appealing a denial that says a service was not medically necessary, did not meet clinical criteria, skipped required earlier treatments (step therapy or conservative care), or is experimental. Use after denial-triage classifies a denial as medical_necessity.
---

# Medical necessity appeal

A medical necessity denial says the insurer's reviewer did not see enough clinical justification. Most succeed or fail on **documentation**: showing that the plan's own criteria were met.

## 1. Find the plan's criteria

Search the plan document for:
- its definition of "medically necessary"
- any criteria specific to this service (clinical criteria, conservative treatment or step therapy rules, level-of-care rules)
- any exclusion that could apply (experimental/investigational, cosmetic)

The clause with the service-specific criteria is usually the governing clause. Cite the exact chunk IDs you retrieved.

## 2. Compare the facts to the criteria

Use the member note and the denial letter. Common patterns:

| Denial says | Typical appeal argument |
|---|---|
| Records don't document required earlier treatment | The treatment happened; supply records showing what was tried, for how long, and that it failed. |
| Step therapy drug not tried | The preferred drug was tried before, or is contraindicated or was not tolerated. Most step-therapy rules have these exceptions. |
| Criteria not met (device, test, procedure) | Show the specific criterion the member meets (e.g. a documented condition, a failed or inadequate earlier test, a comorbidity). |
| Could have been treated at a lower level of care | Show the services needed that could only be given at the higher level (e.g. IV therapy, monitored oxygen). |
| No measurable improvement (therapy) | Show measurable functional gains, or that therapy prevents significant loss of function. |
| Cosmetic | Show the functional symptoms and their duration despite conservative measures. |

## 3. Judge viability honestly

An appeal is **not viable** when the plan clearly excludes the service regardless of the member's facts, most often an explicit experimental/investigational exclusion that names the service, with no evidence the service has become standard of care. Mention that external review may still be available, but set `appeal_viable` to false and explain.

## 4. Evidence

See `references/evidence-checklist.md`. Start from what the plan's appeals section says to include for this kind of denial, add anything the denial letter says was missing, then remove what the member already has.
