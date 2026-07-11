# Naruon 20B Security Questionnaire Draft

Date: 2026-07-02 KST

## Status

Draft for buyer security review. This is not a signed legal, compliance, or DPA response.

## Summary Answers

| Question | Draft answer | Evidence | Status |
| --- | --- | --- | --- |
| What is Naruon? | Customer-owned AI workspace and control plane for mail, calendar, files, tasks, search, AI workflows, and governance. | `README.md`, `docs/architecture/naruon-product-spec.md` | Draft |
| Does Naruon host buyer mailboxes? | Current architecture treats customer-owned mail/file/calendar systems as source systems; Naruon is not positioned as the mailbox host in this package. | `docs/operations/email-relay-proxy-boundary.md`, `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md` | Draft |
| How is authentication handled? | Backend accepts signed bearer sessions and rejects unsupported critical headers. | `backend/api/auth.py`, `backend/tests/test_auth_real.py` | Implemented, buyer env proof pending |
| How is authorization handled? | RBAC/ABAC policy logic exists and is tested. | `backend/core/rbac.py`, `backend/tests/test_rbac.py`, `backend/tests/test_access_policy.py` | Implemented, buyer policy mapping pending |
| Are provider writes automatic? | Provider-write paths must be explicit, intent-based, and audited. The current buyer package does not claim all live provider-write paths are production-proven. | `backend/services/`, `frontend/scripts/full-product-ui-smoke.mjs` | Caveated |
| Is analytics privacy-safe? | Pilot product events block sensitive raw text fields and are local-only in the current implementation. | `frontend/src/lib/product-events.ts`, `frontend/src/lib/product-events.test.ts` | Mail/search covered |
| Are live KPIs available? | No. The KPI model is defined, but live measured data is required before ROI claims. | `docs/superpowers/reports/2026-07-02-naruon-kpi-validation.md` | Not complete |
| Is CI/security gating enforced? | Branch-level PR governance patch now fails closed on blocker comments, but issue #634 remains open until trusted-base remote proof exists. | `docs/superpowers/reports/2026-07-02-naruon-security-governance-followup.md` | Branch fix |
| Is production deployment proven? | Not in this package. Deployment and rollback proof must be attached before final procurement. | `docs/operations/`, `.github/workflows/` | Not complete |
| Is incident response documented? | Draft support/SLA package exists; formal incident response requires buyer/operator approval. | `docs/superpowers/reports/2026-07-02-naruon-20b-sla-support-draft.md` | Draft |

## Data Handling Draft

Data categories in scope:

- Mail metadata and message content selected by the customer.
- Calendar event metadata selected by the customer.
- File/document metadata and content selected by the customer.
- Task and project metadata generated from customer-owned sources.
- Product-event telemetry for pilot flows, without raw sensitive text.

Processing boundaries:

- Use source-grounded displays for buyer-visible actions.
- Avoid copying raw private body text into product analytics payloads.
- Treat provider-send and provider-write execution as explicit user or admin actions.
- Keep customer-owned sources as systems of record unless a buyer contract says otherwise.

Open approvals:

- DPA and data retention schedule.
- Tenant-specific subprocessors.
- External analytics destination and retention period.
- Production log redaction policy.
- Support access and impersonation policy.

## Access Control Draft

Implemented or present:

- Signed bearer-session boundary in backend auth.
- RBAC/ABAC policy tests.
- Security dashboard surface.
- Provider secret handling UI language in settings.

Needs buyer-specific proof:

- Tenant role matrix.
- SSO/IdP integration proof.
- Admin break-glass policy.
- Support access audit policy.
- Production audit-log retention and export path.

## Secure Development And CI

Current evidence:

- Application CI.
- Bandit.
- Trivy.
- CodeQL.
- Scorecard.
- Dependency review.
- Strix security scan.
- PR governance gate.

Important caveat:

Issue #634 showed a historical governance failure mode. This branch patches the central script, but final closure requires trusted-base remote evidence after merge.

## Procurement Caveats

The following must be disclosed before a final 20B KRW procurement claim:

- Production deployment and rollback proof not attached.
- Live provider-send and provider-write proof incomplete.
- External analytics governance not approved.
- DPA, retention, support, and incident terms are drafts.
- Full responsive Product Design QA is incomplete.
- Measured ROI is not available until a live pilot.
