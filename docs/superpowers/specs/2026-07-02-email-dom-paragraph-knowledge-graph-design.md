# Email DOM, Paragraph, And Knowledge Graph Design

Date: 2026-07-02

Repo: `ContextualWisdomLab/naruon`

Figma/FigJam artifact: https://www.figma.com/board/zXkcwT2E2aBtNhMVznLT4l?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=a97d7c74-02e9-4f7c-8e8f-c61c4659aa70&architecture=true

## Goal Registered

ContextualWisdomLab/naruon의 이메일 본문과 첨부파일 파싱을 DOM 구조 및 문단 단위로 정규화하고 지식 그래프로 적재하는 기능을, 20억 원 수준 판매 가능 제품 기준으로 설계한다. 구체적으로 현행 repo 구조와 민감메일 테스트 제약을 확인하고, 별도 라이브러리/서브모듈/모노레포 옵션을 비교한 뒤, 제품 UX, 데이터 품질, KPI, Figma 산출물, 구현 단계, 검증/PR 전략까지 포함한 실행 가능한 계획과 repo 내 설계 산출물을 만든다.

## Decision Frame

20억 원에 판매 가능한 프로그램이라는 목표는 단일 기능 구현 완료가 아니라 실사 가능한 제품 자산 기준으로 본다. 구매자나 파일럿 고객이 확인해야 할 것은 다음이다.

- 민감한 업무 메일과 첨부를 외부 유출 없이 수집, 파싱, 검색, 증거 제시까지 처리한다.
- 본문과 첨부를 단순 문자열로 flatten하지 않고, 원본 위치와 구조를 보존한 DOM 노드와 문단 세그먼트로 만든다.
- 각 세그먼트가 이메일, 스레드, 첨부, 문서, 사람, 일정, 작업, 결정 근거로 연결되어 검색 결과와 AI 판단의 citation으로 쓰인다.
- 운영자가 Data workspace에서 파싱률, 문단화율, 임베딩 커버리지, 그래프 edge 품질, 실패 사유를 볼 수 있다.
- 실제 브라우저 화면에서 메일 상세, 첨부 분석, 맥락 검색, 관계 맥락, 데이터 품질 화면이 같은 근거 체계를 보여준다.

시장 맥락상 엔터프라이즈 RAG와 enterprise knowledge graph는 각각 빠르게 커지는 카테고리이며, Microsoft 365 Copilot connectors 같은 제품도 보안 권한을 유지한 외부 데이터 연결을 핵심 가치로 둔다. Naruon의 포지션은 범용 검색 엔진이 아니라, 고객 소유 메일과 첨부를 판단과 실행으로 연결하는 evidence graph workspace다.

## Current State Evidence

Live GitHub state checked on 2026-07-02:

- Default branch is `develop`.
- Repo is public and license metadata is `Other`, matching proprietary product posture.
- Open PRs #889 to #894 target `develop` and are currently blocked, so new implementation work should use a focused branch and expect central required checks.
- Fresh clone on macOS shows case-collision working tree noise for `.Jules/palette.md` versus `.jules/palette.md` and `.Jules/sentinel.md` versus `.jules/sentinel.md`; do not touch those files in this work.
- CodeGraph is not initialized in this fresh clone. Per AGENTS.md, `codegraph init -i` should be run only after user confirmation.

Relevant current implementation:

- `backend/services/email_parser.py` parses `.eml` bytes with Python email policy, extracts sanitized sender, recipients, subject, date, body, and text/plain attachments.
- HTML body currently falls back to sanitized text. The active DOM structure is not preserved.
- Attachments are represented as dictionaries with `filename` and `content`; only simple text attachments are first-class today.
- `backend/services/email_import_service.py` supports `.eml`, `.zip`, and `.mbox`, enforces upload quotas, rejects symlinks through `O_NOFOLLOW`, deduplicates by message/fingerprint, embeds email body plus attachment content, and falls back to zero vectors only when provider embedding is unavailable.
- `backend/db/models.py` has legacy `email_records` and `email_attachments` with pgvector embeddings, plus newer `email_raws`, `email_messages`, `email_instances`, `email_threads`, and `email_thread_edges` domain tables.
- `backend/api/search.py` already unions email body search and attachment content search, but returns email-level results rather than DOM/paragraph/source-path results.
- `backend/api/data.py` exposes source-backed Data workspace metrics for emails, attachments, embedding coverage, and attachment content quality, but not DOM coverage, paragraphization coverage, graph edge coverage, or parser failure taxonomy.
- `docs/ui-ux/naruon-ui-ux-mapping.md` defines Naruon as an evidence-based AI email workspace. The canonical UX terms are `맥락 종합`, `판단 포인트`, `실행 항목`, `맥락 검색`, and `관계 맥락`.

