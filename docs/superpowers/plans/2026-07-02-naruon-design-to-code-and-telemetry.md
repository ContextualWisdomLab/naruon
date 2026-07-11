# Naruon Design-To-Code And Telemetry Follow-Up Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Keep this file current by changing each checkbox from `[ ]` to `[x]` only after the step is verified.

**Goal:** Extend the completed Figma/Product Design/Data Analytics package into implementation-ready product code without using Figma Code Connect, without adding a new frontend library, without sending live analytics, and without claiming live KPI values.

**Architecture:** Treat the existing Next frontend as the implementation anchor. `EmailDetail.tsx`, `SearchLayout.tsx`, and the new `SourceDrawer.tsx` cover the first vertical slice. `frontend/src/lib/product-events.ts` provides a privacy-safe local dispatcher that validates the event contract, records events in memory, dispatches a browser-local `naruon:product-event` custom event, and does not send data to a network destination.

**Tech Stack:** Next 16, React 19, TypeScript, Vitest, Markdown, Figma MCP (`use_figma`, `get_metadata`, `get_screenshot`, `search_design_system` with `disableCodeConnect=true`).

## Global Constraints

- Do not use Figma Code Connect.
- Do not call Code Connect suggestion or mapping tools.
- Do not introduce a new analytics SDK or external event destination.
- Do not send raw email body, raw draft body, or raw search query text in product events.
- Preserve existing `.Jules/palette.md` and `.Jules/sentinel.md` modifications.
- Keep changes scoped to `docs/superpowers/`, `design-qa.md`, and the frontend event/source-drawer implementation.
- State clearly that live KPI values are unavailable.

## Task 1: Confirm Current Implementation Anchor

**Files:**
- Read: `frontend/src/components/EmailDetail.tsx`
- Read: `frontend/src/components/DecisionPointCard.tsx`
- Read: `frontend/src/lib/api-client.ts`
- Read: `frontend/package.json`

**Interfaces:**
- Consumes: existing mail-detail UI, action handlers, confidence utility, API client.
- Produces: implementation-scope decision for the follow-up package.

- [x] **Step 1: Verify branch and dirty state**

  Evidence:

  - Current worktree: `/Users/seonghobae/Documents/Codex/2026-07-02/https-github-com-contextualwisdomlab-naruon-figma/naruon`
  - Branch baseline: `develop`
  - Existing unrelated modifications: `.Jules/palette.md`, `.Jules/sentinel.md`
  - New package artifacts already under `docs/superpowers/` and `design-qa.md`

- [x] **Step 2: Verify CodeGraph availability**

  Evidence:

  - Deferred CodeGraph tools are not exposed in this session.
  - `.codegraph/` is not present in the worktree.
  - Because the user asked for autonomous execution, proceed with native repo reads and do not initialize CodeGraph without explicit confirmation.

- [x] **Step 3: Confirm first-slice UI coverage**

  Evidence from `EmailDetail.tsx` and `DecisionPointCard.tsx`:

  - `맥락 종합` card exists.
  - `실행 항목` card exists.
  - `답장 초안` flow exists.
  - `일정 반영` flow exists.
  - Confidence badge exists through `toConfidencePercent`.
  - Provenance/source chip pattern exists through `provenance` and `근거 원본 보기`.
  - Loading, empty, and error states exist.

- [x] **Step 4: Choose implementation slice**

  Decision:

  - Do not rebuild the UI.
  - Add a typed event contract and local dispatcher so the existing UI can be instrumented safely now.
  - Wire the first vertical slice in `EmailDetail.tsx` and `SearchLayout.tsx` without external analytics transport.
  - Use Figma for interaction-state frames and Product Design notes, not Code Connect.

## Task 2: Add Typed Product Event Contract

**Files:**
- Create: `frontend/src/lib/product-events.ts`
- Create: `frontend/src/lib/product-events.test.ts`

**Interfaces:**
- Consumes: event names from KPI validation and first vertical slice.
- Produces: strongly typed event names, contract metadata, payload fields, denominator grain, timezone, owner, privacy class, and quality caveat.

- [x] **Step 1: Define required event names**

  Required product events:

  - `context_synthesis_viewed`
  - `decision_point_viewed`
  - `source_chip_opened`
  - `action_item_created`
  - `calendar_reflected`
  - `draft_reply_generated`
  - `draft_reply_inserted`
  - `draft_reply_sent`
  - `context_search_submitted`
  - `context_search_result_opened`
  - `context_search_result_action_created`
  - `latency_guardrail_recorded`
  - `model_quality_guardrail_recorded`
  - `trust_safety_guardrail_triggered`

