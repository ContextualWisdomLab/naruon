# LineageWeave Calendar Projection Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement each task with test-first verification.

**Goal:** Publish the Naruon provider side of the strict calendar observation contract consumed by LineageWeave while remaining explicitly unavailable until real inbound provider evidence exists.

**Architecture:** Add a dedicated service-to-service router outside the browser user-auth dependency, verify an exact RS256 OIDC audience/scope using startup-cached signing keys, define immutable strict response models and a provider port, and keep the production default fail-closed. No event store or synthetic provider result is introduced.

**Tech Stack:** Python 3.14 target, FastAPI, Pydantic v2, PyJWT RS256, JSON Schema Draft 2020-12, pytest, existing OIDC signing-key cache.

**Spec:** `docs/adr/0005-lineageweave-calendar-projection-provider.md`

## Global Constraints

- Browser/end-user tokens and service tokens use different audiences.
- Provider credentials, sync tokens, DAV payloads, and private calendar content never enter the cross-service response.
- The route returns explicit unavailable state until a real normalized provider read model exists.
- Windows are at most 366 days and pages at most 200 occurrences.
- Opaque references, cursors, timestamps, vocabularies, and response media types are strict and versioned.
- External events are `observed`; they cannot mutate Naruon or LineageWeave state.
- Changed production statement/branch coverage and public docstrings must reach 100%.

---

### Task 1: Service-audience authentication

**Files:**
- Create: `backend/tests/test_calendar_projection_service_auth.py`
- Create: `backend/api/calendar_projection_auth.py`

**Interfaces:**
- Produces: `decode_calendar_projection_service_token(token) -> CalendarProjectionServiceContext`.
- Produces: `get_calendar_projection_service_context()` FastAPI dependency.

- [ ] Write failing tests using a real RS256 token and cached PyJWK fixture.
- [ ] Cover exact audience, required `calendar:read` scope, tenant/workspace claims, missing OIDC, and duplicate key identity.
- [ ] Run the focused test and confirm failure is caused by the missing module.
- [ ] Implement strict bearer extraction, cached-key selection, issuer/audience/signature verification, opaque claim validation, and rate-limit integration.
- [ ] Re-run focused tests until green and verify no token or claim value appears in errors.

### Task 2: Provider contract and fail-closed route

**Files:**
- Create: `backend/tests/test_calendar_projection_contract.py`
- Create: `backend/tests/test_calendar_projection_api.py`
- Create: `backend/services/calendar_projection.py`
- Create: `backend/api/calendar_projection.py`
- Modify: `backend/main.py`

**Interfaces:**
- Produces: `CalendarProjectionOccurrence` and `CalendarProjectionPage`.
- Produces: `CalendarProjectionProvider.list_events(...)` port.
- Produces: `GET /api/calendar/events` with the v1 vendor media type.

- [ ] Write failing model tests for exact strings, timestamps, interval ordering, closed vocabularies, duplicate occurrences, page bounds, and cursor safety.
- [ ] Write failing route tests proving service auth is present, user auth is absent, invalid queries do not call the provider, and unavailable returns 503.
- [ ] Run the focused tests and confirm failure is caused by the missing contract/route.
- [ ] Implement immutable Pydantic models, exact RFC 3339 parsing, cursor validation, and a provider protocol.
- [ ] Implement the unconfigured production provider that always raises unavailable.
- [ ] Register the service router separately from `PRIVATE_API_DEPENDENCIES`.
- [ ] Re-run focused tests until green.

### Task 3: Cross-repository contract evidence

**Files:**
- Create: `docs/contracts/naruon-calendar-projection-v1.schema.json`
- Create: `docs/adr/0005-lineageweave-calendar-projection-provider.md`
- Modify: `docs/adr/README.md`
- Create: `docs/product-technical-gap-baseline.md`
- Create: `docs/changes/2026-08-21-lineageweave-calendar-projection-provider.md`

**Interfaces:**
- Produces: one provider schema that LineageWeave PR #355 consumes.

- [ ] Add a schema drift test against runtime model fields and limits.
- [ ] Record authority, service token, unavailable-state, and activation decisions in ADR-0005.
- [ ] Record the exact open integration gaps and current PR queue observation in the canonical product/technical baseline.
- [ ] Add a release-note fragment that explicitly says inbound provider data is not implemented.
- [ ] Validate JSON syntax, ADR index, documentation links, compileall, Ruff, and diff hygiene.

### Task 4: Review and protected delivery

**Files:**
- No additional product file unless review finds a defect.

**Interfaces:**
- Consumes: exact-head hosted checks and independent review.
- Produces: a mergeable contract PR; it does not produce runtime activation.

- [ ] Open a Draft PR from protected `develop` and link Naruon #1437, #978, #998, LineageWeave #336/#355.
- [ ] Fetch every exact-head check, review, and unresolved thread.
- [ ] Fix actionable findings using new failing regressions before implementation changes.
- [ ] Mark Ready only after focused verification evidence exists.
- [ ] Enable auto-merge only when the repository ruleset and exact-head evidence permit it.
- [ ] Keep LineageWeave runtime consumption disabled until the real inbound provider slice is separately merged and released.
