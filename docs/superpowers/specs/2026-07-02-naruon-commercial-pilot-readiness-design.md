# Naruon Commercial Pilot Readiness Design

## Purpose

This spec defines the minimum standard for presenting Naruon as a paid pilot product, not a Figma handoff, telemetry-only demo, or public launch claim.

The target state is **commercial pilot ready**: the core buyer-facing mail and context-search workflows can be demonstrated repeatedly, privacy-sensitive analytics remain local-only, production frontend build passes, and the remaining public-launch gaps are explicit.

For high-value enterprise sales, including a 2,000,000,000 KRW review target, this spec only covers the technical slice that a buyer can inspect. Contract close still requires production deployment, tenant security evidence, legal/procurement artifacts, SLA, and support operations outside this frontend slice.

## Non-Goals

- Do not claim public SaaS launch readiness.
- Do not claim live KPI performance.
- Do not add billing, legal/compliance workflow, SLA, hosted deployment, or external analytics export in this slice.
- Do not send raw email body, raw draft body, or raw search query text to product events.
- Do not use Figma Code Connect.

## Commercial Pilot Definition

Naruon is commercial-pilot ready when these are true:

1. A stakeholder can open `/mail`, select a message, inspect AI context, open and close source evidence, generate a reply draft, simulate send, create action items, and create calendar writeback intents without visible runtime failure.
2. A stakeholder can open `/search`, submit a context query, open a result, capture a sender relationship, and see a source backlink without visible runtime failure.
3. Product events are emitted locally with stable event names and entity lineage, but do not leave the browser or contain raw sensitive text.
4. The frontend passes typecheck, unit/component tests, production build, diff hygiene, required-event search, and browser interaction QA.
5. QA evidence is repeatable through a committed smoke script, not only an ad hoc terminal session.
6. Public-launch caveats are documented in stakeholder-facing language.

## Architecture

The current frontend remains the product anchor. `EmailDetail.tsx` owns mail-detail actions and source evidence interactions. `SearchLayout.tsx` owns context-search actions and lineage. `product-events.ts` owns local event validation, sanitization, in-memory recording, and browser-local `naruon:product-event` dispatch.

Commercial QA is exercised through a local Playwright smoke script that runs against a live Next dev or preview server and intercepts `/api/*` calls with deterministic pilot-safe data. This proves UI behavior without requiring a private mailbox, live backend, or external analytics destination.

The smoke script must reject non-localhost base URLs. It must not navigate to or click through shared staging or production environments.

## Surfaces

### Mail Detail

Required user-visible flow:

- Inbox item renders.
- Selecting the item opens detail.
- `맥락 종합` renders with confidence and source affordance.
- `근거 원본 보기` opens `SourceDrawer`.
- Drawer has `role="dialog"`, `aria-modal="true"`, a labelled title, initial focus on close, close button, Escape close, and focus restore.
- `답장 초안 생성` fills the editable reply draft.
- `답장 보내기` clears the draft and shows simulated-send status.
- `실행 항목 생성` shows created task status.
- `일정 반영` shows calendar intent status.

Required local events:

- `context_synthesis_viewed`
- `source_chip_opened`
- `draft_reply_generated`
- `draft_reply_inserted`
- `draft_reply_sent`
- `action_item_created`
- `calendar_reflected`
- `latency_guardrail_recorded`
- `model_quality_guardrail_recorded` when confidence is low

### Context Search

Required user-visible flow:

- Default search results render.
- Submitting a new query updates the selected result.
- Result detail renders source binding and confidence.
- `발신자 관계 캡처` creates a relationship card and source backlink.

Required local events:

- `context_search_submitted`
- `context_search_result_opened`
- `context_search_result_action_created`
- `latency_guardrail_recorded`

## Privacy And Analytics

The pilot build may emit only local browser events. External analytics export remains blocked until destination ownership, retention, consent, and warehouse schema are approved.

Forbidden payload content:

- raw email body
- raw draft body
- raw search query
- arbitrary non-contract payload fields

Runtime safety requirements:

- local product-event history must be bounded
- fallback event IDs must not double-prefix caller-provided event prefixes
- event recording must remain browser-local unless a separately approved analytics destination, consent, retention, and warehouse contract exist

Allowed payload content:

- stable IDs
- event names
- surface names
- status values
- source types
- length/rank buckets
- booleans such as `source_backlink_present`

## QA Gates

All gates must pass before calling the slice complete:

```bash
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend pilot:smoke
git diff --check
rg -n "context_synthesis_viewed|source_chip_opened|action_item_created|calendar_reflected|draft_reply_generated|draft_reply_inserted|draft_reply_sent|context_search_submitted|context_search_result_opened|context_search_result_action_created|latency_guardrail_recorded|model_quality_guardrail_recorded|trust_safety_guardrail_triggered" frontend/src docs/superpowers design-qa.md
rg -n "TBD|TODO|FIXME|contract only|proposed only|not instrumented|public launch ready|live KPI" docs/superpowers design-qa.md frontend/src
```

The placeholder scan may return guarded caveat language such as “No live KPI values”; it must not return claims that the product is publicly launch ready.

## Public Launch Caveats

These are not blockers for a paid pilot demo, but they are blockers for public launch:

- Hosted production deployment and rollback process.
- Real auth/tenant authorization audit.
- Provider-send email path beyond simulated send.
- Live backend and private mailbox integration in a controlled environment.
- External analytics destination, consent, retention, and dashboard governance.
- Billing and legal/compliance review.
- SLA, support, incident response, and data processing terms.
- Procurement/security questionnaire package for enterprise buyers.
- Commercial terms and acceptance criteria for any 2,000,000,000 KRW transaction.

## Completion Rule

Do not mark this work complete unless production build, automated tests, browser smoke, privacy scan, and PR/merge/keep/discard handoff are all present in current evidence.
