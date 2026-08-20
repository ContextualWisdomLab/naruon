# Doctoring: Noema gateway settings

## Change under review

The signed-session `GET`/`PUT /api/noema-gateway` route configures the existing
per-user contextual-orchestrator gateway without exposing the gateway token.
It is a control-plane settings surface, not a mailbox credential surface and
not an organization-wide delegation API.

## Evidence-backed controls

| Control | Implementation evidence | Customer/operational action |
|---|---|---|
| Authenticated subject boundary | The route depends on the verified `AuthContext` and resolves `TenantConfig` with both `user_id` and `organization_id`. | Sign in to the intended organization before saving the gateway; do not reuse a token across organizations. |
| Credential confidentiality | `noema_orchestrator_token` uses the existing `EncryptedString` Fernet type; responses expose only `has_token`, and audit text is generic. | Confirm readiness from `has_token`; never paste the gateway token into support tickets or logs. |
| Endpoint validation | The URL must be HTTPS, end in `/v1`, pass the existing host allowlist, and resolve to global addresses. | Add the gateway host to the approved allowlist before saving it; a rejected URL is an actionable setup error. |
| Accountability | Successful updates create both `AuditLog` and `SecurityAuditEvent` records with a stable opaque resource UID and no token value. | Use the security audit surface to verify who changed the gateway and when. |
| Fail-closed behavior | Missing URL/token, malformed URL, control characters, invalid fields, and encryption-root failures return controlled errors; runtime resolution already fails closed. | Resolve the returned setup error before retrying Noema; do not bypass validation with environment keys. |

These controls are aligned with the OWASP Application Security Verification
Standard's use as a verification baseline for web application security controls
(OWASP Foundation, 2025) and with NIST's current authentication and authenticator
management guidance (National Institute of Standards and Technology, 2025). This is an implementation mapping,
not a claim that Naruon is certified or conforms to every requirement in either
publication.

## Test evidence

`backend/tests/test_noema_config_api.py` covers ready/unready state, malformed
and unallowlisted URLs, omitted/masked/null token preservation, control
characters, extra fields, no-setting updates, token non-disclosure, generic
audit content, encryption-root failure, and unexpected database errors. The
module reaches 100% line coverage under the focused coverage command. The full
backend suite passes with warnings treated as errors.

## References (APA 7th)

National Institute of Standards and Technology. (2025, July). *Digital identity
guidelines: Authentication and authenticator management* (NIST Special
Publication 800-63B-4). https://doi.org/10.6028/NIST.SP.800-63B-4

OWASP Foundation. (2025). *OWASP Application Security Verification Standard
5.0.0*. https://owasp.org/www-project-application-security-verification-standard/
