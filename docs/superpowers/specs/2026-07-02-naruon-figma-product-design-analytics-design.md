# Naruon Figma Product Design Analytics Design Spec

## Summary

This spec defines the execution package for `ContextualWisdomLab/naruon` using Figma, Product Design, Superpowers, Ponytail, and Data Analytics. Figma Code Connect is explicitly out of scope: do not create Code Connect files, do not depend on Code Connect mappings, and do not treat Code Connect as required evidence for this work.

The package turns the existing Naruon UI/UX repository assets into a product-design and measurement handoff: a Figma file structure, design-system screen plan, core user stories, acceptance criteria, KPI definitions, QA checks, and follow-up backlog. The first implementation slice is deliberately small and high-value: Mail detail -> `맥락 종합` -> `판단 포인트` -> `실행 항목` / `일정 반영`.

## Evidence Baseline

- Repository: `ContextualWisdomLab/naruon`
- Checked branch: `develop`
- Checked commit: `00e9c15f559349d21fdf53bffc6c487c323dd4be`
- Live repo description: `AI 이메일 워크스페이스: 메일·첨부·일정·작업을 맥락으로 묶어 판단과 실행으로 연결합니다.`
- Canonical UI/UX entrypoint: `docs/ui-ux/README.md`
- Agent text map: `docs/ui-ux/naruon-ui-ux-mapping.md`
- Canonical mockup set: `docs/ui-ux/mockups/mockup_01.png` through `mockup_41.png` (41 files)
- Durable reference set: `docs/ui-ux/reference-set-2026-06-18/images/ui-ux-reference-01.png` through `ui-ux-reference-45.png` (45 files)
- Reference integrity file: `docs/ui-ux/reference-set-2026-06-18/sources.tsv` (45 rows)
- Asset overview manifest: `docs/ui-ux/asset-overviews-2026-06-21/manifest.tsv` (97 rows)
- Individual asset manifest: `docs/ui-ux/individual-assets-2026-06-22/manifest.tsv` (945 rows)
- Product Design saved context: not configured at runtime; use repo sources as the first-pass design context.

The README requires agents to start with `naruon-ui-ux-mapping.md`, then open the referenced original PNG files directly. The mapping file is an index, not a replacement for visual inspection.

## Product Definition

Naruon is an evidence-based AI email workspace. It is not a generic mail client and not a simple summarizer. It connects email, attachments, images, calendars, relationships, tasks, projects, and source evidence so a user can move from fragmented information to judgment and execution.

Design principles:

- Connect context, do not merely shorten email.
- Present evidence and confidence, not unsupported AI conclusions.
- Turn judgment into execution through reply, calendar, task, project, approval, or policy actions.

Mandatory UI terminology:

| Avoid | Use | Meaning |
| --- | --- | --- |
| AI Summary | `맥락 종합` | Evidence-backed synthesis |
| Summary | `종합`, `핵심 맥락` | Condensed but sourced context |
| Insight | `판단 포인트` | Decision point that needs judgment |
| Todo | `실행 항목` | Action item tied to evidence |
| Smart Reply | `답장 초안` | Draft reply the user can inspect |
| Search | `맥락 검색` | Search across connected context |
| Network Graph | `관계 맥락` | Relationship context |
| Calendar Sync | `일정 반영` | Reflect schedule into calendar |
| AI Assistant | `판단 보조` | Judgment assist |

## Information Architecture

Naruon has 10 main GNB areas. Figma and product artifacts must preserve this IA even when the first execution slice only implements a subset.

| Area | Main surfaces | Required actions |
| --- | --- | --- |
| 홈 | 판단 포인트, 대기 작업, 일정 충돌, 최근 메일 | 열기, 보류, 실행 항목 만들기, 일정 조율하기 |
| 메일 | 받은편지함, 메일 상세, 새 메일, 답장 초안, 스레드 전체 | 답장 초안, 맥락 종합, 판단 포인트, 실행 항목 생성, 일정 후보 보기, 첨부 분석 |
| 일정 | 월간/주간 캘린더, 일정 상세, 회의 조율, 일정 후보 | 새 일정, 회의 조율, 일정 반영, 후보 확정, 관련 메일 열기 |
| 작업 | 내 작업, 위임한 작업, 칸반, 작업 상세 | 작업 생성, 담당자 변경, 상태 변경, 마감일 변경, 관련 메일 연결 |
| 프로젝트 | 프로젝트 목록, 프로젝트 상세, 마일스톤, 의사결정 로그 | 새 프로젝트, 프로젝트 열기, 마일스톤 추가, 의사결정 추가, 관련 문서/메일 연결 |
| 맥락 검색 | 통합 검색, 결과 상세, 관계 그래프, 타임라인 | 검색, 필터 적용, 결과 종합, 그래프 확장, 원본 열기 |
| 데이터 | 문서 저장소, 수집 파이프라인, 임베딩, 품질 점검 | 업로드, 재파싱, 임베딩 재생성, 품질 점검, 격리 |
| AI 허브 | 프롬프트 스튜디오, 워크플로우, 에이전트, 평가, 실행 이력 | 테스트 실행, 게시, 워크플로우 실행, 평가 시작, 로그 보기 |
| 보안 | 보안 대시보드, 접근 권한, 감사 로그, 외부 공유, 정책 | 권한 변경, 차단, 공유 승인/거절, 정책 배포, 보고서 내보내기 |
| 설정 | 워크스페이스, 멤버, 연결 계정, 알림, 자동화, 결제, 개발자 | 저장, 초대, 계정 연결/해제, 규칙 추가, API 키 생성, Webhook 추가 |