- [x] **Step 2: Define shared payload baseline**

  Every event contract must include:

  - `event_id`
  - `occurred_at`
  - `workspace_id`
  - `actor_user_id`
  - `surface`

- [x] **Step 3: Define per-event payload fields**

  Each event must define:

  - owner
  - trigger
  - denominator grain
  - timezone
  - privacy class
  - entity IDs
  - required/optional payload fields
  - quality caveat

- [x] **Step 4: Add test coverage**

  Tests must verify:

  - event names are exact and unique
  - timezone/owner/denominator/payload/caveat exists for every event
  - raw body and raw query fields are not allowed
  - `recordProductEvent` validates required fields before recording
  - local browser dispatch uses `CustomEvent("naruon:product-event")`
  - bucket helpers avoid raw body, draft, and query text

## Task 2A: Wire Product Events Into Current UI

**Files:**
- Modify: `frontend/src/components/EmailDetail.tsx`
- Modify: `frontend/src/components/SearchLayout.tsx`
- Modify: `frontend/src/components/EmailDetail.test.tsx`
- Create: `frontend/src/components/SearchLayout.test.tsx`

**Interfaces:**
- Consumes: product-event contract and current mail/search actions.
- Produces: privacy-safe local event records tied to real user actions.

- [x] **Step 1: Wire mail-detail events**

  Implemented in `EmailDetail.tsx`:

  - `context_synthesis_viewed`
  - `source_chip_opened`
  - `action_item_created`
  - `calendar_reflected`
  - `draft_reply_generated`
  - `draft_reply_inserted`
  - `draft_reply_sent`
  - `latency_guardrail_recorded`
  - `model_quality_guardrail_recorded`

- [x] **Step 2: Wire context-search events**

  Implemented in `SearchLayout.tsx` because current results expose stable IDs through `result.id` and source-message IDs:

  - `context_search_submitted`
  - `context_search_result_opened`
  - `context_search_result_action_created`
  - `latency_guardrail_recorded`

- [x] **Step 3: Preserve privacy constraints**

  Implemented by contract validation and tests:

  - raw email body keys are rejected
  - raw draft body keys are rejected
  - raw search query keys are rejected
  - query and draft contents are represented by buckets and IDs only

## Task 2B: Implement Source Drawer

**Files:**
- Create: `frontend/src/components/SourceDrawer.tsx`
- Modify: `frontend/src/components/EmailDetail.tsx`
- Modify: `frontend/src/components/EmailDetail.test.tsx`

**Interfaces:**
- Consumes: Figma interaction state `Desktop / Interaction / Source Drawer Open` (`14:3`) and current source-chip affordance.
- Produces: accessible source evidence drawer.

- [x] **Step 1: Replace anchor-only source opening**

  `근거 원본 보기` now opens `SourceDrawer` instead of only navigating to a message anchor.

- [x] **Step 2: Add accessible drawer behavior**

  Implemented:

  - `role="dialog"`
  - `aria-modal="true"`
  - `aria-labelledby`
  - `aria-describedby`
  - close button focus on open
  - Escape close
  - mouse close
  - focus restore
  - body scroll lock

- [x] **Step 3: Add interaction tests**

  `EmailDetail.test.tsx` verifies:

  - source button click opens the drawer
  - dialog aria attributes are present
  - initial focus lands on the close control
  - close button closes the drawer
  - Escape closes the drawer
  - `source_chip_opened` is recorded without raw email body

## Task 3: Produce Design-To-Code Backlog

**Files:**
- Create: `docs/superpowers/reports/2026-07-02-naruon-design-to-code-backlog.md`

**Interfaces:**
- Consumes: Figma file, existing frontend components, first-slice source mockups.
- Produces: product-design-to-frontend backlog with exact component anchors.

- [x] **Step 1: Map Figma components to current code**

  Include mappings for:

  - navigation shell
  - evidence/action panel
  - confidence badge
  - source chip
  - table row
  - source drawer
  - reply draft controls
  - action item controls
  - calendar controls

- [x] **Step 2: Mark implementation status**

  Use statuses:

  - implemented in existing UI
  - contract added
  - backlog only
  - blocked by analytics destination

- [x] **Step 3: Define next PR sequence**

  Sequence:

  1. Wire product-event dispatcher behind the contract.
  2. Attach events to `EmailDetail` handlers.
  3. Add source drawer as an accessible component.
  4. Extend context-search result actions.
  5. Add dashboard only after telemetry destination is confirmed.

## Task 4: Produce Event Dictionary Report

**Files:**
- Create: `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`

