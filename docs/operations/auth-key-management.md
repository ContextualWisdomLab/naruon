# Authentication and Key Management

## 확인된 사실 / Confirmed

- `backend/api/auth.py` no longer accepts public `X-User-*`,
  `X-Organization-*`, `X-Group-*`, or `X-Dev-Auth-Token` headers as runtime
  authentication material.
- Runtime authentication accepts only `Authorization: Bearer` compact session
  envelopes whose protected header pins `alg=HS256` and whose `header.payload`
  signing input is signed with HMAC-SHA256 by the configured
  `AUTH_SESSION_HMAC_SECRET`. The secret must be explicitly configured,
  high-entropy generated material, and at least 32 bytes. Settings fail at
  startup in every runtime mode when this secret is missing, too short, or an
  obvious repeated placeholder or known public fixture value; runtime
  verification still fails closed with `401 Authentication required` when an
  already-loaded configured value becomes absent, weak, or public.
- The signed session payload is versioned and must include
  `iss=naruon-control-plane`, `aud=naruon-api`, `sub`, explicit `role`,
  `workspace`, `exp`, and organization/group scope claims. Tampered, expired,
  malformed, wrong-secret, wrong-algorithm, legacy two-segment, or invalid-role
  tokens are rejected; user ids such as `admin` do not grant privileges unless
  the signed role claim is elevated.
- Token issuers must mint the compact `header.payload.signature` form before this
  verifier rolls out, or the rollout must intentionally expire all legacy
  two-segment sessions.
- Local smoke tests must generate a fresh local-only `AUTH_SESSION_HMAC_SECRET`
  instead of copying a static fixture from docs or tests; reusable public fixture
  secrets are denied by configuration and runtime verification.
- Endpoint tests that need fixture identity use explicit FastAPI dependency
  overrides in `backend/tests/conftest.py`; those test overrides are not the
  production auth path.
- `backend/db/models.py` stores OAuth/OpenAI secret fields through an
  `EncryptedString` type backed by Fernet.
- `backend/db/models.py` no longer contains a fallback Fernet key or SHA256
  passphrase-derivation path. Secret-field encryption now requires an explicit
  valid Fernet `ENCRYPTION_KEY` in every runtime mode, including `DEBUG=true`.
  Decryption failures return `None` instead of ciphertext; user-facing routes
  that touch encrypted fields should return the existing operator-facing
  missing-key or unavailable-secret error rather than fallback encryption or raw
  encrypted blobs.
- Email rows now have nullable `user_id` and `organization_id` owner keys, and
  email/search/network graph queries are scoped to the authenticated user plus
  organization. Managed environments apply schema changes through
  `backend/scripts/migrate_db.py`; `backend/scripts/bootstrap_db.py` remains a
  local compatibility path for idempotent backfills. Production still needs an
  audited mailbox-owner and organization migration/backfill before multi-tenant
  data is mixed.
- Email `message_id` uniqueness, fixture import upserts, and reply-thread lookup
  are scoped by `user_id` plus `organization_id` so reused RFC Message-ID values
  cannot cross tenant boundaries.
- `DATABASE_URL` has no code default. Every runtime, test harness, and deployment
  path must inject the database URL explicitly instead of relying on a shared
  development credential fallback.
- Tenant SMTP hosts are accepted only when the operator has placed the normalized
  hostname in `ALLOWED_SMTP_HOSTS`, the port is in `ALLOWED_SMTP_PORTS`, and the
  final send-time DNS answers are globally routable. Localhost, metadata,
  private, link-local, reserved, multicast, and otherwise non-global addresses
  are rejected before the backend opens a pinned SMTP socket.

## 가설 / Hypothesis

- Keycloak and Casdoor should be evaluated as OIDC providers before production
  multi-user access is claimed. The HMAC session envelope is a narrow internal
  bridge, not the final external IdP integration.
- Production still needs key rotation runbooks and separate secret scopes for
  `AUTH_SESSION_HMAC_SECRET`, OpenAI, SMTP/IMAP, OAuth, and CI tokens.

## Universal RBAC/ABAC contract

