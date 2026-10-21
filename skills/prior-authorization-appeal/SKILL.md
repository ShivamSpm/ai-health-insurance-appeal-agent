---
name: prior-authorization-appeal
description: Build the case for appealing a denial because prior authorization (precertification) was required and not obtained, not on file, expired, or did not match the service. Use after denial-triage classifies a denial as prior_authorization.
---

# Prior authorization appeal

A prior authorization (PA) denial is procedural: the insurer says approval was needed first. The appeal usually wins on one of the exceptions below, not on arguing the rules.

## 1. Check whether PA was actually required

Search the plan for its list of services that require prior authorization. Check carefully:
- Is this service on the list for **this** plan?
- Are there thresholds (e.g. therapy visits only after a certain number per year)?

If the service wasn't on the list, or was under a threshold, that is the appeal, and it's a contradiction between the letter and the plan.

## 2. Look for the exception that fits

| Situation | Typical argument (verify in the plan) |
|---|---|
| Emergency care | Emergency services never need prior authorization. |
| Urgent care that couldn't wait | Many plans allow retrospective review when the service was urgent and records show why. Check whether this plan allows it, and for which services. |
| PA was requested and approved, but the insurer has no record | Plans often honor an approval the provider can document (reference number, confirmation). |
| Approved service moved to another facility or date | Check whether the plan keeps an authorization valid for the same service at another network facility, and how long approvals last. |
| A network provider was responsible for getting PA and didn't | Many plans make network providers responsible and bar them from billing the member. The member shouldn't pay. |

## 3. Judge viability honestly

An appeal is **not viable** when PA was clearly required, no exception applies, and the plan leaves the member responsible. Typical example: non-urgent elective care from an **out-of-network** provider who didn't get approval, under a plan with no retrospective review for that situation. Set `appeal_viable` to false and explain.

Read retrospective-review rules carefully: plans differ, and some allow it only for emergencies.

## 4. Evidence

See `references/evidence-checklist.md`.