## Figma Deliverable

If the user provides a Figma design URL in a future iteration, use that file's `fileKey`. In this run, no pre-existing Figma URL was provided, so a new Figma design file named `Naruon Product Design System - 2026-07-02` was created after authenticated plan discovery.

Current Figma file:

- URL: https://www.figma.com/design/68b5XB58w8nwT2LYOOnikK
- File key: `68b5XB58w8nwT2LYOOnikK`
- Created from the authenticated single Figma plan `Seongho Bae's team` (`team::1408252278989737675`).
- Search policy used: `search_design_system(..., disableCodeConnect=true)`.
- Code Connect status: not used for file creation, not used as a dependency, and not used as evidence.

Required Figma pages:

1. `Source Map`
   - Place or reference the 41 canonical mockups and the 45-image reference set.
   - Include source paths, SHA-256 references, and semantic aliases.
   - Highlight the first vertical slice source images: `mockup_19.png`, `mockup_29.png`, `mockup_31.png`, `mockup_36.png`, `mockup_37.png`, `mockup_40.png`, `mockup_41.png`.
2. `Foundations`
   - Logo and brand principles from `mockup_27.png` and `mockup_41.png`.
   - Color, typography, elevation, radii, spacing, icon style, and responsive breakpoints from `mockup_27.png`, `mockup_28.png`, `mockup_29.png`, `mockup_34.png`, `mockup_41.png`.
3. `Components`
   - Navigation shell, GNB, side rail, page header, tabs, profile/notification menu.
   - Buttons, icon buttons, input fields, selects, toggles, segmented controls, chips, badges, cards, tables, drawers, modals, evidence panels, action panels, confidence badges, source chips.
   - Repeated components must be componentized; avoid flat one-off shapes.
4. `Desktop Screens`
   - First slice: Mail detail / thread analysis screen using `mockup_19.png`, `mockup_30.png`, `mockup_31.png`, `mockup_36.png`.
   - Next screens: Home from `mockup_35.png`, Context Search from `mockup_37.png`, Calendar/Task coordination from `mockup_38.png`, Data from `mockup_23.png`, AI Hub workflow from `mockup_22.png`, Security access control from `mockup_24.png`, Settings members from `mockup_26.png`.
5. `Mobile Screens`
   - Mobile login, inbox, mail detail, context synthesis, quick action sheet, profile/settings from `mockup_40.png` and `mockup_32.png`.
6. `QA Notes`
   - Figma screenshot checks, source/terminology checks, accessibility notes, missing inputs, and follow-up backlog.

Allowed Figma tools:

- `create_new_file`
- `use_figma`
- `get_libraries`
- `search_design_system`
- `get_metadata`
- `get_screenshot`
- `generate_figma_design` only if a rendered web source exists and a target fileKey is available

Forbidden Figma work:

- Creating Code Connect files
- Using Code Connect as a required dependency
- Treating Code Connect results as the source of truth
- Replacing canonical repo images with unsourced generated visuals

## First Vertical Slice

The first slice proves the core product promise with the smallest useful surface.

Flow:

1. User opens `메일`.
2. User selects a thread in project/grouped mail.
3. Naruon shows thread content plus evidence-backed `맥락 종합`.
4. Naruon extracts `판단 포인트` with confidence and source chips.
5. User chooses an execution path:
   - Create `실행 항목`
   - Generate `답장 초안`
   - Use `일정 반영`
   - Open `관계 맥락`
6. User can inspect cited evidence before accepting an action.

Primary source images:

- `mockup_19.png`: full Mail screen and AI evidence panel
- `mockup_30.png`: inbox/thread components
- `mockup_31.png`: AI decision, confidence, source, and action components
- `mockup_36.png`: applied mail/thread analysis screen
- `mockup_37.png`: related context search behavior
- `mockup_40.png`: mobile context synthesis
- `mockup_41.png`: final brand/component principles

