# Data anonymizer boundary

## Decision and observed implementation

PR #1482 repair parent `034d111b6bef126929d6f0085c2fa15bbf9724be`
stacks on PR #1555 exact head
`03799bc157fa39a419cf6c3f77a29a2ca02cd7f4`. The handler reuses the stack's
canonical ASCII email and selected Korean/North American phone matchers, then
adds bounded Unicode-email, French phone, and Korean resident-registration
patterns. Every input is subject to `ANALYSIS_TEXT_MAX_CHARS` before scanning.

This tool performs deterministic format masking only. It does not measure
re-identification risk, detect names or organizations, transform free-form
quasi-identifiers, or certify that output is anonymous. Product copy must keep
that limitation visible. A downstream workflow that requires release-grade
de-identification needs a documented data model, threat model, risk metric,
review authority, and evidence that the transformed dataset meets its intended
use. It must not infer that assurance from this handler's successful response.

Endpoint regressions cover hyphenated and separator-free Korean identifiers,
an internationalized email address, a French phone number, punctuation
preservation, and the input-size boundary. The values are synthetic test data;
no real person's identifiers are committed.

## Research grounding

NIST SP 800-188 treats de-identification as a managed process involving data
models, techniques, governance, and re-identification risk rather than a small
set of textual substitutions. That distinction supports the deliberately
narrow product claim above and rejects the earlier broad “data anonymization”
assurance.

Garfinkel, S., Guttman, B., Near, J., Dajani, A., & Singer, P. (2023).
*De-identifying government datasets: Techniques and governance* (NIST Special
Publication 800-188). National Institute of Standards and Technology.
https://doi.org/10.6028/NIST.SP.800-188

The official publication page was available during verification, but its
linked PDF endpoint returned HTTP 404 on 2026-09-04. The PR therefore records
the DOI and bounded summary instead of committing an unverified or
redistribution-uncertain binary.
