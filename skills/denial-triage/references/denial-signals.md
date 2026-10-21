# Denial signals

Typical wording in denial letters, by type. Wording varies; use these as hints, not rules.

## medical_necessity
- "not medically necessary", "does not meet clinical criteria"
- "records do not document / do not support / do not establish"
- "could have been treated at a lower level of care", "continued stay not justified"
- "a trial of [other drug/treatment] is required first" (step therapy, conservative treatment)
- "experimental", "investigational", "not proven effective"
- "cosmetic" (when the dispute is whether symptoms justify the procedure)

## prior_authorization
- "prior authorization / precertification / preauthorization was required and not obtained"
- "no authorization on file", "authorization expired", "authorization was for a different service, provider or facility"
- "notification requirements were not met"

## out_of_network
- "not a participating / network / contracted provider"
- "processed at the out-of-network benefit level", "your plan does not cover out-of-network care"
- "no referral on file" combined with a non-network specialist (an HMO-style denial)

## coding_error
- Mentions specific codes: CPT/HCPCS (5 characters, e.g. 99214, J3301) or ICD-10 (e.g. M54.5)
- "invalid / not billable / deleted code", "diagnosis does not support the procedure as coded"
- "duplicate", "included in / bundled with another service", "component of a panel"
- "modifier missing / invalid", "units exceed the maximum", "place of service"
- "processed as diagnostic rather than preventive / screening"

## Common traps
- A **provider identifier** problem can be a network issue (the provider really is out of network at that location) or a billing error (the wrong ID was put on the claim). Often ambiguous.
- "Does not support the procedure **as billed**" can be a coding mismatch or a medical-necessity judgment. Often ambiguous.
- Two sentences giving two reasons ("not authorized, and records do not establish necessity") means two types.
- An emergency treated out of network is still classified `out_of_network`; the emergency is the argument, not the type.