## User Stories And Acceptance Criteria

### Story 1: Evidence-backed thread synthesis

As a workspace user, I want a selected mail thread to show `맥락 종합` with source chips and confidence so I can judge whether the AI result is reliable.

Acceptance criteria:

- The selected thread remains visible while the right panel shows `맥락 종합`.
- Each synthesis section has at least one visible source chip.
- Confidence is shown as a badge or meter and is not hidden in tooltip-only UI.
- The panel offers correction or source-opening affordances.
- Empty/loading/error states exist for unavailable synthesis.

### Story 2: Decision point extraction

As a user handling project email, I want Naruon to surface `판단 포인트` separately from ordinary summaries so I know what requires a decision.

Acceptance criteria:

- `판단 포인트` is visually distinct from `맥락 종합`.
- Each decision point has source evidence, owner/role context when available, and a priority/severity signal.
- A decision point can lead to reply, task, calendar, or project actions.
- Low-confidence decision points are marked rather than suppressed.

### Story 3: Action item creation

As a user, I want to convert a decision point into an `실행 항목` without losing the source email context.

Acceptance criteria:

- The action item creation entrypoint is visible near the decision point.
- Created action item includes title, due date or schedule candidate, source thread, assignee, and status.
- The UI preserves a backlink to the source thread or relation context.
- Confirmation and failure states are defined.

### Story 4: Calendar reflection

As a user, I want schedule candidates extracted from mail to become calendar actions after review.

Acceptance criteria:

- Candidate times are shown with conflict indicators.
- The user can inspect related email and attendees before confirming.
- `일정 반영` is the action label, not `Calendar Sync`.
- Confirmation creates or updates a calendar item and links back to the source mail.

### Story 5: Context search follow-through

As a user, I want `맥락 검색` to connect query results to email, documents, people, schedules, tasks, projects, and timelines.

Acceptance criteria:

- Results are grouped by source or type with relevance/confidence signals.
- Selecting a result opens detail plus evidence/action panel.
- Relation graph or timeline can be opened without losing the selected result.
- Source filters, date filters, people filters, and attachment filters are visible.

### Story 6: Mobile context synthesis

As a mobile user, I want the same judgment-to-action flow in a compact bottom sheet.

Acceptance criteria:

- Mobile screens keep bottom navigation and quick action patterns from `mockup_40.png`.
- `맥락 종합`, `판단 포인트`, and `실행 항목` fit without text overlap.
- Quick actions are reachable with one thumb-friendly surface.
- Evidence remains inspectable rather than hidden behind final AI conclusions.

## Component Requirements

Core reusable components:

- App shell: top GNB, left rail, local sidebar, primary work area, evidence/action panel.
- Navigation: breadcrumbs, tabs, segmented controls, mobile bottom tabs.
- List/table: inbox row, task row, document row, audit log row, member row.
- Evidence: source chip, confidence badge, source drawer, relation card, timeline item.
- Judgment: `맥락 종합` card, `판단 포인트` card, risk/issue card, recommended action card.
- Execution: action item card, reply draft card, schedule candidate card, confirm/cancel actions.
- Data states: empty, loading skeleton, success, error, offline, low-confidence, permission denied.
- Admin/security: permission toggle, role badge, audit event detail, policy status.

Design rules:

- Use quiet workbench layouts, not marketing/hero layouts.
- Use 3-column desktop composition where appropriate.
- Preserve source evidence and confidence near AI-generated content.
- Use icon buttons for compact tool actions and text buttons only for clear commands.
- Keep card radius restrained and consistent with existing mockups.
- Do not hide primary execution actions below the fold in the first slice.

## Data Analytics Measurement Plan

Live analytics data is not available in the current session. The metrics below are a proposed measurement framework, not measured performance.