- Roles such as SaaS admin, enterprise admin, security operator, IT operator,
  B2B2C tenant admin, B2C member, SOHO owner, and delegated support engineer are
  authorization inputs, not final decisions by themselves.
- ABAC denies for data region, consent, workspace/group scope, provider
  capability, legal hold, and customer policy must take precedence over RBAC
  allows.
- `platform_admin` is the only cross-tenant exception in the pure resource access
  evaluator: when `platform_admin` is explicitly present in `permitted_roles`, it
  may bypass organization and resource ownership/delegation checks for platform
  operations. That exception does not bypass data-region, consent, provider
  capability, legal hold, or customer-policy denies.
- `ResourcePolicy.data_region = None` means the resource has no residency
  restriction. A request with `data_region = None` does not satisfy a resource
  that declares a concrete data region.
- Runtime claims must be signed and server-verifiable. Public headers from
  browsers or edge proxies are not identity material unless they are backed by a
  validated OIDC/JWT or internal signed session envelope.
- Private FastAPI `/api/*` routers are included with a default
  `get_auth_context` dependency so authentication is deny-by-default at router
  registration time. Public endpoints must be explicit exceptions, currently
  `/`. Runtime feature/configuration endpoints stay signed-session protected.
  Prometheus `/metrics` is opt-in and must stay behind a trusted scrape path or
  reverse proxy access policy when enabled.
- Authentication is not sufficient for privileged control-plane resources: LLM
  provider registry reads and writes require `platform_admin` or
  `organization_admin` signed role claims.
- The browser API client uses same-origin credentials and strips public identity
  headers (`X-User-Id`, `X-Organization-Id`, `X-Group-Id`, `X-Group-Ids`,
  `X-User-Role`, `X-Dev-Auth-Token`) from caller-provided request headers so
  copied frontend code cannot reintroduce the development-header trust boundary.
- Caller-provided `Authorization` is also discarded by the browser API client.
  Only the same-origin Next.js `/api/*` proxy may translate the HttpOnly
  `naruon_session` cookie into a backend `Authorization: Bearer` session.
- When `NEXT_PUBLIC_OIDC_ISSUER_URL` and `NEXT_PUBLIC_OIDC_CLIENT_ID` are set,
  the browser can start an Authorization Code + PKCE login against the configured
  Keycloak/Casdoor issuer. The same-origin `/auth/oidc/*` server routes keep
  PKCE verifier state in an HttpOnly transient cookie, exchange the callback
  code server-side, verify the resulting token with the backend, and then install
  only the HttpOnly `naruon_session` cookie for private API calls. Public
  endpoint overrides may be supplied with
  `NEXT_PUBLIC_OIDC_AUTHORIZATION_ENDPOINT`, `NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT`,
  `NEXT_PUBLIC_OIDC_END_SESSION_ENDPOINT`, `NEXT_PUBLIC_OIDC_REDIRECT_URI`, and
  `NEXT_PUBLIC_OIDC_SCOPE`; otherwise Keycloak's
  `/protocol/openid-connect/{auth,token,logout}` endpoints are derived from the
  issuer URL.
- Browser-side OIDC support does not mint local roles. The IdP token must still
  satisfy the backend's signed claim contract: verified issuer/audience, subject,
  explicit non-platform role, organization, groups, workspace, expiry, and no
  unsupported critical headers.

## Keycloak/Casdoor decision path

- Keycloak is the default enterprise candidate when realm federation, identity
  brokering, authorization services, admin separation, and audit requirements are
  more important than footprint.
- Casdoor remains the lighter candidate when a deployment values simpler
  self-hosting, Casbin-style policy integration, and lower operational overhead.
- Either option must preserve Naruon's signed claim contract: explicit subject,
  organization, group/workspace, role, delegation, expiry, and provider/source
  ownership claims are required before production multi-user access is claimed.

## 다음 결정

- Compare Keycloak and Casdoor on OIDC support, operational complexity, admin UX,
  self-hosting footprint, backup/restore, and integration with gateway auth.
- Complete production IdP onboarding runbooks and key rotation procedures while
  keeping regression tests that prove every email/search/network query path is
  scoped to the authenticated mailbox owner and organization.
