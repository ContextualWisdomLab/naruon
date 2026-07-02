# Naruon Design-To-Code Telemetry QA

Question being answered: whether the follow-up package turns the Figma/Product Design/Data Analytics handoff into working product code without using Figma Code Connect, without external analytics dispatch, and without claiming live product metrics.

## Result

Final result: passed.

## Commercial Pilot Readiness

This package is suitable for a controlled paid-pilot demonstration after the release gates pass. It is not a public-launch readiness claim: hosted deployment, real tenant authorization review, provider-send email, live private-mailbox integration, external analytics governance, billing/legal review, SLA, and support operations remain outside this slice.

## Evidence

- Product-event contract: `frontend/src/lib/product-events.ts`
- Product-event tests: `frontend/src/lib/product-events.test.ts`
- Mail-detail instrumentation and source drawer integration: `frontend/src/components/EmailDetail.tsx`
- Source drawer component: `frontend/src/components/SourceDrawer.tsx`
- Mail-detail interaction tests: `frontend/src/components/EmailDetail.test.tsx`
- Context-search instrumentation: `frontend/src/components/SearchLayout.tsx`
- Context-search product event tests: `frontend/src/components/SearchLayout.test.tsx`
- Follow-up plan: `docs/superpowers/plans/2026-07-02-naruon-design-to-code-and-telemetry.md`
- Design-to-code backlog: `docs/superpowers/reports/2026-07-02-naruon-design-to-code-backlog.md`
- Event dictionary: `docs/superpowers/reports/2026-07-02-naruon-event-dictionary.md`
- Figma file: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK
- Figma interaction cluster: `Naruon Interaction States / 2026-07-02` (`14:2`)
- Figma state frames:
  - `Desktop / Interaction / Source Drawer Open` (`14:3`)
  - `Desktop / Interaction / Draft Reply Review` (`14:41`)
  - `Desktop / Interaction / Schedule Confirmation` (`14:78`)
  - `Desktop / Interaction / Prototype Notes` (`14:118`)
- Screenshot evidence: `docs/superpowers/artifacts/naruon-figma-package/qa/figma-interaction-states.png`
- Local browser QA screenshot: `/tmp/naruon-mail-source-drawer.png`
- Local browser QA screenshot: `/tmp/naruon-search-event-flow.png`
- Commercial pilot smoke screenshot: `/tmp/naruon-pilot-mail.png`
- Commercial pilot smoke screenshot: `/tmp/naruon-pilot-search.png`

## Validation

- `search_design_system` was called with `disableCodeConnect=true`; no linked library components, styles, or variables were returned.
- `use_figma` added visible state frames and returned node IDs.
- `get_metadata` confirmed the interaction cluster and child frame structure.
- `get_screenshot` rendered the cluster; local PNG verification reports 2400 x 1252 RGBA.
- Required product event names appear in code and docs.
- `EmailDetail.tsx` emits local events for synthesis view, source opening, task creation, calendar reflection, draft generation, draft insertion, draft send, latency, and low-confidence model-quality guardrails.
- `SearchLayout.tsx` emits local events for search submit, result open, result action creation, and latency guardrails.
- `SourceDrawer.tsx` provides `role="dialog"`, `aria-modal`, labelled/described content, focus on open, Escape close, mouse close, body scroll lock, and focus restore.
- Browser QA on `http://127.0.0.1:3001/mail` with mocked local APIs opened `근거 원본 보기`, verified the source drawer, focus on `근거 원본 닫기`, close button, Escape close, and local `source_chip_opened`/`context_synthesis_viewed` events without raw email body in event payloads.
- Browser QA on `http://127.0.0.1:3001/search` with mocked local APIs verified search submit, result open, relation capture, `context_search_result_action_created`, and no raw query text in event payloads.
- Browser QA completed with no console errors or warnings after the local `/api/network/graph` mock returned the expected `{ nodes, edges }` shape.
- `pnpm --dir frontend pilot:smoke` is the repeatable browser QA gate for the paid-pilot demo path; it exercises mail source evidence, draft generation/send simulation, task creation, calendar intent, search submit, result open, and relationship capture with local mocked APIs.
- `pnpm --dir frontend pilot:smoke` passed and saved `/tmp/naruon-pilot-mail.png` plus `/tmp/naruon-pilot-search.png` with no console errors or warnings.
- Commercial pilot screenshots are non-empty 1440 x 1024 PNGs.
- `pnpm --dir frontend test src/components/EmailDetail.test.tsx src/components/SearchLayout.test.tsx src/lib/product-events.test.ts` passed: 3 test files, 33 tests.
- `pnpm --dir frontend test` passed: 43 test files, 319 tests.
- `pnpm --dir frontend typecheck` passed.
- `pnpm --dir frontend build` passed with an optimized Next 16 production build.
- `git diff --check` passed.
- Placeholder and launch-claim scan returned only guarded caveat language about not claiming live KPI values or public-launch readiness.

## Caveats

- No live analytics warehouse, dashboard, or telemetry destination was available.
- No KPI values in this package are measured product performance.
- Product events are local-only records plus browser-local `naruon:product-event` custom events; no network emission was added.
- Browser QA used mocked local API responses because no backend service was running behind the Next `/api/*` proxy.
- `frontend/node_modules/` was installed by `pnpm` during the test run and is ignored by git.
- Existing `.Jules/*` modifications were preserved and are unrelated to this follow-up package.
