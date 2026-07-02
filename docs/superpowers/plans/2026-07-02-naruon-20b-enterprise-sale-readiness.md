# Naruon 20B KRW Enterprise Sale Readiness Plan

> Scope: This plan raises PR #893 from a controlled paid-pilot demo toward a buyer-reviewable enterprise sale package. It does not claim public SaaS launch readiness or guaranteed contract value.

## Goal

Prepare the current Naruon frontend slice so it can withstand a 2,000,000,000 KRW enterprise buyer technical review for the implemented `/mail` and `/search` workflows.

The acceptable outcome is not "the whole company can publicly launch Naruon." The acceptable outcome is "the reviewed slice is technically coherent, repeatably demonstrable, privacy-safe for the mocked pilot path, and honest about missing production-operating prerequisites."

## Completion Standard

- `/mail` proves context synthesis, source evidence review, draft generation, simulated send, task creation, and calendar intent without runtime failure.
- `/search` proves query submission, result detail, and sender relationship capture without runtime failure.
- Product events are local-only, contract-checked, and free of raw email body, raw draft body, and raw query text.
- Smoke tests cannot accidentally target staging or production; `NARUON_PILOT_BASE_URL` must remain localhost-only.
- `SourceDrawer` accessibility remains stable under single and multiple component instances.
- Local product-event history is bounded, so long-running sessions do not grow memory without limit.
- `event_id` generation is stable and does not double-prefix fallback IDs.
- Release gates pass: `test`, `typecheck`, `build`, `pilot:smoke`, `git diff --check`, required-event scan, and placeholder/launch-claim scan.
- PR #893 is updated with the hardening changes, while `.Jules/palette.md` and `.Jules/sentinel.md` remain untouched user changes.

## Implementation Tasks

### Task 1: Harden Runtime Safety

- [x] Restrict `frontend/scripts/pilot-ui-smoke.mjs` to localhost targets only.
- [x] Keep deterministic mocked local APIs for `/auth/session`, `/api/emails`, `/api/llm/*`, `/api/search`, `/api/ontology/*`, task, calendar, and WebDAV endpoints.
- [x] Make source drawer smoke selection resilient to duplicate text matches in the mail layout.

### Task 2: Harden Product Events

- [x] Reject raw sensitive fields and non-contract payload keys.
- [x] Keep events browser-local; do not add an external analytics destination.
- [x] Cap local product-event buffer to the most recent 200 events.
- [x] Normalize fallback event IDs so callers own the prefix exactly once.
- [x] Add regression coverage for local event buffer capping.

### Task 3: Harden Evidence Drawer Accessibility

- [x] Keep `role="dialog"` and `aria-modal="true"`.
- [x] Keep open focus on the close button, Escape close, backdrop/mouse close, scroll lock, and focus restore.
- [x] Generate per-instance title and description IDs with `useId()` to avoid duplicate ARIA targets.

### Task 4: Preserve The Sales Boundary

- [x] State that the current work supports buyer-reviewed controlled pilots, not public launch.
- [x] Keep public-launch blockers explicit: hosted deployment, tenant auth/audit, provider send, live mailbox integration, analytics governance, billing/legal, SLA, support, incident response, and data-processing terms.
- [x] Avoid live KPI or revenue claims unless backed by measured production data.

### Task 5: Gate And Publish

- [x] Run `pnpm --dir frontend test`.
- [x] Run `pnpm --dir frontend typecheck`.
- [x] Run `pnpm --dir frontend build`.
- [x] Run `pnpm --dir frontend pilot:smoke`.
- [x] Run `git diff --check`.
- [x] Run required-event and placeholder scans.
- [x] Commit only product changes, excluding `.Jules/*`.
- [x] Push `sellable-pilot-hardening-2026-07-02` and update PR #893.
- [ ] Re-check PR #893 status after push.

## Latest Gate Evidence

Executed on 2026-07-02 KST from branch `sellable-pilot-hardening-2026-07-02`:

- `pnpm --dir frontend test`: passed, 43 test files and 320 tests.
- `pnpm --dir frontend typecheck`: passed.
- `pnpm --dir frontend build`: passed, optimized Next 16 production build.
- `pnpm --dir frontend pilot:smoke`: passed, mail/search flows exercised, screenshots saved at `/tmp/naruon-pilot-mail.png` and `/tmp/naruon-pilot-search.png`.
- `git diff --check`: passed.
- required-event scan: passed; required product-event names appear in code/docs.
- placeholder/launch-claim scan: returned only guarded caveat language about live KPI and public-launch claims.
- screenshot file check: both pilot screenshots are 1440 x 1024 PNGs.

## Current Sale Readiness Position

The implemented slice can be presented as a controlled enterprise pilot for technical review when the gates above pass. It is not yet a full 20B KRW enterprise contract package without commercial artifacts, procurement terms, security questionnaire answers, DPA/legal review, production deployment, tenant isolation audit, provider-send verification, customer support motion, and SLA/incident process.

That distinction is part of the sellable package: the code slice demonstrates product value and engineering discipline; the remaining items are operating-company and deployment prerequisites.