Security and privacy constraints:

- Real work email corpora are highly sensitive. Use local or approved private self-hosted runner paths only; do not upload real mail to public CI or external test services.
- Parsed display fields must remain sanitized. Do not store or expose active HTML/script markup through email APIs.
- Browser code must keep the signed HttpOnly cookie path and same-origin `/api/*` proxy. Do not reintroduce public identity headers or browser-stored bearer tokens.
- New DB names must use at least two-word `snake_case`; avoid new single-token columns like `id`, `title`, `status`, or `priority`.

## Recommended Architecture

Build this first as an internal backend package under `backend/services/content_graph/`, not as a submodule.

Reasoning:

- The first version needs direct access to Naruon auth scope, SQLAlchemy models, migrations, embedding provider selection, email import lifecycle, and Data workspace status contracts.
- A submodule would add versioning and CI friction before the API boundary is proven.
- An internal package can still have a clean public interface and later be extracted into `naruon-content-graph` as a private PyPI package, Git subtree, or standalone repo when a second consumer exists.

Extraction trigger:

- Keep it internal until at least two consumers use it, such as Naruon plus a connector/CLI, or until a commercial customer needs the parser SDK separately.
- Extract only after the parser API, segment schema, failure taxonomy, and golden corpus tests have stabilized.
- Prefer a private package or subtree over a git submodule. Use a submodule only if a customer requires independent licensing, independent release cadence, and separate repository access control.

## Core Pipeline

1. Source envelope
   - Normalize source metadata before parsing.
   - Inputs: email bytes, MIME parts, attachment bytes, workspace documents.
   - Output: `SourceEnvelope` with owner scope, organization scope, workspace scope, source kind, provider/source UID, content hash, and display-safe filename/subject.

2. MIME and DOM parser
   - Reuse Python `email` stdlib for RFC/MIME.
   - Build a normalized content tree from message body and attachments.
   - For HTML, start with a small safe parser that records tag hierarchy, text nodes, heading/list/table boundaries, and sanitized display text. Add BeautifulSoup/lxml only if golden corpus cases prove stdlib parsing is insufficient.
   - For XML-like inputs, use `defusedxml`.
   - For text/plain and Markdown, use deterministic paragraph and heading heuristics.
   - For PDF/DOCX/HWP, create adapter interfaces first and mark unsupported binary content as `parser_pending` rather than pretending success.

3. Paragraph segmenter
   - Split DOM text into stable paragraph-level segments.
   - Preserve `node_path`, `ordinal_index`, source byte/part hints when available, heading ancestry, attachment filename, and content hash.
   - Use existing `langchain-text-splitters` only for overflow chunking after paragraph units are created; paragraph is the primary unit.

4. Persistence
   - Add append-only parse runs and source-linked content tables.
   - Store sanitized text and structural provenance, not active HTML.
   - Keep raw provider bytes behind existing raw/source boundaries; do not expose raw bodies in user-facing APIs.

5. Embedding
   - Generate vectors for paragraph segments and optionally aggregate to email/attachment level.
   - Use active organization provider `embedding_model` and `base_url` exactly as email import does.
   - Batch by segment count and byte budget. Fall back per item and record failure reason rather than silently degrading an entire import.

6. Graph extraction
   - Create first-order deterministic edges before LLM extraction:
     - `contains`: email to MIME part, part to DOM node, node to segment.
     - `attached_to`: attachment to email.
     - `belongs_to_thread`: email to thread.
     - `sent_by`, `sent_to`, `cc_to`: segment/email to participants.
     - `references_date`: segment to parsed date/time mention when deterministic.
     - `mentions_file`: segment to attachment/document filename mention.
   - Add model-derived edges only after deterministic provenance exists:
     - `supports_decision`, `creates_action_item`, `mentions_project`, `blocks_schedule`, `same_topic_as`.
   - Every model-derived edge must store confidence, prompt/model version, evidence segment UID, and parser run UID.

7. Retrieval and UX
   - Extend `/api/search` to return segment-level hits with source path, attachment filename, paragraph snippet, graph neighborhood summary, and email/thread rollup.
   - Add `/api/emails/{email_id}/structure` for Mail detail and attachment analysis.
   - Add `/api/data/content-graph-surface` or extend quality surface with parser and graph quality metrics.
   - Keep external execution actions opt-in and source-backed.

## Proposed Data Model

Names follow the repo rule against new single-token columns.

`content_parse_runs`

