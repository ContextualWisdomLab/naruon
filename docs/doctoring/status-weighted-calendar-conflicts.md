# Status-weighted calendar conflict policy

## Shipped boundary in this slice

Naruon evaluates a proposed calendar commitment against a bounded set of existing commitments and returns one of three deterministic outcomes: `available`, `blocked`, or `review_required`. The decision is advisory evidence only. It does not mutate, cancel, reschedule, accept, or decline any provider event.

The public endpoint is `POST /api/calendar/conflicts/evaluate`. It is mounted behind Naruon's existing private API authentication dependency. Inputs use timezone-aware timestamps, an opaque commitment identifier, and one of the product statuses `confirmed`, `tentative`, or `desired`. Existing evidence is capped at 500 commitments per request.

## Standards traceability

RFC 5545 defines `VEVENT` `DTSTART` as inclusive and `DTEND` as non-inclusive, and requires `DTEND` to be later than `DTSTART`. Naruon therefore evaluates conflicts as half-open intervals `[start_at, end_at)`: an event ending exactly when another begins is not a collision. The implementation compares timezone-aware instants, so equivalent instants represented with different UTC offsets still collide.

RFC 5546 defines iTIP scheduling methods such as `REQUEST` and `REPLY`, including attendee participation status (`PARTSTAT`). It provides the interoperability basis for later RSVP/writeback integration, but it does **not** define Naruon's three-level scheduling priority. `confirmed > tentative > desired` is an explicit Naruon product policy required by roadmap issue #988, not a standards claim.

## Decision policy

- No overlapping commitment: `available`; the customer can proceed.
- Any equal- or higher-priority overlap: `blocked`; the customer must choose another time or explicitly resolve that conflict first.
- Only lower-priority overlaps: `review_required`; Naruon surfaces the lower-priority conflicts and requires explicit review instead of silently displacing them.
- An existing commitment with the same opaque identifier as the proposal is treated as the current representation of that event, not as a self-conflict.
- Conflict evidence is sorted by UTC start instant and then opaque identifier so provider response ordering cannot change the decision payload.

This policy deliberately prevents a convenience feature from silently breaking an existing confirmed commitment. A later RSVP slice may consume the same deterministic policy, but this slice does not claim RSVP mutation support.

## Security, privacy, and operability

The decision path is deterministic and uses no LLM judgment. It accepts only scheduling evidence needed for the decision; it does not require email bodies, participant names, provider credentials, or calendar descriptions. The endpoint rejects naive timestamps, invalid/non-positive intervals, unsupported statuses, oversized evidence batches, and extra request fields through the transport/service validation layers. Customer-facing results include a concrete next action rather than a generic warning.

No database objects or migrations are introduced. No provider is contacted. Rollback consists of removing the endpoint registration and policy module; existing calendar data is unaffected because the slice is read-only with respect to provider and database state.

## Verification evidence required before merge

The exact unchanged PR head must prove realistic overlap, adjacency, timezone-offset equivalence, deterministic ordering, self-update, invalid interval, unsupported status, API validation, authentication, and bounded-batch behavior. Repository-required CI, security, coverage, supply-chain, package, and independent current-head review gates remain authoritative; predecessor or queued evidence is non-passing.

## References (APA 7th)

Daboo, C. (Ed.). (2009). *iCalendar transport-independent interoperability protocol (iTIP)* (RFC 5546). RFC Editor. https://doi.org/10.17487/RFC5546

Desruisseaux, B. (Ed.). (2009). *Internet calendaring and scheduling core object specification (iCalendar)* (RFC 5545). RFC Editor. https://doi.org/10.17487/RFC5545
