# Naruon 20B Full Commercial Readiness Design

## Purpose

This spec defines the standard for treating Naruon as a program that can be submitted for a 2,000,000,000 KRW enterprise sale review. It intentionally raises the bar above the current PR #893 frontend pilot slice.

The target state is not "a useful demo." The target state is a buyer-reviewable product package with working product flows, production deployment evidence, tenant/security proof, analytics definitions, design evidence, support operations, and commercial handoff material.

## Explicit Boundary

Current PR #893 proves a controlled frontend pilot slice for `/mail` and `/search`. It does not prove the whole Naruon program is ready for final enterprise procurement, public launch, or a 2,000,000,000 KRW contract close.

For this spec, Naruon is 20B-commercial-ready only when every gate in this document has current evidence. A delayed review process, stale review decision, or `opencode-review` wait state is not a blocker. A failing CI job, missing production path, missing security proof, missing Figma evidence, or missing buyer handoff artifact is a blocker.

## Plugin Roles

### Figma

Use Figma for source-map repair, product IA boards, reusable component maps, desktop/mobile screen coverage, interaction states, QA screenshots, and buyer-demo review boards.

Rules:

- Do not use Figma Code Connect.
- Call `search_design_system` with `disableCodeConnect=true`.
- Treat `docs/ui-ux/mockups/*.png` and `docs/ui-ux/naruon-ui-ux-mapping.md` as the visual source of truth until a newer approved design file is provided.
- Current Figma file: `https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK`.
- Current live metadata observation on 2026-07-02 KST: only top-level page `Source Map` is visible through `get_metadata`; design-system search returned no components, variables, or styles. The first Figma task is therefore file-structure repair or a new verified replacement file.

### Product Design

Use Product Design for screenshot-backed flow audits, UX findings, accessibility risks, and design QA. Do not accept opinion-only reviews. Every finding must reference a captured screen, Figma node, or local screenshot.

Required audited buyer flows:

1. Login or signed-session entry.
2. Home decision dashboard.
3. Mail thread selection, `맥락 종합`, evidence drawer, `판단 포인트`, `답장 초안`, `실행 항목`, `일정 반영`.
4. Context search, result detail, relation capture, source backlink.
5. Calendar coordination and provider-write intent.
6. Data document store, ingestion, embedding, and quality controls.
7. AI Hub prompt/workflow execution and run history.
8. Security access control, audit log, policy posture, and external sharing.
9. Settings members, connected accounts, notifications, automation, billing, and developer/API areas.

### Superpowers

Use Superpowers to keep this work goal-backed, plan-backed, task-oriented, and verified before any completion claim.

Required Superpowers artifacts:

- Design spec under `docs/superpowers/specs/`.
- Implementation plan under `docs/superpowers/plans/`.
- Evidence reports under `docs/superpowers/reports/`.
- Fresh verification output before claiming completion.

### Ponytail

Use Ponytail as the architecture guardrail. Prefer existing code, existing scripts, current monorepo boundaries, platform primitives, and already-installed dependencies.

Library split decision:

- Do not introduce a new submodule now.
- Do not split a separate published library now.
- Keep shared frontend product-event and UI primitives in the existing `frontend/src/lib` and `frontend/src/components/ui` boundaries until there are at least three independent consumers, a separate release cadence, or cross-repo ownership.
- If extraction becomes necessary, prefer an internal workspace package under `frontend/packages/` before a git submodule. A submodule is acceptable only when the extracted code has independent ownership, independent versioning, and a stable public API.

### Data Analytics

Use Data Analytics for KPI definitions, ROI assumptions, funnel/guardrail design, and evidence caveats. No live KPI value may be claimed without a live source of truth.

Required analytics outputs:

- Event dictionary with privacy-safe payloads.
- Funnel metrics and guardrails.
- Pilot success criteria.
- Buyer ROI model with assumptions separated from measurements.
- Data-quality and source-of-truth caveats.

## Product Completion Standard

### Gate 1: Buyer-Visible Product Coverage

All ten IA areas from `docs/ui-ux/naruon-ui-ux-mapping.md` must have buyer-reviewable UI coverage:

