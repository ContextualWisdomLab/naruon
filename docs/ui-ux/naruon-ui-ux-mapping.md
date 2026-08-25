# Naruon UI/UX Definition & Mapping

## 1. Overview
Naruon is an **Evidence-based AI Email Workspace**. The core objective of the UI/UX is not to simply act as an email client or AI summarization tool, but to synthesize email, attachments, images, calendars, relations, and project contexts based on evidence to assist users in judgment and execution.

## 2. Core Philosophy & UI Terminology
Naruon's UX strictly follows three principles:
1. **Do not just shorten emails. Connect the context.**
2. **AI does not just state conclusions. It presents evidence and confidence.**
3. **Judgments must lead to execution.**

### Terminology Rules
The UI must use specific terminology to reflect this philosophy:
* ❌ AI Summary -> ⭕ 맥락 종합 (Context Synthesis)
* ❌ Summary -> ⭕ 종합, 핵심 맥락 (Synthesis, Core Context)
* ❌ Insight -> ⭕ 판단 포인트 (Decision Point)
* ❌ Todo -> ⭕ 실행 항목 (Action Item)
* ❌ Smart Reply -> ⭕ 답장 초안 (Draft Reply)
* ❌ Search -> ⭕ 맥락 검색 (Context Search)
* ❌ Network Graph -> ⭕ 관계 맥락 (Relation Context)
* ❌ Calendar Sync -> ⭕ 일정 반영 (Reflect Calendar)
* ❌ AI Assistant -> ⭕ 판단 보조 (Judgment Assist)

## 3. Core GNB & UI Organization
The application is structured into 10 Main Global Navigation Bar (GNB) areas:

### 3.1 홈 (Home)
* **Key Sections:** 오늘의 판단 포인트 (Today's Decision Points), 대기 작업 (Pending Tasks), 일정 충돌 (Calendar Conflicts), 최근 메일 (Recent Emails).
* **Key Actions:** 열기 (Open), 보류 (Hold), 실행 항목 만들기 (Create Action Item), 일정 조율하기 (Coordinate Calendar).

### 3.2 메일 (Mail)
* **Key Sections:** 받은편지함 (Inbox), 메일 상세 (Mail Detail), 새 메일 (Compose), 답장 초안 (Draft Reply), 스레드 전체 (Thread Entire View).
* **Key Actions:** AI 답장 초안 (AI Draft Reply), 맥락 종합 (Context Synthesis), 판단 포인트 (Decision Points), 실행 항목 생성 (Create Action Item), 일정 후보 보기 (View Calendar Candidates), 첨부 분석 (Analyze Attachments), 스레드 병합/분리 (Merge/Split Thread).
* **UI Focus:** Show probability confidence, allow users to merge/split threads, provide source bindings for AI outputs.

### 3.3 일정 (Calendar)
* **Key Sections:** 월간/주간 캘린더 (Monthly/Weekly Calendar), 일정 상세 (Calendar Detail), 회의 조율 (Coordinate Meeting), 일정 후보 (Calendar Candidates).
* **Key Actions:** 새 일정 (New Event), 회의 조율 (Coordinate Meeting), 일정 반영 (Reflect Calendar), 후보 확정 (Confirm Candidate), 메일 열기 (Open Related Mail).

### 3.4 작업 (Task)
* **Key Sections:** 내 작업 (My Tasks), 위임한 작업 (Delegated Tasks), 칸반 (Kanban), 작업 상세 (Task Detail).
* **Key Actions:** 작업 생성 (Create Task), 담당자 변경 (Change Assignee), 상태 변경 (Change Status), 마감일 변경 (Change Due Date), 관련 메일 연결 (Link Related Mail).

### 3.5 프로젝트 (Project)
* **Key Sections:** 프로젝트 목록 (Project List), 프로젝트 상세 (Project Detail), 마일스톤 (Milestone), 의사결정 로그 (Decision Log).
* **Key Actions:** 새 프로젝트 (New Project), 프로젝트 열기 (Open Project), 마일스톤 추가 (Add Milestone), 의사결정 추가 (Add Decision), 관련 문서/메일 연결 (Link Context Graph Edge).

### 3.6 맥락 검색 (Context Search)
* **Key Sections:** 통합 검색 (Unified Search), 결과 상세 (Result Detail), 관계 그래프 (Relation Graph), 타임라인 (Timeline).
* **Key Actions:** 검색 (Search), 필터 적용 (Apply Filter), 맥락 종합 (Selected Result Synthesis), 그래프 확장 (Expand Graph), 타임라인 항목 열기 (Open Source Detail).

### 3.7 데이터 (Data)
* **Key Sections:** 문서 저장소 (Document Store), 수집 파이프라인 (Ingestion Pipeline), 임베딩 (Embedding Job Status), 품질 점검 (Quality Check).
* **Key Actions:** 업로드 (Upload), 재파싱 (Reparse), 임베딩 재생성 (Re-embed), 품질 점검 (Run Quality Suite), 격리 (Quarantine), HWP 변환 (HWP Convert).

### 3.8 AI 허브 (AI Hub)
* **Key Sections:** 프롬프트 스튜디오 (Prompt Studio), 워크플로우 (Workflow), AI 에이전트 (AI Agent), 평가 (Evaluation), 실행 이력 (Execution History).
* **Key Actions:** 테스트 실행 (Run Sandbox Test), 게시 (Publish), 워크플로우 실행 (Run Automation), 에이전트 실행 (Run Agent), 평가 시작 (Start Evaluation), 로그 보기 (View Run Log).

### 3.9 보안 (Security)
* **Key Sections:** 보안 대시보드 (Security Dashboard), 접근 권한 (Access Control), 감사 로그 (Audit Log), 외부 공유 (External Share), 정책 (Policies).
* **Key Actions:** 권한 변경 (Update RBAC/ABAC), 사용자 차단 (Revoke Access), 공유 승인/거절 (Approve/Reject Share), 감사 로그 상세 (View Event Detail), 정책 배포 (Publish Policy), 보고서 내보내기 (Export Report).

### 3.10 설정 (Settings)
* **Key Sections:** 워크스페이스 (Workspace), 멤버 (Members), 연결 계정 (Connected Accounts), 알림 (Notifications), 자동화 (Automations), 결제 (Billing), 개발자 (Developer).
* **Key Actions:** 저장 (Save), 멤버 초대 (Invite Member), 계정 연결 (Connect OAuth), 연결 해제 (Revoke Integration), 규칙 추가 (Add Automation Rule), API 키 생성 (Generate API Key), Webhook 추가 (Add Webhook).

## 4. UI Design Mockups (Phase 1 & 2)
All Naruon UI/UX visual source material is consolidated under `docs/ui-ux/`. This directory is the unified asset repository for front-end implementation, PR reviews, and LLM Agent handoff. Keep the existing image paths stable: the dated reference set has SHA-256 provenance, while `mockups/` remains the canonical design image set.

**Unified UI/UX Asset Repository:** `docs/ui-ux/`
* **Agent text map:** `docs/ui-ux/naruon-ui-ux-mapping.md`
* **Canonical mockup image set:** `docs/ui-ux/mockups/`
* **Durable reference image set:** `docs/ui-ux/reference-set-2026-06-18/images/`

**LLM Agent instruction:** An LLM Agent implementing or reviewing Naruon UI must first read this text map, then directly open the relevant original image files under `docs/ui-ux/mockups/` and `docs/ui-ux/reference-set-2026-06-18/images/` to verify layout, spacing, visual hierarchy, state chips, and annotated button flows. The descriptions below are a text navigation aid for agents that cannot see the figures immediately; they do not replace the source PNG files.

한국어 요지: LLM Agent는 이 파일의 설명만으로 판단하지 말고, 구현 또는 리뷰 대상과 관련된 `mockup_XX.png` 또는 `ui-ux-reference-XX.png` 원본 그림 파일을 직접 열어 화면 구성과 상호작용 주석을 확인해야 한다.

*Note: The mockups contain design definitions for the components above and must be translated into the Naruon Design System following the Evidence-based UI principles (confidence intervals, citation binding, and human correction UI).*

### 4.1 Common Visual Structure
The mockups use a quiet workbench layout rather than a marketing layout. Most desktop screens follow a 3-column shell:

1. **Global navigation:** Naruon logo on the left, top GNB items for Home, Mail, Calendar, Tasks (작업), Projects, Context Search (맥락 검색), Data, AI Hub, Security, and Settings, plus global search, notifications, app switcher/help, and profile controls on the right. Section 3 lists the same ten areas; this GNB list must not omit 작업 or 맥락 검색.
2. **Local navigation:** A left sidebar lists the current domain's folders, filters, saved views, labels, and support/help controls.
3. **Primary work area:** The center area carries the active list, calendar, editor, canvas, table, or search result.
4. **Evidence or action panel:** The right side is often a detail drawer or AI/evidence panel showing source metadata, confidence, related people, attached files, schedule proposals, decision points, risks, and executable actions.
5. **Evidence-based UI language:** Repeated building blocks include `맥락 종합`, `판단 포인트`, `실행 항목`, confidence badges, source chips, relation graphs, timelines, priority/status chips, and buttons that turn judgment into calendar, reply, task, or approval actions.

### 4.2 Mockup File Map

| File | What It Defines | Text Description for Agents |
|---|---|---|
| `mockup_01.png` | Settings button action map | A settings detail board with seven settings pages: Workspace, Members, Connected Accounts, Notifications, Automation, Billing, and Developer. Each page has a left local settings nav, center content cards, and numbered purple hotspots showing interactions such as editing workspace info, inviting members, changing member roles, disconnecting accounts, adding automation rules, opening billing details, changing plans, creating API keys, and adding webhooks. Empty and loading states are shown at the bottom of each page group. |
| `mockup_02.png` | Project button action map | A project-domain board split into Project List, Project Detail, Milestone, and Decision Log. The list area shows filters, project rows, status/progress rings, owners, update dates, and actions for creating/opening/filtering projects. The detail area shows tabs, progress, owner avatars, related information, and right-side numbered actions for creating tasks, inviting teams, connecting documents, and opening related email. Milestones use a vertical timeline and decision logs use a table with filter and create actions. |
| `mockup_03.png` | Context Search button action map | A four-panel map for context search: integrated search, result detail, relation graph, and timeline. It shows query input, source category chips, filters, result cards with confidence badges, a detail pane with attached files and AI summary, a graph canvas with relationship legend and zoom controls, and a timeline of related events. Numbered action markers explain search refresh, filter application, result selection, graph expansion, node click behavior, timeline item opening, and related schedule creation. |
| `mockup_04.png` | Data button action map | A data-domain map with Document Store, Ingestion Pipeline, Embedding, and Quality Check sections. It includes document tables, upload and preview modals, pipeline cards with source-parser-clean-chunk-store steps, embedding model selection and re-run actions, quality issue lists, detail drawers, toasts, and loading/empty/error states. The visual emphasis is on source connectors, processing status, and safe operator actions. |
| `mockup_05.png` | AI Hub button action map | An AI Hub board covering Prompt Studio, Workflow, AI Agent, Evaluation, and Execution History. It shows a prompt editor with variables and model settings, a live test panel, a node-based workflow canvas, an agent detail drawer, evaluation score cards, benchmark tables, execution run lists, and log detail drawers. Numbered annotations call out test execution, publishing, opening agent detail, comparing versions, viewing logs, and retrying failed runs. |
| `mockup_06.png` | Security button action map | A security-domain board with Security Dashboard, Access Control, Audit Log, External Sharing, and Policy. It uses risk charts, user/role tables, audit event tables, external share approval cards, policy toggles, compliance checklists, and incident panels. The lower row defines dialogs and feedback patterns for risk detail, permission editing, user invitation, audit-log detail, success/error toasts, user blocking, policy save feedback, and compliance checklist expansion. |
| `mockup_07.png` | Full IA and early screen inventory | A compact map of the whole product: hero brand block, Home dashboard, Mail inbox/detail/compose/draft/thread, Calendar month/week/detail/coordination/candidates, Task list/delegated/kanban/detail, Project list/detail/milestone/decision log, Context Search search/detail/graph/timeline, Data document/pipeline/embedding/quality, AI Hub prompt/workflow/agent/evaluation/history, Security dashboard/access/audit/share/policy, Settings workspace/member/account/notification/automation/billing/developer, and common design system atoms. |
| `mockup_08.png` | Home UX assets | A Home asset sheet with the final top GNB, daily overview dashboard, KPI cards, today's core summary, decision-point cards, pending-task list, calendar conflict alerts, recent mail list, quick actions, summary KPI card variants, small widget empty/loading/error states, status chips, buttons, toggles, avatar stacks, and card styles. The main Home surface is a dashboard for judgment and execution, not a generic landing page. |
| `mockup_09.png` | Mail UX assets | A Mail asset sheet with palette, typography, icon style, inbox row variants, mail detail pane, new mail composer, AI draft reply panel, full thread view, list states, labels, toolbar actions, attachment cards, recipient input, rich text editor states, suggested reply cards, empty states, loading skeletons, sending state, success state, and offline state. It defines the core mail workflow from list selection to evidence-backed reply/action. |
| `mockup_10.png` | Calendar UX assets | A Calendar asset sheet with monthly calendar, weekly time-grid calendar, event detail drawer, meeting coordination form, AI schedule candidate cards, event category chips, attendee avatars, attendance status chips, meeting-room selector, RSVP buttons, conflict warning, mini calendar widget, empty-state widget, icon set, button styles, and date/time input fields. |
| `mockup_11.png` | Task UX assets | A Task asset sheet with priority tags, status tags, due-date chips, My Tasks list, Delegated Tasks list, Kanban board, Task Detail panel, task creation modal, assignee/participant avatar controls, project/label filters, status dropdown, priority badges, due-date examples, activity log, progress bar, checklist/radio controls, attachment row, notification badge, and view toggle buttons. |
| `mockup_12.png` | Project UX assets | A Project asset sheet with project list, quick filter bar, project cards, project detail, progress rings, status chips, priority chips, owner/participant avatars, milestone timeline, decision log, related mail/document/task previews, empty state, and responsive breakpoints. The project detail uses tabs for overview, milestones, tasks, documents, decision logs, mail, dashboard, and settings. |
| `mockup_13.png` | Context Search UX assets | A Context Search asset sheet with integrated search, result detail, relation graph, timeline, source chips, confidence badges, result-card types, graph node types, relation legend, timeline markers, and AI panel components. The layout ties search results to people, documents, email, calendar events, projects, confidence, and relationship strength. |
| `mockup_14.png` | Data UX assets | A Data asset sheet with four large columns: Document Store, Ingestion Pipeline, Embedding, and Quality Check. It defines metrics, search/filter controls, file/folder tables, metadata panels, source connector cards, pipeline step cards, pipeline history, embedding job lists, embedding progress cards, model info, reprocess controls, quality issue lists, issue details, thumbnails, history, and shared badges for status, severity, progress, toggles, checkboxes, file icons, table actions, and pagination. |
| `mockup_15.png` | AI Hub UX assets | An AI Hub asset sheet organized into Prompt Studio, Workflow, AI Agent, Evaluation, and Execution History. It includes prompt template cards, prompt editor fields, model settings, version history, a workflow canvas and node components, node setting panels, agent cards and detail fields, evaluation summary/score/benchmark tables, execution history lists, execution logs, detailed run metadata, status badges, model selectors, and action feedback toasts. |
| `mockup_16.png` | Settings UX assets | A Settings asset sheet covering Workspace, Members, Connected Accounts, Notifications, Automation, Developer/API, Billing, and shared badges. It shows organization profile cards, workspace security and plan cards, member lists and invite drawer, integration connection lists, connector detail, notification toggles, webhook endpoint form, automation rule cards, rule creation form, API key cards, webhook settings, invoice/billing card, and role/status/priority/plan badges. |
| `mockup_17.png` | Security UX assets | A Security asset sheet with dashboard risk cards, donut charts, compliance status, access matrix, recent permission changes, MFA adoption, audit log summary/table, incident detail panel, external sharing request cards, link policy settings, policy toggle list, compliance checklist, risk severity chips, status badges, security icon buttons, toggles, checkboxes, progress indicators, warning/info banners, and empty states. |
| `mockup_18.png` | Early integrated desktop board | A combined application board showing the original dark brand splash, login, wide GNB, collapsed sidebar, Home dashboard, inbox, thread detail, compose screen, AI draft screen, full thread view, weekly calendar, meeting coordination, task board, task detail, project detail, relationship graph, attachment preview and analysis, run detail, and notification center. This is a compact reference for the product's end-to-end workflow from email to decision to execution. |
| `mockup_19.png` | Full Mail screen | A full desktop Mail screen. Left sidebar contains compose, mailbox folders, user folders, labels, and storage usage. Center column has search, tabs, filters, mail rows, labels, unread markers, and pagination. Right detail area shows the selected thread, message body, inline replies, action bar, AI `맥락 종합`, `판단 포인트`, related schedule candidates, relation-context card, attachment file list, and quick actions such as calendar registration, task creation, customer folder move, meeting participation, and AI reply draft generation. |
| `mockup_20.png` | Full Calendar screen | A full Calendar month view. Left sidebar contains calendar scopes, mini calendar, and filters. The top area has metric cards for today's events, coordination waiting, email-extracted schedule candidates, and this week's meeting time. Center area is a color-coded month grid with month/week/day switching. Right panel shows selected event details, attendees, linked email and attachments, attendance status, edit/reconfirm/mail actions, and AI schedule proposals with candidate time slots and confirm buttons. |
| `mockup_21.png` | Full Prompt Studio screen | A full AI Hub Prompt Studio screen. Left sidebar lists prompt template categories. Center editor has system/user/assistant tabs, prompt name, system prompt textarea, variables, model selection, temperature, response style, and output format. Right live preview panel has sample input, generated result, regenerate action, quality checklist, and version history. Bottom panels show recent test results, deployment history, and usage metrics. |
| `mockup_22.png` | Full Workflow Editor screen | A full AI Hub Workflow Editor screen. Left node palette groups input, AI analysis, condition, approval, notification, data, and tips. Center canvas shows a flow from start to mail collection, attachment parsing, context synthesis, decision-point extraction, approval branch, result storage, Slack notification, and finish. Right drawer edits the selected node's basic settings, file types, retry policy, SLA, prompt template, and delete action. Bottom panels show recent runs, execution summary, and execution logs. |
| `mockup_23.png` | Full Document Store screen | A full Data Document Store screen. Left data sidebar lists document-related subareas and storage usage. Top metric cards show total documents, recent updates, OCR completion, and embedding coverage. Center table lists documents with source, owner, modified date, tags, status, and embedding percentage. Right detail drawer shows selected document metadata, preview, extracted entities, tags, embedding state, related projects, permissions, and action buttons for preview, classification edit, re-embedding, and more. |
| `mockup_24.png` | Full Access Control screen | A full Security Access Control screen. Left security sidebar lists dashboard, access control, audit log, data policy, external sharing, warnings, and compliance. Main area shows access metrics, filters, user table, permission change history, and recent approval requests. Right drawer shows selected user identity, role/status, permission tabs, project/document/folder/share/API permission toggles, approval workflow, permission expiration, MFA status, access reason, last change, and save/cancel actions. |
| `mockup_25.png` | Full Search Result Detail screen | A context-heavy search result detail screen under the Project/Search experience. Left rail contains filters for time range, source, type, people, project, tag, importance, and downstream inclusion. Center area starts with the core topic `Q2 출시 계획 우선순위`, relation counts, and topic sharing actions, then presents summary, key decisions, related threads, attachments, meeting timeline, tasks, people, related projects, related timeline, and decision flow. Right panel contains AI synthesis, key context, decision points, major risks, recommended actions, and a relation graph. |
| `mockup_26.png` | Full Settings Members screen | A full Settings Members and Permissions screen. Left settings sidebar lists workspace, members, connected accounts, notifications, automation, security, billing, and developer. Top metric cards show total members, pending invites, guest seats, and available seats. Center table lists users with department, role, group, seat type, recent activity, MFA, and status. Right drawer shows selected member profile, group membership, assigned projects, permission scope, SSO sync state, recent activity, and actions for permission edit and invite resend. |
| `mockup_27.png` | Brand foundation assets | A brand foundation board. It defines primary logo, symbol mark, wordmark, dark-background logo variants, minimum logo sizes, color tokens, typography scale, icon stroke/radius/grid principles, example icons, and Naruon brand principles: `맥락 종합`, `판단 보조`, `실행 중심`, `관계 이해`, and `연결된 흐름`. |
| `mockup_28.png` | Form and input assets | A form/input asset board. It defines primary/secondary/tertiary/ghost/destructive buttons with default/hover/active/disabled states and sizes; text/password/search/tag/textarea fields with error/help/success states; select/dropdown, checkbox, radio, toggle, segmented control, and stepper controls; login/SSO buttons; alert badges, chips, status tags; confirmation/info/form/warning modals; and fullscreen drawer filter examples. |
| `mockup_29.png` | Navigation and shell assets | A navigation shell board. It specifies desktop GNB states and spacing, expanded left sidebar and compact icon rail states, page-header and breadcrumb patterns, text/icon/compact tab systems, dropdown menus, notification panel, profile menu, mobile app bars and bottom tab bars, 3-column layout grid, gutters, right panel width, and responsive breakpoints. |
| `mockup_30.png` | Inbox and thread assets | A mail-thread component board. It defines inbox row variants, detailed thread header, message bubble/card patterns, attachment cards, link previews, image thumbnails, reply action bars, extra action icons, empty state, no-result state, and loading skeleton. The right side shows message cards with authors, timestamps, attachments, reactions, mentions, and comments. |
| `mockup_31.png` | AI insight and decision assets | An AI decision component board. It defines the three main insight cards `맥락 종합`, `판단 포인트`, and `실행 항목`; progress/risk/decision/recommended-action cards; stakeholder/document/calendar/mail relation cards; KPI/stat cards; priority and status visual language; an AI assist panel explaining relevance, recommended next actions, related people, and reference threads; tags, confidence ratings, source labels, update-time chips, action buttons, and collapse/expand controls. |
| `mockup_32.png` | Calendar, task, and mobile assets | A combined Calendar/Task/Mobile asset board. Desktop assets include weekly calendar event blocks and states, schedule proposal cards, meeting proposal cards, calendar-reflect button states, task list items, draggable task cards, checklists, and task property chips. Mobile assets include login, inbox, thread detail, context synthesis bottom sheet, floating quick-action sheet, profile/settings, empty states, swipe actions, and inline toast notifications. |
| `mockup_33.png` | Login and onboarding screen | A polished desktop login/onboarding screen. Left card provides Naruon logo, welcome message, Google/Microsoft/email/enterprise SSO login options, email/password fields, remember-me checkbox, password recovery, login button, signup/admin/security links. Right hero area states the value proposition, shows `맥락 종합`, `판단 포인트`, and `실행 항목` chips, a product preview card with email AI summary, a connected calendar card, trust/security/relationship benefit blocks, language selector, and footer links. |
| `mockup_34.png` | Navigation and GNB system | A navigation system board focused on implementation rules. It shows desktop top GNB, expanded side navigation, collapsed icon rail, breadcrumb and page header pattern, tab navigation variants, notification dropdown, profile dropdown, mobile top app bar, mobile bottom tab bar, navigation color tokens, icon styles, and default/hover/active/selected state keys. |
| `mockup_35.png` | Applied Home screen | A full Home screen. Left sidebar contains compose, Home, mailbox shortcuts, AI workspace links, tags, and plan usage. Top area has search, profile, and quick action cards for decision points, calendar links, pending tasks, and quick execution. Center list shows prioritized messages. Right selected item panel shows message metadata, tags, `맥락 종합`, `판단 포인트`, `실행 항목`, and actions for calendar reflection, reply draft, and task creation. Bottom tabs expose related emails, related schedules, and related documents. |
| `mockup_36.png` | Applied Mail detail screen | A full mail/thread analysis screen. Left sidebar contains mailbox navigation, AI Hub shortcuts, project grouping, labels, and today's insight chart. Next column lists project-related threads. Center content shows a selected thread with top quick actions for calendar reflection, reply draft, and decision memo; then context synthesis, related context, confidence/progress chart, decisions, risks/issues, stakeholders, and action items. Right panel shows participants, attachments, meeting proposal, and related past mails/threads. |
| `mockup_37.png` | Applied Context Search screen | A full context search screen. It uses a large search bar with query text, filter chips for source/date/people/attachments/relevance, and a left navigation rail. Results are grouped by category cards and list rows with source icons, tags, attachments, and relevance. The center preview opens the selected email thread. Right insight panel explains why the result is relevant, lists related people, related schedules, key decisions, and suggested next actions. |
| `mockup_38.png` | Applied Home calendar/task screen | A home-style execution dashboard centered on calendar and task coordination. Left rail lists Home, Calendar, Action Items, Connected Mail, Decisions, Documents, Projects, and Insights. Main top is a weekly calendar; lower panels show connected emails and action items. Right panels show decisions needing action and proposed schedule actions. The screen demonstrates turning email/calendar context into decisions, schedule reflections, and tasks in one workspace. |
| `mockup_39.png` | Low-fidelity UX architecture board | A grayscale wireframe board that defines the product flow: Login -> Inbox -> Thread Analysis -> Judgment -> Execution. It includes rough layouts for login, inbox/dashboard, thread detail/analysis view, context search, schedule/task coordination, settings/admin, mobile responsive states, IA tree, core user flow, design principles, and notes that the later high-fidelity UI should follow this structure. |
| `mockup_40.png` | Mobile workspace concept | A mobile design board with six phone screens: login, inbox, mail detail, context synthesis, schedule/execution quick action sheet, and profile/settings. It uses bottom navigation, a floating AI action button, chips for priority/context, compact AI summary cards, calendar/task actions, and profile preference links. The bottom band restates the mobile principles of context synthesis, judgment assist, execution, relationship understanding, and connected flow. |
| `mockup_41.png` | Final brand and component board | A final brand board with large Naruon logo and tagline, logo system, Korean/English type recommendations, color palette, brand values, micro UI examples, an email thread insight card, action buttons for calendar/reply/task, app icon, favicon, and social tile. It summarizes the final product identity: Naruon is not a tool for shortening email, but an AI email workspace that connects fragmented context to better judgment and execution. |

### 4.3 Reference Set File Map

`docs/ui-ux/reference-set-2026-06-18/` is a durable 45-image reference set captured for the June 18, 2026 PR review cycle. Its `README.md` lists the image set, and `sources.tsv` records each reference file's stable SHA-256 digest and repository path. Use `sources.tsv` to verify reference-set file integrity before assuming that a copied or renamed image is the same asset.

The reference set contains four additional button-action maps plus 41 visual/semantic equivalents of the mockup files above. Exact binary hashes should be checked before deduplicating files; when two files are confirmed identical, reuse the existing description instead of writing a second long description. For this mapping document, the 41 repeated concepts are intentionally represented as aliases to the existing mockup descriptions.

| Reference File | Mapping | Text Description for Agents |
|---|---|---|
| `ui-ux-reference-01.png` | Additional dashboard action map | Dashboard detail page and button action map. It shows the Naruon dashboard broken into overview metrics, decision/priority cards, pending work, schedule or calendar summaries, recent mail/context lists, right-side insight/action panels, bottom utility components, and numbered interaction callouts. Use it when reviewing dashboard-level buttons, quick actions, drill-downs, and state feedback across the Home/Dashboard experience. |
| `ui-ux-reference-02.png` | Additional mail action map | Mail detail page and button action map. It expands the Mail workflow beyond the component sheet by numbering inbox actions, message selection, thread detail controls, AI reply draft insertion, attachment/file actions, search/filter states, empty/loading/offline states, and action mapping for reply, forward, thread navigation, scheduling, task creation, and AI-assisted context panels. |
| `ui-ux-reference-03.png` | Additional calendar action map | Calendar detail page and button action map. It documents calendar list/month/week/detail areas, event creation and editing, meeting coordination, schedule candidate confirmation, attendance/RSVP controls, linked mail and attachment access, mini calendar/filter behavior, AI suggestion panels, and state components for conflict, loading, and confirmation feedback. |
| `ui-ux-reference-04.png` | Additional task action map | Task detail page and button action map. It shows task list, delegated task, kanban, task detail, task creation, filters, priority/status/due-date chips, assignee controls, checklist editing, activity logs, related source links, and numbered button flows for creating, opening, assigning, changing status, and connecting tasks back to mail/project evidence. |
| `ui-ux-reference-05.png` | Alias of `mockup_02.png` | Project button action map. Use the `mockup_02.png` row for the detailed description. |
| `ui-ux-reference-06.png` | Alias of `mockup_03.png` | Context Search button action map. Use the `mockup_03.png` row for the detailed description. |
| `ui-ux-reference-07.png` | Alias of `mockup_04.png` | Data button action map. Use the `mockup_04.png` row for the detailed description. |
| `ui-ux-reference-08.png` | Alias of `mockup_05.png` | AI Hub button action map. Use the `mockup_05.png` row for the detailed description. |
| `ui-ux-reference-09.png` | Alias of `mockup_06.png` | Security button action map. Use the `mockup_06.png` row for the detailed description. |
| `ui-ux-reference-10.png` | Alias of `mockup_01.png` | Settings button action map. Use the `mockup_01.png` row for the detailed description. |
| `ui-ux-reference-11.png` | Alias of `mockup_07.png` | Full IA and early screen inventory. Use the `mockup_07.png` row for the detailed description. |
| `ui-ux-reference-12.png` | Alias of `mockup_08.png` | Home UX assets. Use the `mockup_08.png` row for the detailed description. |
| `ui-ux-reference-13.png` | Alias of `mockup_09.png` | Mail UX assets. Use the `mockup_09.png` row for the detailed description. |
| `ui-ux-reference-14.png` | Alias of `mockup_10.png` | Calendar UX assets. Use the `mockup_10.png` row for the detailed description. |
| `ui-ux-reference-15.png` | Alias of `mockup_11.png` | Task UX assets. Use the `mockup_11.png` row for the detailed description. |
| `ui-ux-reference-16.png` | Alias of `mockup_12.png` | Project UX assets. Use the `mockup_12.png` row for the detailed description. |
| `ui-ux-reference-17.png` | Alias of `mockup_13.png` | Context Search UX assets. Use the `mockup_13.png` row for the detailed description. |
| `ui-ux-reference-18.png` | Alias of `mockup_14.png` | Data UX assets. Use the `mockup_14.png` row for the detailed description. |
| `ui-ux-reference-19.png` | Alias of `mockup_15.png` | AI Hub UX assets. Use the `mockup_15.png` row for the detailed description. |
| `ui-ux-reference-20.png` | Alias of `mockup_17.png` | Security UX assets. Use the `mockup_17.png` row for the detailed description. |
| `ui-ux-reference-21.png` | Alias of `mockup_16.png` | Settings UX assets. Use the `mockup_16.png` row for the detailed description. |
| `ui-ux-reference-22.png` | Alias of `mockup_18.png` | Early integrated desktop board. Use the `mockup_18.png` row for the detailed description. |
| `ui-ux-reference-23.png` | Alias of `mockup_19.png` | Full Mail screen. Use the `mockup_19.png` row for the detailed description. |
| `ui-ux-reference-24.png` | Alias of `mockup_20.png` | Full Calendar screen. Use the `mockup_20.png` row for the detailed description. |
| `ui-ux-reference-25.png` | Alias of `mockup_21.png` | Full Prompt Studio screen. Use the `mockup_21.png` row for the detailed description. |
| `ui-ux-reference-26.png` | Alias of `mockup_22.png` | Full Workflow Editor screen. Use the `mockup_22.png` row for the detailed description. |
| `ui-ux-reference-27.png` | Alias of `mockup_23.png` | Full Document Store screen. Use the `mockup_23.png` row for the detailed description. |
| `ui-ux-reference-28.png` | Alias of `mockup_24.png` | Full Access Control screen. Use the `mockup_24.png` row for the detailed description. |
| `ui-ux-reference-29.png` | Alias of `mockup_25.png` | Full Search Result Detail screen. Use the `mockup_25.png` row for the detailed description. |
| `ui-ux-reference-30.png` | Alias of `mockup_26.png` | Full Settings Members screen. Use the `mockup_26.png` row for the detailed description. |
| `ui-ux-reference-31.png` | Alias of `mockup_27.png` | Brand foundation assets. Use the `mockup_27.png` row for the detailed description. |
| `ui-ux-reference-32.png` | Alias of `mockup_28.png` | Form and input assets. Use the `mockup_28.png` row for the detailed description. |
| `ui-ux-reference-33.png` | Alias of `mockup_29.png` | Navigation and shell assets. Use the `mockup_29.png` row for the detailed description. |
| `ui-ux-reference-34.png` | Alias of `mockup_30.png` | Inbox and thread assets. Use the `mockup_30.png` row for the detailed description. |
| `ui-ux-reference-35.png` | Alias of `mockup_31.png` | AI insight and decision assets. Use the `mockup_31.png` row for the detailed description. |
| `ui-ux-reference-36.png` | Alias of `mockup_32.png` | Calendar, task, and mobile assets. Use the `mockup_32.png` row for the detailed description. |
| `ui-ux-reference-37.png` | Alias of `mockup_33.png` | Login and onboarding screen. Use the `mockup_33.png` row for the detailed description. |
| `ui-ux-reference-38.png` | Alias of `mockup_34.png` | Navigation and GNB system. Use the `mockup_34.png` row for the detailed description. |
| `ui-ux-reference-39.png` | Alias of `mockup_35.png` | Applied Home screen. Use the `mockup_35.png` row for the detailed description. |
| `ui-ux-reference-40.png` | Alias of `mockup_36.png` | Applied Mail detail screen. Use the `mockup_36.png` row for the detailed description. |
| `ui-ux-reference-41.png` | Alias of `mockup_37.png` | Applied Context Search screen. Use the `mockup_37.png` row for the detailed description. |
| `ui-ux-reference-42.png` | Alias of `mockup_38.png` | Applied Home calendar/task screen. Use the `mockup_38.png` row for the detailed description. |
| `ui-ux-reference-43.png` | Alias of `mockup_39.png` | Low-fidelity UX architecture board. Use the `mockup_39.png` row for the detailed description. |
| `ui-ux-reference-44.png` | Alias of `mockup_40.png` | Mobile workspace concept. Use the `mockup_40.png` row for the detailed description. |
| `ui-ux-reference-45.png` | Alias of `mockup_41.png` | Final brand and component board. Use the `mockup_41.png` row for the detailed description. |
