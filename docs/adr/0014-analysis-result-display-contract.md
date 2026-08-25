# ADR-0014: One honest analysis-result display contract

- Status: Accepted
- Date: 2026-08-23 (UTC)
- Owners: Naruon frontend maintainers
- Figma file ID: `68b5XB58w8nwT2LYOOnikK`

## Context

Mail detail, context search, and decision-point cards all render analysis
results (`맥락 종합`, `판단 포인트`, `실행 항목`, confidence, source/evidence,
next actions). Three different numeric rules were in use:

- `toConfidencePercent` treated `[0, 1]` as a unit interval, so `1` became
  `100%` while `1.01` became `1%`.
- Search results used `score <= 1`.
- Sender DAG always multiplied `confidence_score * 100`.
- `DecisionPointCard` assumed the value was already a percent.

The same score therefore disagreed across mail and search. Missing provenance
was replaced with `판단 보조 생성`. Empty execution hid the footer instead of
saying the next action was blocked. Figma
`https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK` already specifies
confidence badges, source chips, and execution actions for the mail-detail
slice; the shipped UI must not invent a second scale or claim evidence that
the payload does not contain.

## Decision

1. One helper, `toConfidencePercent`, owns display math. Values whose
   magnitude is in `[0, 2)` are unit-interval (so `1` and `1.01` both display
   near `100%`). Values `>= 2` are already percent. The result is clamped to
   `0–100`.
2. Missing confidence is `신뢰도 미제공`. Scores below `50` also show
   `낮은 신뢰도`. Empty synthesis, synthesis error, and low confidence are
   distinct visible states.
3. Provenance is shown only when the payload supplies it. Missing evidence
   is `근거 없음`. Judgment without an executable next action is
   `실행 차단됨` or `의도만 기록`.
4. `판단 포인트` is derived from the existing `action_items` synthesis
   payload. Do not invent backend analysis fields.
5. Storybook CSF stories for this flow reuse production tokens from
   `frontend/src/app/globals.css` (see [ADR-0013](0013-storybook-design-system.md)).
   Interaction truth remains in Vitest.

## Consequences

- Mail and search no longer disagree on the same score.
- Tests fail if the dual-scale cliff or the `판단 보조 생성` overclaim return.
- Calendar writeback that does not execute a provider write stays labeled
  intent-only.

## Verification

```bash
corepack pnpm@11.5.3 --dir frontend test -- src/lib/confidence.test.ts src/components/DecisionPointCard.test.tsx src/components/EmailDetail.test.tsx src/components/SearchLayout.test.tsx
corepack pnpm@11.5.3 --dir frontend build-storybook
```

## References (APA 7th)

Storybook. (n.d.). *Play function*. Retrieved August 23, 2026, from
https://storybook.js.org/docs/writing-stories/play-function

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/