**Interfaces:**
- Consumes: `frontend/src/lib/product-events.ts`.
- Produces: stakeholder-readable Data Analytics handoff.

- [x] **Step 1: State caveats**

  Required caveats:

  - No live event warehouse was available.
  - No KPI values are measured product performance.
  - Event owner and destination must be confirmed before dashboards.
  - Timezone is fixed to `Asia/Seoul` for the initial contract.

- [x] **Step 2: Document every event**

  For each event, include:

  - trigger
  - denominator grain
  - entity IDs
  - required payload
  - optional payload
  - owner
  - quality caveat

- [x] **Step 3: Document guardrails**

  Include:

  - latency guardrail
  - model-quality guardrail
  - trust/safety guardrail

## Task 5: Add Figma Interaction States

**Figma File:**
- URL: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK
- File key: `68b5XB58w8nwT2LYOOnikK`

**Allowed tools:**
- `search_design_system` with `disableCodeConnect=true`
- `get_metadata`
- `use_figma`
- `get_screenshot`

**Forbidden tools:**
- Code Connect suggestion tools
- Code Connect mapping tools

- [x] **Step 1: Search design system without Code Connect**

  Search for source chip, drawer, button, badge, and card patterns with `disableCodeConnect=true`.

- [x] **Step 2: Add visible state frames**

  Add these state frames near the existing desktop slice:

  - `Desktop / Interaction / Source Drawer Open`
  - `Desktop / Interaction / Draft Reply Review`
  - `Desktop / Interaction / Schedule Confirmation`

  Created Figma nodes:

  - `Naruon Interaction States / 2026-07-02` (`14:2`)
  - `Desktop / Interaction / Source Drawer Open` (`14:3`)
  - `Desktop / Interaction / Draft Reply Review` (`14:41`)
  - `Desktop / Interaction / Schedule Confirmation` (`14:78`)

- [x] **Step 3: Add prototype notes**

  Add a compact notes frame that describes:

  - source-chip opening
  - evidence drawer
  - draft reply review
  - schedule confirmation
  - event names tied to each transition

  Created node:

  - `Desktop / Interaction / Prototype Notes` (`14:118`)

- [x] **Step 4: Screenshot verify**

  Capture screenshot evidence for the new interaction cluster and save it under:

  - `docs/superpowers/artifacts/naruon-figma-package/qa/figma-interaction-states.png`

  Verified:

  - PNG image data, 2400 x 1252, RGBA.

## Task 6: Verify

**Files and commands:**
- `git status --short`
- `test -f frontend/src/lib/product-events.ts`
- `test -f frontend/src/lib/product-events.test.ts`
- `test -f docs/superpowers/reports/2026-07-02-naruon-design-to-code-backlog.md`
- `test -f docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`
- `rg -n "context_synthesis_viewed|source_chip_opened|calendar_reflected|trust_safety_guardrail_triggered" frontend/src/lib docs/superpowers`
- `pnpm --dir frontend test src/lib/product-events.test.ts`

- [x] **Step 1: Verify required artifacts**

  Confirm all new files exist.

- [x] **Step 2: Verify event references**

  Confirm all required event names appear in code and docs.

- [x] **Step 3: Run frontend test if dependencies exist**

  If `frontend/node_modules` is absent, document that the test was not run because dependencies are not installed in this worktree.

  Actual result:

  - `pnpm --dir frontend test src/components/EmailDetail.test.tsx src/components/SearchLayout.test.tsx src/lib/product-events.test.ts` passed: 3 files, 33 tests.
  - `pnpm --dir frontend test` passed: 43 files, 319 tests.
  - `pnpm --dir frontend typecheck` passed.
  - Browser QA with local mocked APIs passed for `/mail` source drawer interaction and `/search` submit-result-action flow.
  - Browser QA screenshots: `/tmp/naruon-mail-source-drawer.png`, `/tmp/naruon-search-event-flow.png`.
  - `pnpm` installed ignored `frontend/node_modules/` because dependencies were absent at the start of the run.

- [x] **Step 4: Verify Figma**

  Confirm new Figma frame IDs and screenshot path.

## Completion Criteria

- New Goal-specific plan exists and is updated.
- Product-event contract and privacy-safe local dispatcher exist in frontend code.
- Mail-detail and context-search call sites are wired.
- Source drawer exists as working UI with accessibility tests.
- Event dictionary report exists with payload, denominator grain, timezone, owner, and caveat.
- Design-to-code backlog exists with exact current-code anchors.
- Figma file has visible interaction state frames and screenshot evidence.
- Verification output is recorded in the final response.
- External analytics destination remains explicitly blocked until owner, retention, consent, and warehouse schema are confirmed.
