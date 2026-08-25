# Naruon UI-UX and analysis-result gap baseline

**Baseline version:** 0.3 (analysis-result / design-flow slice)
**Observed on:** 2026-08-23 (Asia/Seoul)
**Observed Storybook PR head:** `feat/storybook-design-system`
**Figma file ID:** `68b5XB58w8nwT2LYOOnikK`
**Related ADRs:** [ADR-0013](adr/0013-storybook-design-system.md), [ADR-0014](adr/0014-analysis-result-display-contract.md)

This document inventories **UI-UX design-flow contradictions** and
**analysis-result logical defects** found in the protected tree and in open
PRs. It does not replace the broader commercial completion inventory on
[#1429](https://github.com/ContextualWisdomLab/naruon/pull/1429)
(`docs/product-completion-baseline-2026-08-20`). Counts and PR states are
point-in-time evidence.

Anti-Slop-UI and ui-ux-pro-max are used here as **checklists**, not as a second
visual identity. Naruon stays a Korean-first workbench.

---

## 1. Open UI-UX PRs in this inventory

| PR | Topic | Relation to this slice |
|---|---|---|
| [#1436](https://github.com/ContextualWisdomLab/naruon/pull/1436) | Storybook Button/Badge inventory, Figma ID in ADR-0013 | **This branch.** Extended with analysis CSF + play stories. |
| [#1429](https://github.com/ContextualWisdomLab/naruon/pull/1429) | Product/technical gap baseline (93-PR commercial inventory) | Broader completion baseline. This file is the UI-UX/analysis overlay; do not fork a second commercial baseline. |
| [#1349](https://github.com/ContextualWisdomLab/naruon/pull/1349) | Evidence-workspace task contract | Out of this code change except as the source-linked task contract that mail `실행 항목 생성` must keep. |
| [#1352](https://github.com/ContextualWisdomLab/naruon/pull/1352) | `aria-busy` on async controls | Complementary a11y; analysis buttons already emit `aria-busy` on calendar/task/draft. |
| [#1452](https://github.com/ContextualWisdomLab/naruon/pull/1452) | Disabled tooltip | Complementary a11y; not an analysis-result logic defect. |
| [#1449](https://github.com/ContextualWisdomLab/naruon/pull/1449) | Data repo `aria-busy` | Data workspace only; cited so Data is not treated as an analysis surface. |
| [#1441](https://github.com/ContextualWisdomLab/naruon/pull/1441) | Mail density | Layout density, not confidence math. |
| [#1430](https://github.com/ContextualWisdomLab/naruon/pull/1430) | Focus-visible | Complementary; analysis cards keep `focus-visible:ring-ring/40`. |
| [#1421](https://github.com/ContextualWisdomLab/naruon/pull/1421) | Decorative icons | Complementary; analysis icons stay `aria-hidden`. |
| [#1411](https://github.com/ContextualWisdomLab/naruon/pull/1411) | Search clear `aria` | Search chrome, not score display. |
| [#1408](https://github.com/ContextualWisdomLab/naruon/pull/1408) | AI Hub tab focus | AI Hub ops evidence reuses `판단 포인트` as an **ops** label, not mail synthesis. |
| [#1400](https://github.com/ContextualWisdomLab/naruon/pull/1400) | Withheld-media next actions | Draft. Next-action honesty is the same class of defect as blocked/intent-only execution. |
| [#1387](https://github.com/ContextualWisdomLab/naruon/pull/1387) | Calendar a11y | Draft. Calendar reflect remains intent-only until provider write exists. |
| [#1241](https://github.com/ContextualWisdomLab/naruon/pull/1241) | OIDC focus | Auth chrome; out of analysis-result scope. |

Non-UI-UX PRs (auth encodings, Message-ID, workflow registry, dependabot
Actions, PDF decode tests) are **out of scope** here except as citations that
they are not analysis-result work.

---

## 2. Design-flow contradictions

| ID | Contradicting sources | User-facing failure |
|---|---|---|
| DF-01 | Mapping §3 lists ten GNB areas including 작업 and 맥락 검색; mapping §4.1 previously named only Home, Mail, Calendar, Project, Data, AI Hub, Security, Settings | Agents and implementers could ship a shell that omits Tasks and Context Search while claiming the mapping is satisfied. **Fix in this PR:** §4.1 now names the same ten areas. |
| DF-02 | Mail empty copy (`EmailDetail.tsx`) promised `맥락 종합, 판단 포인트, 실행 항목`; shipped cards were only 맥락 종합 / 실행 항목 / 답장 초안. Figma `3:157` and `design-qa.md` show a titled 판단 포인트 card | Selecting a mail told the user judgment points would appear; no titled card existed. **Fix:** 판단 포인트 is derived from existing `action_items` (no invented backend field). |
| DF-03 | `design-qa.md` claimed “No actionable P0/P1/P2 findings remain” for an intentionally incomplete first slice | Reviewers could treat an incomplete handoff as production-complete. **Fix:** findings now point at this baseline and the dual-scale / overclaim defects. |
| DF-04 | Figma `68b5XB58w8nwT2LYOOnikK` + Storybook PR #1436 inventory was Button/Badge only | Scene events (source open, draft review, calendar reflect, task create) and edge states had no CSF/play catalog. **Fix:** `DecisionPointCard.stories.tsx` on this PR. |
| DF-05 | AI Hub reuses `판단 포인트` for ops/model evidence (`AIHubLayout.tsx`) | Operators can read Hub “판단 포인트” as if it were the current mail synthesis. Labeled as a remaining naming collision; this PR does not invent Hub analysis data. |

---

## 3. Analysis-result logical defects

| ID | Contradicting sources | User-facing failure |
|---|---|---|
| AR-01 | `toConfidencePercent` (`<= 1` → ×100) vs SearchLayout (`score <= 1`) vs DAG (`* 100`) vs DecisionPointCard (already-percent) | The same score `1` vs `1.01` rendered as 100% in mail and ~1% in search, or 9100% in DAG if a percent leaked in. **Fix:** one helper, magnitude `< 2` is unit-interval. |
| AR-02 | `EmailDetail` `provenance={llmData?.provenance \|\| "판단 보조 생성"}` | Missing provenance was displayed as if a model/source had been named. **Fix:** show provenance only when supplied. |
| AR-03 | Low confidence recorded `model_quality_guardrail_recorded` but the card still looked like a successful high-confidence synthesis | Users could not see `낮은 신뢰도`. **Fix:** visible label + `data-analysis-state="low-confidence"`. |
| AR-04 | Empty `action_items` hid the execution footer | No next action and no `실행 차단됨` / `의도만 기록`. **Fix:** blocked footer; calendar without `provider_write_executed` is intent-only. |
| AR-05 | Search result without `source_message_id` still offered “메일 원본” evidence chrome | Users could believe a source chip existed. **Fix:** `근거 없음`. |

---

## 4. Ten-dimension review (analysis flow only)

Checklist sources: Anti-Slop-UI (anti-generic-slop) and ui-ux-pro-max
(contrast, focus, reduced-motion, reflow, non-color-only badges). Identity
stays Naruon tokens in `frontend/src/app/globals.css`.

| Dimension | Finding | Action |
|---|---|---|
| Accessibility | Loading used a spinner; error used `role="alert"`; source drawer already traps focus. Low confidence was event-only. | Keep `role="status"` / `alert`; add text `낮은 신뢰도` / `신뢰도 미제공` (not color-only). `motion-reduce:animate-none` on the spinner. |
| Touch & Interaction | Calendar/task buttons were already 36px (`h-9`). | Unchanged. |
| Performance | No new network. Display math is O(1). | Unchanged. |
| Style Selection | DecisionPointCard used a second glass theme (`bg-white/50 backdrop-blur-xl`, emerald/amber/red chips) beside production tokens. | Card uses `bg-card` / `border-border` / `primary` / `destructive` / `muted`. |
| Layout & Responsive | Mail analysis stacked three cards; adding 판단 포인트 is the mapping-required fourth. Footer wraps with `flex-wrap` on chips. | Added the titled card; chips wrap. |
| Typography & Color | Confidence used color-only bands in search. | Text labels on every band. |
| Animation | Spinner ignored `prefers-reduced-motion`. | `motion-reduce:animate-none`. |
| Forms & Feedback | Empty vs error used the same card shell but error copy could be missed if empty footer hid state. | Distinct empty/error/blocked copy. |
| Navigation Patterns | Mapping GNB omitted 작업/맥락 검색. | Docs fix DF-01. Desktop nav already includes those routes; this PR does not restyle GNB. |
| Charts & Data | Confidence is a badge, not a chart. Dual scale was the data lie. | One scale (AR-01). |

Remaining (not this PR): pixel-clone of 41 mockups, Figma Code Connect, Hub
ops/mail naming collision (DF-05), withheld-media (#1400), calendar a11y
(#1387).

---

## 5. Honest analysis contract (shipped)

1. Single scale: `toConfidencePercent` in `frontend/src/lib/confidence.ts`.
2. Visible states: loading, empty, error, low confidence, missing confidence,
   missing evidence, blocked execution, intent-only execution.
3. Mail and search import the same helper.
4. `판단 포인트` = `action_items` from `/api/llm/summarize`. No new backend
   fields.
5. Storybook play covers scene and edge events on production tokens.
