# ADR-0005: Publish a fail-closed calendar projection for LineageWeave

- Status: Accepted
- Date: 2026-08-21
- Related: Naruon #978, #998, #1437; LineageWeave #336, PR #355

## Context

Naruon owns customer mail, calendar, contact, and file provider interaction.
LineageWeave owns post-grounded commitments, issue/todo identity, and the
ontology/provenance used to explain those internal work records. A future Buyer
Calendar may show both Naruon-observed provider occurrences and LineageWeave
commitments, but those records have different truth and authority.

The earlier LineageWeave adapter read a custom JSON `/events` endpoint and was
named as CalDAV even though it did not implement WebDAV discovery/REPORT,
recurrence, timezone reconciliation, sync-token/ETag behavior, provider
credentials, or writeback. LineageWeave PR #355 corrects that product claim and
publishes a strict consumer contract.

Naruon currently has CalDAV writeback intent and runner dispatch, but inbound
CalDAV import remains explicitly unconfigured. Publishing synthetic or empty
success as if provider observations existed would create false product evidence.

## Decision

Naruon publishes the provider side of calendar projection contract `1.0` at:

```text
GET /api/calendar/events
```

The route is not protected by the browser/end-user session dependency. It uses a
separate RS256 service token issued by the configured OIDC authority with:

```text
aud = naruon-calendar-read
scope includes calendar:read
organization_id = exact tenant scope
workspace_id = exact workspace scope
```

Tokens are verified against startup-cached signing keys. Missing OIDC
configuration or signing keys fails closed. A browser token for `naruon-api`, a
provider credential, or a token without the exact read scope is rejected.

The route accepts an offset-aware RFC 3339 window, a page limit of 1..200, and an
optional opaque cursor. Windows longer than 366 days, URL-shaped cursors, naive
or invalid timestamps, and end-before-start windows fail before provider access.
The response media type is:

```text
application/vnd.contextualwisdomlab.naruon-calendar.v1+json
```

Each occurrence contains only opaque source/event/occurrence references,
provider revision, policy-filtered display text, interval, all-day/timezone,
status, disclosure, and `observed` provenance. Attendees, descriptions, provider
URLs, credentials, sync tokens, and raw DAV payloads are outside contract v1.

The product default is `UnconfiguredCalendarProjectionProvider`, which returns
an explicit `503 calendar_projection_unavailable`. The endpoint therefore exists
for provider/consumer contract testing without claiming inbound calendar data.
A real implementation may replace the provider port only after Naruon has:

- an authoritative normalized occurrence/read model;
- tenant/workspace and source disclosure policy;
- provider revision and recurrence evidence;
- synchronization, retry, and reconciliation receipts; and
- immutable conformance fixtures consumed by LineageWeave.

## Consequences

### Positive

- Naruon and LineageWeave can test one stable media/schema/auth contract without
  direct SQL, shared ORM state, or provider credential forwarding.
- Browser identity and service identity have different audiences and cannot be
  silently interchanged.
- Naruon does not fabricate external events while inbound synchronization is
  absent.
- LineageWeave commitments remain independently available when the provider
  projection is unavailable.
- The contract can merge before the real provider adapter while remaining
  operationally disabled.

### Costs and limitations

- This ADR does not claim CalDAV conformance or a working inbound event feed.
- A service token issuer/client configuration must be added to Keyverse or the
  deployment OIDC authority before external activation.
- The first provider implementation still requires a separate reviewed storage,
  synchronization, policy, and reconciliation slice.
- Contract v1 intentionally omits attendees, recurrence rules, raw descriptions,
  and provider URLs; adding them requires a new reviewed contract revision.

## Activation gate

Runtime use by LineageWeave remains disabled until:

1. Naruon replaces the unconfigured provider with a real authorized read model;
2. LineageWeave #355 is merged and released as an immutable artifact;
3. both repositories run the same conformance fixture and media type;
4. service token issuance, timeout, degraded, revision, retry, and reconciliation
   cases pass;
5. exact-head security, coverage, review-thread, and protected merge gates pass.

## References

Daboo, C., Desruisseaux, B., & Dusseault, L. M. (2007). *Calendaring extensions
to WebDAV (CalDAV)* (RFC 4791). RFC Editor. https://doi.org/10.17487/RFC4791

Daboo, C., & Quillaud, A. (2012). *Collection synchronization for WebDAV*
(RFC 6578). RFC Editor. https://doi.org/10.17487/RFC6578

Desruisseaux, B. (2009). *Internet calendaring and scheduling core object
specification (iCalendar)* (RFC 5545). RFC Editor.
https://doi.org/10.17487/RFC5545

World Wide Web Consortium. (2013). *PROV-O: The PROV ontology*.
https://www.w3.org/TR/prov-o/
