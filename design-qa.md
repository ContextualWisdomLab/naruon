# Naruon Design QA

source visual truth path:

- `docs/ui-ux/mockups/mockup_36.png`
- `docs/ui-ux/mockups/mockup_40.png`

implementation screenshot path:

- `docs/superpowers/artifacts/naruon-figma-package/qa/figma-desktop-mail-detail.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/figma-mobile-context-sheet.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/figma-interaction-states.png`

viewport:

- Desktop Figma frame: 1440 x 1024
- Mobile Figma frame: 390 x 844

state:

- Desktop: `Desktop / Mail Detail / Evidence Review` (`3:157`)
- Mobile: `Mobile / Context Synthesis Bottom Sheet` (`3:273`)
- Interaction follow-up cluster: `Naruon Interaction States / 2026-07-02` (`14:2`)
- Source drawer state: `Desktop / Interaction / Source Drawer Open` (`14:3`)
- Draft review state: `Desktop / Interaction / Draft Reply Review` (`14:41`)
- Schedule confirmation state: `Desktop / Interaction / Schedule Confirmation` (`14:78`)
- Prototype notes: `Desktop / Interaction / Prototype Notes` (`14:118`)

full-view comparison evidence:

- `docs/superpowers/artifacts/naruon-figma-package/qa/compare-desktop-mockup36-vs-figma.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/compare-mobile-mockup40-vs-figma.png`

focused region comparison evidence:

- Focused region was not separated into additional crops because the compared frames are readable at full-view scale and the current deliverable is a first vertical slice, not a pixel-perfect clone. The full-view comparison covers the critical regions: mail thread, `맥락 종합`, `판단 포인트`, source chips, confidence badge, action buttons, and mobile bottom sheet.

**Findings**

- The Figma first vertical slice remains a usable design handoff for layout of mail detail, `맥락 종합`, source chips, and execution actions. That is not the same as “no product defects.”
  Location: shipped mail/search analysis UI versus Figma `68b5XB58w8nwT2LYOOnikK` and mapping §3/§4.1.
  Evidence: see `docs/product-technical-gap-baseline.md` (dual confidence scale, missing titled `판단 포인트` card, provenance overclaim `판단 보조 생성`, empty execution with no blocked/intent-only footer, mapping GNB omitting 작업/맥락 검색).
  Impact: users could read 100% and ~1% for nearly the same score, or treat placeholder provenance and empty footers as successful synthesis.
  Fix: ADR-0014 display contract on the Storybook branch; do not treat this QA file as a clean bill of health for the incomplete slice.

**Open Questions**

- The Figma slice intentionally simplifies the density of `mockup_36.png` and `mockup_40.png`. It is aligned to the Product Design scope as a handoff slice, not a full pixel clone of every source screen.
- Live product analytics data is unavailable, so KPI claims remain framework-level only.

**Implementation Checklist**

- Figma pages exist: `Source Map`, `Foundations`, `Components`, `Desktop Screens`, `Mobile Screens`, `QA Notes`.
- Source mockups are uploaded on the Figma `Source Map` page as `mockup_19`, `mockup_30`, `mockup_31`, `mockup_36`, `mockup_37`, `mockup_40`, and `mockup_41`.
- First desktop slice exists at node `3:157`.
- First mobile slice exists at node `3:273`.
- Component page includes table row and source drawer coverage.
- Desktop page includes expansion roadmap node `11:17`.
- Figma Code Connect was not used.

**Follow-up Polish**

- Add higher-density desktop variants for the participant list, attachment file rail, and meeting proposal panel from `mockup_36.png`.
- Add more mobile states for reply review, source drawer, and schedule confirmation.
- Replace local minimal components with an official team library if a newer Naruon Figma source appears.

patches made since the previous QA pass:

- Created the Figma file `https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK`.
- Created required Figma pages and first vertical slice frames.
- Uploaded source mockups into the Figma `Source Map` page.
- Captured Figma desktop/mobile screenshots and generated source-vs-Figma comparison boards.
- Added table row and source drawer components after completion audit.
- Added expansion roadmap for Home, Calendar, Data, AI Hub, Security, and Settings.
- Added a follow-up interaction-state cluster for source-chip opening, evidence drawer, draft reply review, and schedule confirmation.
- Added typed product-event contract and event dictionary for `context_synthesis_viewed`, `source_chip_opened`, `calendar_reflected`, draft-reply events, context-search events, and guardrail events.
- Added privacy-safe local dispatcher and actual call sites in `EmailDetail.tsx` and `SearchLayout.tsx`.
- Added `SourceDrawer.tsx` and connected `근거 원본 보기` to an accessible source evidence drawer.
- Added Vitest coverage for product-event validation, mail-detail source drawer behavior, mail-detail action events, and context-search events.
- Added a controlled paid-pilot readiness spec and repeatable `pnpm --dir frontend pilot:smoke` browser gate for `/mail` and `/search`.
- Verified the pilot smoke path with no console errors or warnings and 1440 x 1024 screenshots at `/tmp/naruon-pilot-mail.png` and `/tmp/naruon-pilot-search.png`.
- Added a 20B KRW enterprise sale readiness plan for the implemented frontend slice, with explicit separation between buyer-reviewable product evidence and unresolved public-launch/procurement requirements.
- Hardened the pilot smoke gate to localhost-only targets, bounded browser-local product-event history, normalized fallback event IDs, and generated unique `SourceDrawer` ARIA IDs.

final result: passed for the scoped design-to-code and controlled paid-pilot demo slice; buyer-reviewable for the implemented frontend slice after release gates pass, but not a public-launch or final procurement-complete claim