| Area | Completion requirement |
| --- | --- |
| Home | Decision points, pending tasks, recent mail, calendar conflict, and quick execution actions render with real or deterministic signed data. |
| Mail | Inbox, thread detail, context synthesis, evidence drawer, draft reply, action item, calendar reflection, attachment/source context, and provider-send boundary are visible and testable. |
| Calendar | Month/week/detail, schedule candidates, conflict state, source mail backlink, and provider-write intent are visible and testable. |
| Tasks | My tasks, delegated tasks, task detail, status change, assignee change, due date change, and source backlink are visible and testable. |
| Projects | Project list/detail, milestones, decision log, related mail/document/task links, and source-backed project boundaries are visible and testable. |
| Context Search | Search, filters, result detail, relation graph/timeline, source detail, and downstream action creation are visible and testable. |
| Data | Document store, ingestion, embedding, quality checks, WebDAV materialization intent, and raw-content privacy rules are visible and testable. |
| AI Hub | Prompt studio, workflow canvas, agent/run detail, evaluation, execution history, and logs are visible and testable. |
| Security | Access control, audit logs, policies, external sharing, permission changes, and security posture evidence are visible and testable. |
| Settings | Workspace, members, connected accounts, notifications, automation, billing, developer/API keys, and webhook controls are visible and testable. |

### Gate 2: Real Integration Boundaries

The product must clearly separate these execution modes:

- deterministic local pilot mode
- private mailbox test mode
- production signed-session mode
- provider-write intent mode
- executed provider-write mode

For a 20B commercial package, mock-only success is not enough. Each provider boundary must have either current live evidence or an explicit buyer-facing caveat:

- IMAP/POP import and private mailbox ingestion
- SMTP or provider send
- CalDAV/CardDAV read/write
- WebDAV document materialization
- LLM provider selection and allowlisted outbound calls
- embedding generation and search
- OIDC or signed-session membership proof
- RBAC/ABAC deny-first authorization
- audit-event durability

### Gate 3: Security And Compliance

Required evidence:

- Branch protection and required security gates are enforced.
- Issue #634 is either resolved or explicitly included as an open governance risk.
- Tenant isolation and workspace authorization are tested.
- Sequential ids and raw provider data are not exposed in buyer-facing APIs.
- Raw email body, raw draft body, raw search query, credentials, provider usernames, and raw mailbox paths are not emitted to analytics or logs.
- Security questionnaire draft exists.
- Data-processing, retention, audit-log, and incident-response terms exist.
- Support and escalation runbooks exist.

### Gate 4: Production Operations

Required evidence:

- Production deployment path with rollback instructions.
- Environment and secret setup guide.
- Backup and restore procedure.
- Observability dashboard or documented OpenTelemetry/APM path.
- Health checks for frontend, backend, database, connector, provider reachability, queue/retry workers, and model provider.
- Smoke tests for local, private-test, and production-like modes.
- Incident runbook and SLA draft.

### Gate 5: Figma And Product Design Evidence

Required Figma pages:

1. `Source Map`
2. `Foundations`
3. `Components`
4. `Desktop Screens`
5. `Mobile Screens`
6. `Interaction States`
7. `Sales Demo`
8. `QA Notes`

Required visual proof:

- Figma metadata shows all required pages.
- Screenshots exist for each required buyer flow.
- Product Design audit notes are tied to captured screenshots.
- QA finds no P0/P1/P2 layout, accessibility, copy, or interaction blockers.
- Korean UI terminology follows the Naruon vocabulary.
- No visible placeholder-only frames remain in buyer-demo screens.

### Gate 6: Data Analytics And ROI

Required evidence:

- Event dictionary is implemented or clearly marked as measurement-only.
- No sensitive raw text leaves the browser or backend without explicit approved policy.
- Funnel definitions exist for thread selected -> synthesis viewed -> source opened -> decision viewed -> action created.
- Guardrails exist for latency, model quality, source missing, discard/correction, permission denial, and provider-write failures.
- ROI model separates measured current data from assumptions.
- Pilot success criteria define a pass/fail decision a buyer can sign off.

### Gate 7: Commercial Handoff

Required buyer package:

- Product overview.
- Demo script.
- Deployment architecture.
- Security questionnaire responses.
- Data-processing and retention summary.
- SLA/support draft.
- Pilot acceptance criteria.
- Pricing/contract assumptions.
- Known caveats and excluded work.
- Evidence index linking PRs, screenshots, tests, Figma nodes, and reports.

## Completion Rule

Do not mark the 20B full-product goal complete until all gates above have current evidence. Passing PR #893, passing frontend tests, or creating a Figma first slice is useful evidence, but it is not sufficient.