- `parse_run_uid` primary key
- `user_scope_id`
- `organization_scope_id`
- `workspace_scope_id`
- `source_kind`
- `source_record_uid`
- `parser_version`
- `status_code`
- `failure_reason_code`
- `input_content_hash`
- `started_at`
- `completed_at`

`content_nodes`

- `content_node_uid` primary key
- `parse_run_uid`
- `parent_node_uid`
- `source_kind`
- `source_record_uid`
- `node_kind`
- `node_path`
- `ordinal_index`
- `display_label`
- `safe_text_content`
- `content_hash`
- `sanitization_status_code`
- `created_at`

`content_segments`

- `content_segment_uid` primary key
- `content_node_uid`
- `parse_run_uid`
- `segment_kind`
- `segment_path`
- `ordinal_index`
- `heading_path`
- `safe_text_content`
- `content_hash`
- `token_count`
- `embedding_status_code`
- `created_at`

`content_segment_embeddings`

- `segment_embedding_uid` primary key
- `content_segment_uid`
- `embedding_model`
- `embedding_dimension_count`
- `embedding_vector`
- `embedding_status_code`
- `failure_reason_code`
- `created_at`

`knowledge_graph_edges`

- `graph_edge_uid` primary key
- `source_node_uid`
- `target_node_uid`
- `source_segment_uid`
- `edge_type_code`
- `confidence_score`
- `evidence_text_hash`
- `extraction_method_code`
- `model_version_label`
- `parse_run_uid`
- `created_at`

The first implementation can collapse `content_segment_embeddings` into `content_segments` if migration size must stay small, but keep the logical separation in service code so later multiple-embedding-model support is possible.

## Product Experience

Use Product Design only as a design and prototype planning aid for now. There is no saved Product Design user context, so the canonical grounding is `docs/ui-ux/naruon-ui-ux-mapping.md` and `docs/ui-ux/mockups/`.

Primary surfaces:

- Mail detail: show `첨부 분석`, `맥락 종합`, and source-bound paragraph citations. Users can expand a citation to see email body path or attachment path.
- Context Search: result list becomes segment-aware. A result can say "Attachment: roadmap.pdf > Section 2 > paragraph 4" instead of only showing an email-level snippet.
- Relation Context: graph nodes include email, attachment, DOM section, paragraph, person, project, task, date, and decision nodes.
- Data workspace: add parser coverage, paragraph coverage, graph edge count, failed parser type, and embedding model coverage to the existing ingestion and quality cards.
- AI Hub: expose the content graph as a prompt context source. Prompts must cite segment UIDs and source paths.

Figma scope:

- FigJam architecture diagram created for the pipeline.
- No Figma Code Connect.
- Future design work should create three screen concepts only after this spec is approved: Data ingestion coverage, Mail attachment analysis, and Context Search segment detail.

## KPI Framework

Primary business KPI:

- `evidence_backed_decision_rate`: share of user-visible AI decisions, action items, or search answers that cite at least one valid content segment and source path.

Technical driver KPIs:

- `parser_success_rate`: successfully parsed messages and attachments divided by attempted parse items.
- `paragraph_coverage_rate`: content bytes represented by paragraph segments divided by safe extracted text bytes.
- `segment_embedding_coverage_rate`: segments with valid embeddings divided by eligible segments.
- `graph_edge_precision_sample`: manually reviewed correct graph edges divided by sampled graph edges.
- `citation_click_success_rate`: citation opens the exact Mail/Data/Search source context without 404 or scope error.
- `ingestion_p95_latency_seconds`: source upload to searchable segment availability.
- `cost_per_thousand_segments`: embedding and extraction cost per 1,000 segments.

Guardrails:

- `raw_markup_exposure_count` must be zero.
- `cross_workspace_leak_count` must be zero.
- `real_mail_public_ci_count` must be zero.
- `parser_false_success_count` must be zero for unsupported binary formats.
- `warning_class_test_output_count` must be zero for merge evidence.

Commercial readiness targets for a pilot:

- 95 percent parser success on supported text, HTML, Markdown, mbox, zip, and `.eml` paths.
- 90 percent paragraph coverage for supported text-like content.
- Segment-level search result available within 120 seconds for a 1,000-message private corpus on local or private runner infrastructure.
- 100 percent of AI-visible answers cite segment UIDs and source paths.
- At least 30 gold corpus scenarios covering Korean/English body, multipart HTML, nested MIME, inline attachments, text attachments, Markdown, malicious HTML, malformed dates, duplicate emails, and large import quotas.

## Implementation Plan

Phase 0: design and evidence

- Keep this spec as the design gate.
- Create FigJam architecture diagram.
- Wait for user approval before code implementation, unless the user explicitly authorizes implementation without a review gate.
- If approved, run `codegraph init -i` and use CodeGraph for structural exploration.

