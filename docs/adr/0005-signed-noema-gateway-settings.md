# ADR-0005: Signed-session Noema gateway settings

- **Status:** Proposed
- **Date:** 2026-08-20
- **Scope:** Naruon's per-user Noema gateway settings API
- **Figma:** Not applicable; this slice is a backend control-plane contract and
  adds no visual surface.

## Context

ADR-0004's Noema runtime path reads a dedicated gateway URL and Fernet-protected
token from the scoped `tenant_configs` record, but operators had no product API
to configure those values. Adding the fields to the mailbox self-service schema
would blur credential ownership and make a future frontend send unrelated mail
settings together with an inference credential.

## Decision

Naruon exposes `GET` and `PUT /api/noema-gateway` for the authenticated signed
session's `(user_id, organization_id)` scope. The route:

1. validates an HTTPS `/v1` URL through the existing allowlist and global-address
   transport policy;
2. stores the gateway token through the existing `EncryptedString` Fernet KV;
3. returns only `base_url`, `configured`, and `has_token`;
4. writes generic `AuditLog` and `SecurityAuditEvent` records without token
   values; and
5. preserves the existing single-alias contextual-orchestrator runtime contract.

The route does not accept a target user, does not manage mailbox credentials,
does not read environment provider keys, and does not add an organization-wide
fallback that would change Noema's existing per-user scope. A frontend must
omit blank secret fields when preserving a stored token.

## Consequences

Users can complete the gateway setup from a signed-session settings surface,
and operators can distinguish unconfigured gateway state without seeing a
credential. Organization-wide administration and frontend presentation remain
separate follow-up decisions because they require an explicit membership and
delegation contract.

## Verification

`backend/tests/test_noema_config_api.py` covers readiness responses, token
non-disclosure, audit records, URL rejection, empty updates, and extra-field
rejection. The focused Noema suite must pass with warnings treated as errors.
