# Naruon Commercial Pilot Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current Naruon frontend slice repeatably demonstrable as a paid pilot product without claiming public launch readiness.

**Architecture:** Keep the existing Next frontend as the product surface. Add a committed pilot smoke harness that exercises `/mail` and `/search` against deterministic mocked local API responses while preserving the privacy-safe local product-event dispatcher. Document the commercial-pilot line separately from public-launch caveats.

**Tech Stack:** Next 16, React 19, TypeScript, Vitest, Playwright, local Next dev/preview server, Markdown.

---

### Task 1: Lock The Commercial Pilot Definition

**Files:**
- Create: `docs/superpowers/specs/2026-07-02-naruon-commercial-pilot-readiness-design.md`
- Create: `docs/superpowers/plans/2026-07-02-naruon-commercial-pilot-readiness.md`
- Modify: `docs/superpowers/reports/2026-07-02-naruon-design-to-code-telemetry-qa.md`

- [x] **Step 1: Define pilot-ready versus public-launch-ready**

  Record that this slice may be sold as a controlled paid pilot only when the local frontend demo, privacy-safe events, tests, build, and browser smoke pass.

- [x] **Step 2: List explicit public-launch caveats**

  Caveats must include hosted deployment, real auth/tenant audit, provider send, live backend/private mailbox integration, external analytics governance, billing/legal review, SLA, and support process.

- [x] **Step 3: Update QA report with commercial-pilot wording**

  Add a “Commercial Pilot Readiness” section that says the slice is pilot-demo ready after all gates pass, but not public-launch ready.

### Task 2: Add Repeatable Browser Smoke Harness

**Files:**
- Create: `frontend/scripts/pilot-ui-smoke.mjs`
- Modify: `frontend/package.json`

- [x] **Step 1: Add `pilot:smoke` npm script**

  Add this script:

  ```json
  {
    "pilot:smoke": "node scripts/pilot-ui-smoke.mjs"
  }
  ```

- [x] **Step 2: Implement deterministic API mocks**

  The smoke harness must intercept:

  - `/auth/session`
  - `/api/network/graph`
  - `/api/emails`
  - `/api/emails/23`
  - `/api/emails/thread/source-thread`
  - `/api/llm/summarize`
  - `/api/llm/draft`
  - `/api/emails/send`
  - `/api/tasks/from-email`
  - `/api/calendar/writeback-intent`
  - `/api/search`
  - `/api/ontology/relationships`
  - `/api/ontology/relationships/capture-source`
  - `/api/tasks`
  - `/api/calendar/writeback-sources`
  - `/api/webdav/folders`

- [x] **Step 3: Exercise the mail flow**

  The harness must verify:

  - inbox item visible
  - detail opens
  - source drawer opens
  - close button and Escape close work
  - draft generation fills `답장 초안`
  - simulated send clears draft and shows send status
  - task creation shows task status
  - calendar writeback intent shows calendar status
  - required mail events exist
  - event JSON does not include the sensitive mail body or draft body

- [x] **Step 4: Exercise the search flow**

  The harness must verify:

  - default result opens
  - query submit opens a new result
  - relationship capture creates a relationship card
  - required search events exist
  - event JSON does not include the raw query

- [x] **Step 5: Save screenshots outside the repo**

  Save:

  - `/tmp/naruon-pilot-mail.png`
  - `/tmp/naruon-pilot-search.png`

### Task 3: Tighten Component Tests For Pilot Flow

**Files:**
- Modify: `frontend/src/components/EmailDetail.test.tsx`
- Modify: `frontend/src/components/SearchLayout.test.tsx`
- Modify: `frontend/src/lib/product-events.test.ts`

- [x] **Step 1: Ensure mail tests cover drawer, draft, send, task, calendar events**

  The existing test file must assert each event is emitted at least once and no raw sensitive text appears in recorded product events.

- [x] **Step 2: Ensure search tests cover submit, result open, action create**

  The existing search test must assert no raw query appears in recorded product events.

- [x] **Step 3: Ensure product-event tests reject non-contract fields**

  `recordProductEvent` must reject arbitrary fields that are not in the selected event contract.

### Task 4: Run Release Gates

**Files:**
- Read: `frontend/package.json`
- Read: smoke screenshots in `/tmp`

- [x] **Step 1: Run unit/component tests**

  ```bash
  pnpm --dir frontend test
  ```

  Expected: all tests pass.

- [x] **Step 2: Run typecheck**

  ```bash
  pnpm --dir frontend typecheck
  ```

  Expected: `tsc --noEmit` exits 0.

- [x] **Step 3: Run production build**

  ```bash
  pnpm --dir frontend build
  ```

  Expected: optimized Next build succeeds.

- [x] **Step 4: Run pilot browser smoke**

  ```bash
  pnpm --dir frontend pilot:smoke
  ```

  Expected: mail/search smoke passes, no console errors or warnings, screenshots are written under `/tmp`.

- [x] **Step 5: Run diff and event scans**

  ```bash
  git diff --check
  rg -n "context_synthesis_viewed|source_chip_opened|action_item_created|calendar_reflected|draft_reply_generated|draft_reply_inserted|draft_reply_sent|context_search_submitted|context_search_result_opened|context_search_result_action_created|latency_guardrail_recorded|model_quality_guardrail_recorded|trust_safety_guardrail_triggered" frontend/src docs/superpowers design-qa.md
  rg -n "TBD|TODO|FIXME|contract only|proposed only|not instrumented|public launch ready|live KPI" docs/superpowers design-qa.md frontend/src || true
  ```

  Expected: diff check passes, required events are present, and placeholder scan has no unqualified launch claims.

### Task 5: Completion Audit And Handoff

**Files:**
- Read: `git status --short --branch`
- Read: test command outputs
- Read: `/tmp/naruon-pilot-mail.png`
- Read: `/tmp/naruon-pilot-search.png`

- [ ] **Step 1: Verify branch and preserved user changes**

  Confirm work is on `sellable-pilot-hardening-2026-07-02` and `.Jules/palette.md`, `.Jules/sentinel.md` remain preserved.

- [ ] **Step 2: Summarize pilot-ready versus public-launch caveats**

  Final response must not claim live KPI values or public launch readiness.

- [ ] **Step 3: Present finishing options**

  Present PR/merge/keep/discard options after all gates pass.
