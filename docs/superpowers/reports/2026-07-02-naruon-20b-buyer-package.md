# Naruon 20B Buyer Package Index

Date: 2026-07-02 KST

## Positioning

Naruon is a customer-owned AI workspace for mail, calendar, files, task follow-up, search, and governance surfaces. This package supports a controlled enterprise buyer technical review. It is not a final public-launch or contract-close claim.

Current package status:

- Buyer-reviewable frontend pilot evidence exists for `/mail` and `/search`.
- A full-product localhost route smoke now covers `/`, `/mail`, `/search`, `/calendar`, `/tasks`, `/projects`, `/data`, `/ai-hub`, `/security`, and `/settings`.
- Figma Code Connect is not used.
- The Figma `Sales Demo / 20B Enterprise Review Flow` frame exists in file `68b5XB58w8nwT2LYOOnikK`, page `15:3`, frame `16:2`.
- PR #893 is the current implementation vehicle: `https://github.com/ContextualWisdomLab/naruon/pull/893`.

## Evidence Map

| Area | Current evidence | Status |
| --- | --- | --- |
| Product scope | `docs/superpowers/specs/2026-07-02-naruon-20b-full-commercial-readiness-design.md` | Defined, not complete |
| Current audit | `docs/superpowers/reports/2026-07-02-naruon-20b-current-state-audit.md` | Current caveats listed |
| Full route smoke | `frontend/scripts/full-product-ui-smoke.mjs` and `frontend/scripts/full-product-ui-smoke.test.mjs` | Localhost pass |
| Pilot smoke | `frontend/scripts/pilot-ui-smoke.mjs` and `frontend/scripts/pilot-ui-smoke.test.mjs` | Localhost pilot flow pass |
| Product events | `frontend/src/lib/product-events.ts` and `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md` | Mail/search covered |
| Design evidence | Figma file `68b5XB58w8nwT2LYOOnikK`, frame `16:2`; `docs/ui-ux/naruon-ui-ux-mapping.md` | First sales frame ready |
| Analytics | `docs/superpowers/reports/2026-07-02-naruon-kpi-validation.md` | Framework only, no live KPI claim |
| Security governance | `docs/superpowers/reports/2026-07-02-naruon-security-governance-followup.md` | Branch fix, merge evidence pending |
| Commercial caveats | `docs/superpowers/specs/2026-07-02-naruon-commercial-pilot-readiness-design.md` | Explicit |

## Buyer Demo Flow

Use `docs/superpowers/reports/2026-07-02-naruon-20b-demo-script.md`.

Primary story:

1. Open Naruon home and show context synthesis.
2. Review mail evidence and source drawer behavior.
3. Generate a reply draft without leaking private text to analytics payloads.
4. Convert source mail into an action item.
5. Search a buyer context and capture sender relationship evidence.
6. Show tasks, data, AI Hub, security, and settings as full-product surfaces.
7. Close with governance caveats and the acceptance plan.

## Architecture Summary

Evidence anchors:

- Frontend: `frontend/src/components/*Layout.tsx`
- API proxy: `frontend/src/app/api/[...path]/route.ts`
- Backend API: `backend/api/`
- Security and RBAC: `backend/core/rbac.py`, `backend/api/auth.py`
- Provider and writeback boundaries: `backend/services/`, `backend/api/calendar.py`, `backend/api/webdav.py`
- Operational docs: `docs/operations/`

Architecture posture:

- Customer-owned source systems remain the system of record.
- Naruon acts as a control plane and workflow surface.
- Provider-write actions must remain explicit and audited.
- Private text must not be copied into product analytics payloads.

## Deployment Status

Current evidence:

- CI workflows exist under `.github/workflows/`.
- Docker image validation jobs exist in `.github/workflows/docker-publish.yml`.
- Render and operations notes exist under `docs/operations/`.

Not yet complete:

- Production deployment proof is not packaged.
- Rollback evidence is not packaged.
- Live tenant environment acceptance evidence is not packaged.

## Security And Privacy Status

Use `docs/superpowers/reports/2026-07-02-naruon-20b-security-questionnaire.md`.

Current strengths:

- Signed session boundary exists in backend auth.
- RBAC/ABAC test coverage exists.
- Security dashboard surface exists.
- PR governance fail-closed patch exists in this branch.
- Product event contract blocks sensitive raw text fields.

Open caveats:

- Issue #634 remains open until trusted-base remote evidence proves the governance patch.
- Live provider-send and provider-write evidence is incomplete.
- Formal DPA, incident response, and support terms are drafts, not signed artifacts.

## Analytics And ROI Status

Use `docs/superpowers/reports/2026-07-02-naruon-kpi-validation.md`.

Current status:

- KPI definitions exist.
- Event dictionary exists.
- Local product events exist for mail/search.
- Full-product event coverage is not complete.
- No live ROI number should be claimed.

Accepted buyer-review language:

```text
Naruon has a measurement framework and local privacy-safe event contract for the pilot surfaces. Live KPI and ROI evidence require a measured pilot.
```

Rejected language:

```text
Naruon has proven a 20B KRW ROI.
Naruon is public-launch ready.
All provider integrations are production-proven.
```

## SLA And Support

Use `docs/superpowers/reports/2026-07-02-naruon-20b-sla-support-draft.md`.

Current status:

- Support/SLA package is a draft.
- Incident response and escalation policy still need owner approval.
- Buyer-specific uptime, RTO, RPO, and support hours must be negotiated.

## Pilot Acceptance Criteria

A buyer technical pilot can be accepted only if:

- Local and remote CI gates pass on the current head.
- Buyer demo script is executed without manual source edits.
- Browser smoke screenshots are produced for all ten routes.
- Security caveats are presented before procurement review.
- Live tenant/provider tests are either completed or explicitly excluded from the pilot scope.

## Known Caveats

This package is not complete for final procurement until:

- Production deployment and rollback evidence is attached.
- Live provider-send and provider-write paths are proven or contractually excluded.
- Security questionnaire, DPA, incident runbook, and SLA terms are buyer-approved.
- Full responsive Product Design QA is complete with no P0/P1/P2 blockers.
- ROI evidence comes from live measured data rather than assumptions.
- Issue #634 is closed after trusted-base remote evidence.
