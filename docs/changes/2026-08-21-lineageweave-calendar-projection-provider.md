# LineageWeave calendar projection provider contract

## Added

- Add a dedicated service-authenticated `GET /api/calendar/events` contract with
  the exact `naruon-calendar.v1+json` media type.
- Verify RS256 service tokens against startup-cached OIDC signing keys using the
  separate `naruon-calendar-read` audience and required `calendar:read` scope.
- Add strict immutable provider response models, JSON Schema Draft 2020-12,
  opaque references/cursors, offset-aware clocks, page/window bounds, and
  stable unavailable/request error codes.
- Register the route outside the browser/end-user authentication dependency so
  a user session cannot be mistaken for a service credential.

## Product truth

- The production provider remains intentionally unconfigured and returns
  `503 calendar_projection_unavailable`.
- This change does not add inbound CalDAV synchronization, an event store,
  recurrence reconciliation, provider credentials, or LineageWeave runtime
  activation.
- A later slice must provide the normalized occurrence read model, provider
  revision and disclosure evidence, retry/reconciliation receipts, and immutable
  provider/consumer fixtures before the endpoint can return real observations.
