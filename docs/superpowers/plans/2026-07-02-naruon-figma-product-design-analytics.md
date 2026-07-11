# Naruon Figma Product Design Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Figma-free-or-Figma-ready product design and analytics handoff for Naruon using Figma, Product Design, Superpowers, Ponytail, and Data Analytics, with Figma Code Connect excluded.

**Architecture:** Treat `docs/ui-ux` on `develop` as the source of truth, produce a local design spec plus implementation plan, then create or update Figma only when a target fileKey or Figma planKey is available. The first visual slice is Mail detail to evidence-backed execution, and all broader IA work hangs off that slice.

**Tech Stack:** GitHub repo sources, Markdown docs, Figma MCP tools (`create_new_file`, `use_figma`, `get_libraries`, `search_design_system`, `get_metadata`, `get_screenshot`, optional `generate_figma_design`), Product Design workflow, Data Analytics KPI design, Ponytail scope control.

## Global Constraints

- Do not use Figma Code Connect.
- Do not create Code Connect mappings or files.
- Do not claim live measured analytics without a real data source.
- Preserve canonical source paths under `docs/ui-ux`.
- Use `develop` as the branch baseline.
- Prioritize the first vertical slice before expanding every screen.
- Reuse repo mockups and manifests before generating new visual material.

---

## File Structure

- Created: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`
  - Product definition, source evidence, IA, Figma deliverable, user stories, KPI framework, QA criteria.
- Created: `docs/superpowers/plans/2026-07-02-naruon-figma-product-design-analytics.md`
  - Task-by-task implementation and verification plan.
- Created Figma file:
  - URL: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK
  - File key: `68b5XB58w8nwT2LYOOnikK`
  - `Source Map`
  - `Foundations`
  - `Components`
  - `Desktop Screens`
  - `Mobile Screens`
  - `QA Notes`

## Task 1: Verify Source Baseline

**Files:**
- Read: `docs/ui-ux/README.md`
- Read: `docs/ui-ux/naruon-ui-ux-mapping.md`
- Read: `docs/ui-ux/asset-overviews-2026-06-21/manifest.tsv`
- Read: `docs/ui-ux/individual-assets-2026-06-22/manifest.tsv`
- Read: `docs/ui-ux/reference-set-2026-06-18/sources.tsv`

**Interfaces:**
- Consumes: live repo state on `develop`
- Produces: evidence baseline for all later design and analytics work

- [x] **Step 1: Confirm repo and branch**

Run:

```bash
gh repo view ContextualWisdomLab/naruon --json nameWithOwner,description,defaultBranchRef,isPrivate,url,pushedAt,primaryLanguage
git rev-parse HEAD
git branch --show-current
```

Expected:

- `defaultBranchRef.name` is `develop`
- local branch is `develop`
- checked commit is recorded in the spec

- [x] **Step 2: Count canonical assets**

Run:

```bash
find docs/ui-ux/mockups -maxdepth 1 -type f -name 'mockup_*.png' | wc -l
find docs/ui-ux/reference-set-2026-06-18/images -maxdepth 1 -type f -name '*.png' | wc -l
wc -l docs/ui-ux/asset-overviews-2026-06-21/manifest.tsv docs/ui-ux/individual-assets-2026-06-22/manifest.tsv docs/ui-ux/reference-set-2026-06-18/sources.tsv
```

Expected:

- 41 mockup PNG files
- 45 reference PNG files
- manifest row counts recorded for traceability

- [x] **Step 3: Confirm visual source instructions**

Read `docs/ui-ux/README.md` and verify it says to start with `naruon-ui-ux-mapping.md`, then open matching original images directly.

## Task 2: Produce Product Design Brief

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`

**Interfaces:**
- Consumes: Task 1 source baseline
- Produces: product definition, IA, terminology, and user stories

- [x] **Step 1: Define product promise**

Write the product definition:

```text
Naruon is an evidence-based AI email workspace. It connects email, attachments, images, calendars, relationships, tasks, projects, and source evidence so a user can move from fragmented information to judgment and execution.
```

- [x] **Step 2: Lock mandatory terminology**

Include the term mapping:

- `AI Summary` -> `맥락 종합`
- `Insight` -> `판단 포인트`
- `Todo` -> `실행 항목`
- `Smart Reply` -> `답장 초안`
- `Search` -> `맥락 검색`
- `Network Graph` -> `관계 맥락`
- `Calendar Sync` -> `일정 반영`
- `AI Assistant` -> `판단 보조`

- [x] **Step 3: Define IA**

Document the 10 GNB areas: 홈, 메일, 일정, 작업, 프로젝트, 맥락 검색, 데이터, AI 허브, 보안, 설정.

- [x] **Step 4: Define user stories**

Write acceptance criteria for:

- Evidence-backed thread synthesis
- Decision point extraction
- Action item creation
- Calendar reflection
- Context search follow-through
- Mobile context synthesis

## Task 3: Define Figma Deliverable

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`

**Interfaces:**
- Consumes: Product Design brief and repo mockup map
- Produces: Figma page structure, allowed tools, and first-slice screen plan

- [x] **Step 1: Lock page structure**

Use these exact page names:

- `Source Map`
- `Foundations`
- `Components`
- `Desktop Screens`
- `Mobile Screens`
- `QA Notes`

- [x] **Step 2: Define first vertical slice**

Use this flow:

```text
Mail detail -> 맥락 종합 -> 판단 포인트 -> 실행 항목 / 답장 초안 / 일정 반영 / 관계 맥락
```

Use these source images:

- `docs/ui-ux/mockups/mockup_19.png`
- `docs/ui-ux/mockups/mockup_30.png`
- `docs/ui-ux/mockups/mockup_31.png`
- `docs/ui-ux/mockups/mockup_36.png`
- `docs/ui-ux/mockups/mockup_37.png`
- `docs/ui-ux/mockups/mockup_40.png`
- `docs/ui-ux/mockups/mockup_41.png`

- [x] **Step 3: Define Figma tool policy**

Allowed:

- `create_new_file`
- `use_figma`
- `get_libraries`
- `search_design_system`
- `get_metadata`
- `get_screenshot`
- `generate_figma_design` only when a rendered web source and target fileKey exist

Forbidden:

- Figma Code Connect generation
- Code Connect dependency
- Unsourced replacement visuals

## Task 4: Define Analytics Measurement Framework

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`

**Interfaces:**
- Consumes: product promise and first-slice flow
- Produces: metric definitions and instrumentation assumptions

- [x] **Step 1: Define primary metrics**

Include:

- Context synthesis usage
- Decision-to-action conversion

- [x] **Step 2: Define driver metrics**

Include:

- Evidence interaction
- Context search success
- Draft reply acceptance
- Calendar/task conversion

- [x] **Step 3: Define guardrails**

Include:

- Model quality
- Latency
- Trust/safety

- [x] **Step 4: Label source gaps**

State that no live analytics source is available in this run and all targets remain provisional until baseline telemetry exists.

## Task 5: Figma File Creation Or Handoff

**Files:**
- Update when available: Figma design file
- Record state in: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`

**Interfaces:**
- Consumes: Figma fileKey or Figma planKey
- Produces: editable Figma file or explicit blocked state

- [x] **Step 1: If the user provides a Figma URL**

Extract `fileKey` from a `/design/` URL and run:

```text
get_metadata(fileKey)
get_libraries(fileKey)
search_design_system(fileKey, query="button", disableCodeConnect=true)
```

Expected:

- Existing pages and available libraries are known when a URL is provided.
- Searches disable Code Connect.

Current result:

- No pre-existing user Figma URL was provided.
- New file URL is now available after authenticated plan discovery: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK

- [x] **Step 2: If the user provides a Figma planKey**

Create the file:

```text
create_new_file(editorType="design", fileName="Naruon Product Design System - 2026-07-02", planKey="<provided planKey>")
```

Expected:

- A new Figma design URL and fileKey are returned.

Current result:

- `whoami` exposed one authenticated plan: `Seongho Bae's team` (`team::1408252278989737675`).
- `create_new_file(editorType="design", fileName="Naruon Product Design System - 2026-07-02", planKey="team::1408252278989737675")` returned file key `68b5XB58w8nwT2LYOOnikK`.

- [x] **Step 3: If no Figma target is available**

Historical fallback, no longer current:

```text
If no Figma URL, planKey, or plan-discovery tool is available, record the missing input and continue with the local package.
```

Current state:

- This earlier blocker was resolved after deferred Figma tools exposed `whoami`.
- The blocker state is retained here as historical context only; it is no longer current.

## Task 6: Figma Build Steps Once FileKey Exists

**Files:**
- Figma design file

**Interfaces:**
- Consumes: fileKey and source images
- Produces: Figma source map, foundations, components, screens, QA notes

- [x] **Step 1: Inspect target file**

Run:

```text
get_metadata(fileKey)
get_libraries(fileKey)
```

Expected:

- Page list and available libraries are known.

Current result:

- Initial metadata showed a blank file.
- `get_libraries` returned Material 3 Design Kit and Simple Design System as added libraries.
- `search_design_system(fileKey, query="button", disableCodeConnect=true)` returned no directly usable assets, so local minimal components were created.

- [x] **Step 2: Create page skeleton**

Use `use_figma` with `skillNames="figma-use"` to create pages named:

- `Source Map`
- `Foundations`
- `Components`
- `Desktop Screens`
- `Mobile Screens`
- `QA Notes`

Return all created page IDs.

Current page IDs:

- `Source Map`: `0:1`
- `Foundations`: `3:2`
- `Components`: `3:3`
- `Desktop Screens`: `3:4`
- `Mobile Screens`: `3:5`
- `QA Notes`: `3:6`

- [x] **Step 3: Search reusable design system assets**

Run searches with `disableCodeConnect=true`:

```text
button, input, card, table, chip, badge, navigation, sidebar, drawer, modal, calendar, source, confidence
```

Expected:

- Available components, variables, and styles are known before any manual drawing.

Current result:

- `get_libraries` checked available libraries.
- `search_design_system` was called with `disableCodeConnect=true`.
- No matching component/style/variable results were returned for the checked query, so local minimal foundations/components were created.

- [x] **Step 4: Build foundations**

Create or import reusable tokens for:

- Background, surface, text, border, accent, semantic status colors
- Spacing scale
- Radius scale
- Text styles
- Effect styles

- [x] **Step 5: Build first vertical slice**

Build these frames:

- `Desktop / Mail Detail / Evidence Review`
- `Desktop / Mail Detail / Decision Actions`
- `Desktop / Context Search / Related Evidence`
- `Mobile / Context Synthesis Bottom Sheet`

Expected:

- The slice visibly supports the flow from mail to judgment to action.

Current result:

- `Desktop / Mail Detail / Evidence Review`: `3:157`
- `Desktop / Context Search / Related Evidence`: `3:246`
- `Mobile / Context Synthesis Bottom Sheet`: `3:273`
- `Desktop / Expansion Roadmap`: `11:17`
- `Component / Table Row` and `Component / Source Drawer` added to the Components page.
- Source mockups uploaded to Source Map: `3:315` through `3:321`.

- [x] **Step 6: Validate screenshots**

Use `get_screenshot` for every completed major frame.

Reject and fix frames with:

- clipped text
- overlapping UI
- blank image placeholders
- wrong font family
- unbound or inconsistent component instances
- leftover placeholder shimmer or placeholder labels

Current screenshot evidence:

- `docs/superpowers/artifacts/naruon-figma-package/qa/figma-desktop-mail-detail.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/figma-mobile-context-sheet.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/compare-desktop-mockup36-vs-figma.png`
- `docs/superpowers/artifacts/naruon-figma-package/qa/compare-mobile-mockup40-vs-figma.png`

## Task 7: QA Completion Audit

**Files:**
- Read: `docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md`
- Read: `docs/superpowers/plans/2026-07-02-naruon-figma-product-design-analytics.md`
- Optional: Figma file metadata and screenshots

**Interfaces:**
- Consumes: all produced artifacts
- Produces: completion status and missing-gaps list

- [x] **Step 1: Verify local package artifacts**

Run:

```bash
test -f docs/superpowers/specs/2026-07-02-naruon-figma-product-design-analytics-design.md
test -f docs/superpowers/plans/2026-07-02-naruon-figma-product-design-analytics.md
rg -n "Figma Code Connect|맥락 종합|판단 포인트|실행 항목|Context synthesis usage|Decision-to-action conversion" docs/superpowers
```

Expected:

- Both files exist.
- Required terminology, Code Connect exclusion, and KPI terms are present.

- [x] **Step 2: Verify Figma artifact when fileKey exists**

Run:

```text
get_metadata(fileKey)
get_screenshot(fileKey, nodeId="<first-slice-frame>")
```

Expected:

- Required pages exist.
- First vertical slice is visible.
- Screenshot QA passes.

- [x] **Step 3: Record incomplete external dependency**

Current external gap:

- No current Figma creation gap remains.
- Live analytics data remains unavailable; KPI outputs are definitions and validation caveats, not measured product performance.

## Current Status

Completed in this run:

- Live repo and `develop` baseline checked.
- Canonical UI/UX source assets counted and inspected.
- Product/design/KPI design spec created.
- Superpowers-style implementation plan created.
- Figma Code Connect exclusion recorded.
- Figma file created: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK
- Required Figma pages created.
- Source Map populated with 7 uploaded source mockup frames.
- Local minimal foundations, components, desktop vertical slice, mobile context synthesis, and QA notes created.
- Component coverage includes source chip, confidence badge, decision card, action item card, reply draft card, evidence panel, nav item, primary button, table row, and source drawer.
- Expansion roadmap added for Home, Calendar, Data, AI Hub, Security, and Settings.
- Figma screenshots captured and compared against source mockups.
- Product Design QA and Data Analytics validation reports added.

Still required to fully complete the active goal:

- Wire live telemetry before claiming measured KPI performance.
- Continue future design-to-code work from the Figma file and this package.