Phase 1: internal parser package

- Add `backend/services/content_graph/` with pure Python dataclasses for source envelopes, content nodes, content segments, parser results, and parser failure reasons.
- Add deterministic parsers for email MIME, text/plain, text/html, text/markdown, and simple XML/CSV/ICS text-like attachments.
- Add unit tests with malicious HTML and malformed MIME.

Phase 2: persistence and search

- Add Alembic migration for parse runs, nodes, segments, embeddings, and graph edges.
- Integrate segment creation into `email_import_service` after existing email/attachment persistence.
- Generate embeddings for paragraph segments through the existing provider-selection path.
- Extend search to return segment-level provenance while preserving current email-level API compatibility.

Phase 3: UX and quality surfaces

- Extend Data quality surface with parser and graph metrics.
- Add Mail structure endpoint and UI panel.
- Update Context Search UI to show source path, segment citation, related graph neighborhood, and timeline anchor.
- Add browser-visible private smoke coverage for real mail paths.

Phase 4: graph intelligence

- Add deterministic edge extraction first.
- Add optional LLM graph extraction only after provenance and prompt audit fields exist.
- Add evaluation harness for graph edge precision and citation faithfulness.

Phase 5: commercial hardening

- Add tenant-level parser policy toggles and allowed attachment type policy.
- Add per-customer corpus benchmark report.
- Add exportable due-diligence bundle: architecture, security posture, quality metrics, golden corpus results, private runner proof, and browser screenshots.
- Package parser as a private internal library only after the second consumer exists.

## Library And Dependency Policy

Ponytail recommendation:

- Do not start by adding a broad parsing framework.
- Use Python stdlib email parsing, existing `defusedxml`, existing `langchain-text-splitters`, and narrow custom normalization first.
- Add new dependencies only for proven unsupported formats with tests and sandboxing:
  - PDF: add only when pilot corpus includes PDFs that matter.
  - DOCX: add only when Microsoft Office attachments become a signed pilot criterion.
  - HWP/HWPX: use an adapter and fail closed until a safe converter path is approved.
  - HTML: add BeautifulSoup or lxml only when stdlib `HTMLParser` cannot preserve enough structure on golden corpus cases.

## PR And Verification Strategy

Use small PRs rather than one broad commercial PR:

1. `content_graph` pure parser and golden tests.
2. DB migration and persistence integration.
3. Search/API provenance extension.
4. Data quality surface metrics.
5. Mail/Search/Data UI.
6. Private smoke and commercial evidence report.

Minimum verification before merge:

- `cd backend && PYTHONWARNINGS=error python3 -m pytest -q tests/test_email_parser.py tests/test_email_import_service.py tests/test_search.py tests/test_data_api.py`
- Add new `backend/tests/test_content_graph_parser.py`.
- Add migration smoke against PostgreSQL because this is DB-affecting.
- `cd frontend && npm test -- src/app/search/page.test.tsx src/components/EmailDetail.test.tsx src/app/data/page.test.tsx`
- Browser-visible private smoke through `backend/scripts/private_mail_http_smoke.py` for real mail only on local/private runner.
- Strix/OpenCode evidence must be current-head and warning-free.

## External Reference Snapshot

- Microsoft 365 Copilot connectors show the enterprise pattern Naruon should match: secure indexed or federated connection to data beyond the office suite while preserving search and Copilot experiences.
  - https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/overview
- Microsoft Graph positions connectors and Data Connect as the way to derive insights and extend Microsoft 365 experiences from Microsoft and external datasets.
  - https://learn.microsoft.com/en-us/graph/overview
- Gmail attachment retrieval is message/attachment scoped, reinforcing the need to persist provider source IDs and attachment provenance separately from display text.
  - https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments/get
- Gartner's 2026 GraphRAG trend framing supports the architectural choice to combine RAG with contextual knowledge graphs for high-accuracy complex use cases.
  - https://www.gartner.com/en/documents/7444326
- Enterprise knowledge graph market estimates indicate this is a commercial infrastructure category, not only an internal parser feature.
  - https://www.grandviewresearch.com/industry-analysis/enterprise-knowledge-graph-market-report

## Open Decisions

- CodeGraph initialization is pending explicit user confirmation because the fresh clone has no `.codegraph/` directory and AGENTS.md requires asking first.
- PDF/DOCX/HWP parser dependencies should wait for a pilot corpus requirement and security review.
- The exact UI mockup generation step should wait until the user approves this design brief; Figma Code Connect remains excluded.

## Approval Gate

This document is ready for user review. After approval, the next step is to convert this design into an implementation plan and begin Phase 1 on a focused branch.
