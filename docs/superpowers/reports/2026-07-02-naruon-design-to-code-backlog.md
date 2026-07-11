# Naruon Design-To-Code Backlog

This backlog connects the Figma/Product Design package to the current frontend without using Figma Code Connect. The current implementation covers the first vertical slice and now includes local product-event instrumentation, source evidence drawer behavior, and context-search event hooks.

## Current Code Anchors

| Product element | Figma/source anchor | Current code anchor | Status | Next implementation step |
| --- | --- | --- | --- | --- |
| Navigation shell | `Components`, desktop slice, 10-area IA | `frontend/src/components/AIHubLayout.tsx`, `DashboardLayout.tsx`, `CalendarLayout.tsx`, `WorkspaceHome.tsx` | implemented in existing UI | Normalize nav labels against the mandatory terminology when each area is touched. |
| Evidence/action panel | `Desktop / Mail Detail / Evidence Review` | `frontend/src/components/EmailDetail.tsx` | implemented and instrumented | Add correction/discard follow-through only after the product defines those actions. |
| Confidence badge | `Components` confidence badge | `frontend/src/components/DecisionPointCard.tsx`, `frontend/src/lib/confidence.ts` | implemented in existing UI | Reuse `toConfidencePercent`; emit confidence in event payload only as 0-100 numeric value. |
| Source chip | source chip in first slice and `근거 원본 보기` | `EmailDetail.tsx`, `SourceDrawer.tsx`, `DecisionPointCard` provenance chip | implemented and instrumented | Add multi-source lists after backend provenance IDs are available. |
| Table row | `Component / Table Row` | `frontend/src/components/EmailList.tsx`, data/security/task rows | implemented in existing UI | Add shared row-density guidance only if duplication becomes a maintenance issue. |
| Source drawer | `Component / Source Drawer` | `frontend/src/components/SourceDrawer.tsx` | implemented and tested | Add richer evidence metadata after source provenance IDs are joined to backend synthesis output IDs. |
| Reply draft controls | `답장 초안` state | `EmailDetail.tsx` `handleDraftReply`, `Textarea`, `handleSendReply` | implemented and instrumented | Add edit-distance or discard metrics only after privacy review. |
| Action item controls | `실행 항목` state | `EmailDetail.tsx` `handleCreateTask` | implemented and instrumented | Add task completion follow-through later. |
| Calendar controls | `일정 반영` state | `EmailDetail.tsx` `handleSyncCalendar` | implemented and instrumented | Keep provider write and local intent separated in dashboard definitions. |
| Context search actions | `Desktop / Context Search / Evidence Action` | `frontend/src/components/SearchLayout.tsx` | implemented and instrumented | Add zero-result, refinement, and filter-change events in a later KPI pass. |
| Product event contract | Data Analytics KPI validation | `frontend/src/lib/product-events.ts` | implemented as local dispatcher | External dispatch remains blocked until analytics destination, retention, and consent policy are confirmed. |

## PR Sequence

1. Keep the local dispatcher in `frontend/src/lib/product-events.ts`; do not add external transport until privacy and destination ownership are confirmed.
2. Extend the existing mail-detail instrumentation with correction, discard, and human feedback events after those UI actions exist.
3. Expand `SourceDrawer` to multiple sources after backend provenance returns stable source arrays per AI output.
4. Extend `SearchLayout` with zero-result, refinement, filter-change, and search-abandon events after KPI denominator rules are finalized.
5. Add product dashboard definitions only after the event destination, retention policy, and warehouse schema are confirmed.

## Product Design Notes

- Keep `맥락 종합`, `판단 포인트`, `실행 항목`, `답장 초안`, `맥락 검색`, `관계 맥락`, `일정 반영`, and `판단 보조` as the visible vocabulary.
- Keep evidence and confidence near AI output; do not move them into tooltip-only UI.
- Keep raw email body, raw reply body, and raw search query text out of analytics payloads.
- Treat source opening as both a trust behavior and a possible clarity problem; pair it with discard/correction rates.

## Blockers And Caveats

- CodeGraph is not initialized in this worktree and no CodeGraph tools are exposed in the session.
- No live analytics destination is confirmed.
- Product events are local-only records and browser-local custom events; no network export is implemented.
- Existing `.Jules/*` modifications are preserved and are not part of this package.
