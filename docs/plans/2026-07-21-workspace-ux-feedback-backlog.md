# Workspace UX feedback backlog (2026-07-21 live review)

Source: live product review by the operator on the running local stack
(1920px desktop, real browser session). Items are grouped by decision size.
The quick fixes in group A were applied in the same branch; everything else
needs its own design + PR per the repo's atomic-PR rule.

## A. Fixed immediately (this branch)

- **1920px header breakage / "two GNBs"**: the desktop header stacked a
  second control strip (시작 화면 toggle + static pills) next to an
  overflow-scrolling primary nav, so at 1920px the nav showed a scrollbar and
  the action group wrapped to a second line. Fix: startup-view choice lives in
  Settings (and the mobile drawer) only; decorative `답장 추적`/`충돌 조율`
  pills removed (inert, AGENTS.md anti-pattern); nav shrinks with a hidden
  scrollbar instead of wrapping.
- **Bell icon navigated to /security**: now deep-links to
  `/settings#notifications`, and Settings honours the hash by opening the 알림
  tab.

## B. Needs product/design decisions (each its own slice)

1. **Multi-account mail connectivity.** `tenant_configs` is a flat
   single-account row (one SMTP/IMAP/POP3 set per user+org). Operator
   expectation: N mail accounts per user with per-account nested settings
   (host/port/secret/OAuth per account), account-scoped sync state, and
   account selection on send. Requires a new `mail_accounts`-style table
   (opaque `account_uid`, two-word snake_case columns), migration from the
   flat row, `/api/accounts` list/detail contract, and Settings UI restructure
   (accounts list → nested detail forms). Biggest single item in this list.
2. **AI 모델 설정 재설계.** Current tab mixes an admin-gated org registry
   (member sessions see a raw "API request failed" banner — deny-first is by
   design, the copy is not) with the personal key card. Needs: role-aware
   rendering (member sees the personal key + read-only "운영자 관리" notice,
   not an error banner), clearer provider-vs-gateway mental model
   (contextual-orchestrator as the default gateway), and a visible "현재 내
   세션이 쓰는 모델 체인" readout (provider source, chat model, embedding
   model).
3. **멤버 탭 실체화.** Three static RBAC/ABAC description cards today.
   Either back it with a signed members/roles API (org membership, roles,
   group scopes from real data) or fold it into 보안 until that API exists.
4. **알림 탭 실체화.** Static policy cards. Needs actual per-channel
   notification preferences persisted per user (reply-wait, calendar
   conflict, connector health), and the header bell should show real pending
   notification state from signed data.
5. **자동화 탭 실체화.** Static rule descriptions. Either wire to real
   rule configuration (source-linked task creation thresholds, calendar
   writeback intent policy, self-sent knowledge classification toggles) or
   label as roadmap and remove from primary nav depth.
6. **결제 탭: 과금 정산인지 PG인지 명확화.** Operator question stands.
   Direction: cost/usage metering surface first (workspace quota, connector
   seats, per-provider AI usage — the orchestrator's cost ledger/rollup API is
   the natural signed source), PG/checkout explicitly out of scope until a
   billing provider decision exists.
7. **WebDAV 원본 설정 진입점 + 개체 스토리지.** No UI today to register
   WebDAV sources (only readiness display). Needs a Data-workspace source
   registration flow (opaque `source_uid`, capability/ETag state), and an
   adapter decision for S3 / Azure Blob backends (likely a connector-side
   adapter with the same fail-closed `adapter_not_configured` contract).
8. **AI 허브 실체 점검.** Member sessions currently get "원본 근거를 불러오지
   못했습니다" because the surface is admin/authoritative-verifier gated
   (AGENTS.md deny-first). Same treatment as (2): role-aware empty states, and
   decide which subset (prompt runs, workflow logs from real audit data) is
   member-visible.
9. **맥락 검색 ↔ 홈 통합.** Operator suggestion: global search in the header
   already exists; the dedicated 맥락 검색 page could become a results overlay
   of Home instead of a separate nav destination. Needs IA decision (nav item
   count also feeds the 1920px pressure).
10. **작업 단위 정의.** Kanban exists but the unit is ambiguous: personal
    task vs project work item vs service request. Direction to decide: tasks
    stay source-linked tickets (email-derived), projects group them, and an
    SR-style intake is a view over ticket provenance — needs an explicit
    domain doc before more Tasks UI work.
11. **일정·작업·프로젝트 유기 연동 + 회의실/온라인 미팅.** Calendar events,
    tasks, and project milestones are separate surfaces today. Needed:
    cross-links (event ↔ task ↔ project provenance), and if meeting rooms are
    shown (current calendar detail shows 회의실 A), a real room-resource model
    (rooms as bookable resources with capacity/conflicts) plus online-meeting
    join links from provider data — otherwise drop the room field as
    decoration.
12. **Deny-first 403 화면의 UX.** Recurring pattern behind several "죄다
    미구현인가" impressions: admin-gated signed surfaces render raw fetch
    errors for member sessions. One shared treatment: scoped "권한 필요"
    empty-state component distinguishing 미구현 vs 권한 없음 vs 데이터 없음.
13. **홈 인사말의 고정 페르소나 제거.** `안녕하세요, 김나루님 👋` is a
    hardcoded fixture name (asserted as a render marker across
    `page.test.tsx`). Replace with the signed-session display identity (or a
    neutral greeting) and update the test markers in the same slice.

## C. Infra directions recorded (applied outside the frontend)

- **No Ollama.** Local inference runs CUDA-native llama.cpp servers
  (chat + embeddings) fronted by contextual-orchestrator as the single
  OpenAI-compatible gateway; MLX stays the documented path on Apple-silicon
  hosts via the `NARUON_MLX_*` overlay pattern.
- **contextual-orchestrator sync `/v1/embeddings`** implemented upstream
  (with base64 encoding support for openai-python clients) so one gateway
  base_url serves both chat and embeddings.
