---
name: out-of-network-appeal
description: Build the case for appealing a denial or reduced payment because the provider or facility was out of network. Covers emergencies, providers the member didn't choose, network gaps, continuity of care, directory errors and out-of-area urgent care. Use after denial-triage classifies a denial as out_of_network.
---

# Out-of-network appeal

An out-of-network (OON) denial says the provider has no contract with the plan. Many US plans, and federal rules such as the No Surprises Act, protect members in specific situations. The appeal asks the plan to apply **network-level cost sharing** under one of these protections. Always confirm the protection in **this** plan's text before relying on it.

## 1. Read the plan's out-of-network rules

Search for: out-of-network coverage, emergency services, network access or adequacy exceptions, continuity of care, out-of-network providers at network facilities, provider directory accuracy, referrals, and urgent care while traveling.

## 2. Find the protection that fits

| Situation | Typical argument |
|---|---|
| Emergency care at an OON hospital | Emergency services are covered at network cost sharing at any emergency department. Whether it was an emergency depends on the symptoms (the prudent layperson standard), not the final diagnosis. |
| OON clinician the member didn't choose, at a network facility (anesthesia, radiology, pathology, lab) | Member pays network cost sharing and can't be balance billed. |
| No network provider available within the plan's distance or wait-time standards | Network access (adequacy) exception: OON care covered at network cost sharing. Check the standards and any referral requirement. |
| Provider left the network mid-treatment (serious condition, pregnancy) | Continuity of care for a limited period. |
| Directory listed the provider as in-network | Member relied on the plan's directory, so network cost sharing applies. |
| Urgent care far from home | Many plans cover out-of-area urgent care at network cost sharing beyond a distance threshold. |

## 3. Judge viability honestly

An appeal is **not viable** when the member chose an OON provider for non-urgent care, no protection applies, and the plan has no OON benefit (or the member already got it). In particular, if a network provider was available within the plan's access standards, a network-gap argument fails. Set `appeal_viable` to false and explain.

Referral-based plans (HMOs) often require a PCP referral for specialist care and for network exceptions. Check the referral rules.

## 4. Evidence

See `references/evidence-checklist.md`.