| Metric | Type | Definition | Event/source assumption | Guardrail |
| --- | --- | --- | --- | --- |
| Context synthesis usage | Primary adoption | Share of selected threads where the user opens or consumes `맥락 종합` | Frontend event: `context_synthesis_viewed`; backend synthesis request logs | Latency and error rate |
| Decision-to-action conversion | Primary value | Share of `판단 포인트` views that lead to reply, task, calendar, or project action | Events: `decision_point_viewed`, `action_item_created`, `calendar_reflected`, `draft_reply_inserted` | Undo/cancel rate |
| Evidence interaction | Trust driver | Share of AI outputs where source chips are opened before execution | Event: `source_chip_opened` tied to AI output ID | Over-clicking due unclear evidence |
| Context search success | Discovery driver | Searches that result in source detail open or downstream action | Events: `context_search_submitted`, `context_search_result_opened`, `context_search_result_action_created` | Zero-result and query-refinement rate |
| Draft reply acceptance | Execution driver | Draft replies inserted, edited, and sent after AI generation | Events: `draft_reply_generated`, `draft_reply_inserted`, `draft_reply_sent` | Manual edit distance and discard rate |
| Calendar/task conversion | Execution driver | Schedule candidates or action items confirmed from mail context | Events: `calendar_reflected`, `action_item_created` | Conflict warning override rate |
| Model quality | Quality guardrail | Human correction, low-confidence rate, failed evidence binding | Feedback events plus backend evaluator output | Hallucination/source-missing rate |
| Latency | Experience guardrail | P50/P95 time from thread selection to synthesis ready | Frontend timing plus backend trace | Abandonment while loading |
| Trust/safety | Safety guardrail | Permission denials, external-share warnings, policy blocks, audit events | Security/audit logs | False-positive workflow blocks |

Recommended dashboard cuts:

- By workspace, mail source, project, model/provider, language, device class, and feature surface.
- Daily adoption trend, weekly conversion trend, and P95 latency.
- Funnel: thread selected -> synthesis viewed -> source opened -> decision point viewed -> action created.
- Quality: low-confidence rate, correction rate, discarded draft rate, source-missing rate.

Instrumentation gaps:

- Event naming and analytics destination are not confirmed in repo evidence.
- No live data warehouse or product analytics source is available in the current run.
- KPI targets should remain provisional until baseline usage is captured.

## QA And Completion Criteria

Figma/package QA must verify:

- `Source Map`, `Foundations`, `Components`, `Desktop Screens`, `Mobile Screens`, and `QA Notes` are present in the Figma plan or file.
- The first vertical slice includes Mail detail, context synthesis, decision point, and at least one execution action.
- `맥락 종합`, `판단 포인트`, `실행 항목`, `답장 초안`, `맥락 검색`, `관계 맥락`, `일정 반영`, and `판단 보조` are used correctly.
- Figma screenshots show no clipped text, incoherent overlap, blank image placeholders, wrong fonts, or leftover placeholders.
- Source images and repo paths are referenced in the Figma/source map.
- Figma Code Connect is not used.
- KPI definitions label live-data gaps and do not claim measured performance.

Current QA evidence:

- Figma Source Map page: `0:1`
- Figma Desktop page: `3:4`
- Figma Mobile page: `3:5`
- First desktop frame: `3:157` (`Desktop / Mail Detail / Evidence Review`)
- First mobile frame: `3:273` (`Mobile / Context Synthesis Bottom Sheet`)
- Expansion roadmap frame: `11:17` (`Desktop / Expansion Roadmap`)
- Added component frames: `Component / Table Row`, `Component / Source Drawer`
- Uploaded source mockup frames: `3:315` through `3:321` (`mockup_19`, `mockup_30`, `mockup_31`, `mockup_36`, `mockup_37`, `mockup_40`, `mockup_41`)
- Figma screenshots:
  - `docs/superpowers/artifacts/naruon-figma-package/qa/figma-desktop-mail-detail.png`
  - `docs/superpowers/artifacts/naruon-figma-package/qa/figma-mobile-context-sheet.png`
- Source comparison boards:
  - `docs/superpowers/artifacts/naruon-figma-package/qa/compare-desktop-mockup36-vs-figma.png`
  - `docs/superpowers/artifacts/naruon-figma-package/qa/compare-mobile-mockup40-vs-figma.png`
- Product Design QA report: `design-qa.md`
- Data Analytics validation report: `docs/superpowers/reports/2026-07-02-naruon-kpi-validation.md`

## Follow-up Backlog

1. Expand the first Figma slice into full-density production screens for Home, Calendar, Data, AI Hub, Security, and Settings.
2. Replace the local minimal components with the team's official Naruon component library if a newer source file is provided.
3. Wire a product analytics event dictionary in the repo once the tracking destination is chosen.
4. Add design-to-code tasks for navigation shell, evidence cards, confidence/source chips, and execution action cards.
5. Add interaction prototypes for source-chip opening, evidence drawer, draft reply review, and schedule confirmation.

## Explicit Assumptions

- The first useful slice is Mail + evidence + execution because it best proves Naruon's value.
- Existing repo mockups are authoritative until the user provides a newer Figma source.
- Product Design saved context is absent, so this package uses repo sources as current context.
- Figma file creation is complete for this run through the authenticated single Figma plan.
- The current Figma screens are an execution-ready first vertical slice, not a pixel-perfect clone of every existing mockup.
- No live analytics source is available, so Data Analytics outputs are definitions and measurement plans.
