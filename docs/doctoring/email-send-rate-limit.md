# Email send rate-limit authority

**Product action:** After ten successful sends in a 60-second scope, wait for
the window to roll or ask an operator to inspect shared limiter availability.
A `429` means the quota is exhausted. A `503` with
`email_send_limit_unavailable` means sending is blocked until the shared store
is healthy — do not retry across another replica to bypass the limit.

## Defect

`POST /api/emails/send` previously counted attempts in a process-local
dictionary guarded by a thread `Lock` (`backend/api/emails.py`). Each API
worker therefore owned an independent 10-per-60-second bucket. Routing the
same authorized `(organization_id, user_id)` across workers oversubscribed the
published restriction. Issue #1379 records the buyer/security impact and the
Strix attribution to this unchanged send path.

## Decision

Naruon now keeps one server-authoritative occupancy window per authorized
scope in `email_send_limit_windows`. Reservation is a single atomic
`INSERT ... ON CONFLICT` so concurrent requests cannot all observe the same
pre-limit count. Shared-state failure fails closed. The limiter never stores
message body, recipients, subject, or credentials.

The table is third-normal-form: `window_uid` identifies the current window;
`(organization_id, owner_user_id)` is the authorized scope; `window_started_at`
and `attempt_count` are facts about that current window only.

## Standards and research

The HTTP contract follows additional status codes for quota exhaustion and
keeps infrastructure unavailability distinct from that exhaustion.

Bray, T. (2012). *Additional HTTP status codes* (RFC 6585). Internet
Engineering Task Force. https://doi.org/10.17487/RFC6585

Fielding, R., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP semantics*
(RFC 9110). Internet Engineering Task Force. https://doi.org/10.17487/RFC9110

Atomic occupancy uses a compare-and-set style update on a unique scope key,
the same isolation idea transaction-processing systems use for shared counters
rather than replica-local memory.

Gray, J., & Reuter, A. (1993). *Transaction processing: Concepts and
techniques*. Morgan Kaufmann.

Distributed token-bucket and leaky-bucket controllers remain the classic
overload models; Naruon applies a fixed window because the published product
contract is “10 successful attempts in 60 seconds,” not a smoothed rate.

Berger, A. W. (1991). Comparison of call gapping and leaky bucket for
overload control in distributed switching systems and telecommunications
networks. *IEEE Transactions on Communications, 39*(4), 574–583.
https://doi.org/10.1109/26.81745

## Verification

`backend/tests/test_email_send_rate_limit.py` proves independent local
buckets oversubscribe, a shared store rejects the 11th attempt, two workers
sharing one store share one bucket, concurrent reservations cannot
oversubscribe, scopes stay isolated, window rollover uses an injected clock,
store failure is `unavailable` rather than local memory, and limiter state
contains no message fields.
