# Attachment Parser Registry Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make attachment parser coverage inspectable by format and status before adding heavyweight document parser dependencies.

**Architecture:** Keep the parser boundary inside `backend/services/attachment_parser.py`. Add a small stdlib-only registry manifest, deterministic parser status guardrails, and a scoped quality-surface breakdown that the Data UI can show without raw attachment bytes, message IDs, attachment IDs, or provider secrets.

**Tech Stack:** Python 3.14, stdlib MIME/path handling, FastAPI/Pydantic, SQLAlchemy async ORM, React/TypeScript, pytest, Vitest, ruff. No new parser dependency in this phase.

## Global Constraints

- Figma Code Connect is not used.
- Review process is not a blocker; continue on PR #895 and keep pushing.
- Do not add PDF/DOCX/PPTX/XLSX parser dependencies until registry coverage shows the format gap and a sandbox/dependency gate is justified.
- Do not expose raw HTML, unsupported binary bytes, message IDs, attachment IDs, provider credentials, or full bodies through user-facing APIs.
- Preserve unrelated `.Jules/*` worktree changes by working in a clean sibling worktree.

---

### Task 1: Parser Registry And Guardrails

**Files:**
- Modify: `backend/services/attachment_parser.py`
- Test: `backend/tests/test_attachment_parser.py`

**Interfaces:**
- Produces: `AttachmentParserDescriptor`
- Produces: `get_attachment_parser_manifest() -> list[AttachmentParserDescriptor]`
- Produces: `MAX_ATTACHMENT_PARSE_TEXT_CHARS`
- Preserves: `parse_email_attachment(filename, content_type, raw_content) -> AttachmentParseResult`

- [x] **Step 1: Write failing parser registry tests**

Add tests asserting:
- the registry lists `plain_text`, `html`, `markdown`, and `unsupported_binary`
- extension fallback maps `application/octet-stream` + `.md` to `text/markdown`
- a raw text attachment larger than `MAX_ATTACHMENT_PARSE_TEXT_CHARS` returns `parse_status == "parse_size_limit_exceeded"` and no raw content

- [x] **Step 2: Run parser tests to verify failure**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py`

Expected: FAIL because the registry and size guardrail do not exist yet.

- [x] **Step 3: Implement registry and guardrail**

Use frozen dataclasses and module constants only. Keep supported parser keys explicit and return unsupported/oversized content as metadata-only parse results.

- [x] **Step 4: Verify parser tests pass**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py`

Expected: PASS.

### Task 2: Backend Parse Breakdown API

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `Attachment.content_type`, `Attachment.parse_status`, scoped `Email` join
- Produces: `DataAttachmentParseBreakdown`
- Produces: `DataQualitySurfaceResponse.attachment_parse_breakdown`

- [x] **Step 1: Write failing API test**

Update the mocked data-quality surface test to include grouped attachment parse rows:
- `("text/markdown", "parsed", 2)`
- `("application/pdf", "unsupported_content_type", 1)`

Assert response includes:
- `content_type`
- `parse_status`
- `object_count`
- `parser_key`
- `display_name`
- `evidence_source == "email_attachments.content_type, email_attachments.parse_status"`

- [x] **Step 2: Run API test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets`

Expected: FAIL because the response model and query do not exist.

- [x] **Step 3: Implement scoped breakdown query**

Add `_get_attachment_parse_breakdown()` using grouped SQL over `Attachment.content_type` and `Attachment.parse_status`. Map known supported content types to `plain_text`, `html`, or `markdown`; map all unsupported statuses to `unsupported_binary`. Limit output to the top 12 groups by count.

- [x] **Step 4: Verify data API tests pass**

Run: `cd backend && python -m pytest -q tests/test_data_api.py`

Expected: PASS.

### Task 3: Frontend Quality Drilldown

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`
- Modify: `frontend/tests/e2e/helpers.ts`

**Interfaces:**
- Consumes: `DataQualitySurfaceResponse.attachment_parse_breakdown`
- Produces: visible Korean section title `첨부 parser 형식별 현황`

- [x] **Step 1: Write failing frontend test**

Update `dataQualitySurface` fixture with `attachment_parse_breakdown` and assert the quality tab renders:
- `첨부 parser 형식별 현황`
- `text/markdown`
- `application/pdf`
- `unsupported_content_type`

- [x] **Step 2: Run frontend test to verify failure**

Run: `cd frontend && pnpm test src/app/data/page.test.tsx`

Expected: FAIL because the UI does not render the breakdown.

- [x] **Step 3: Implement type and UI rendering**

Add an optional `attachment_parse_breakdown` array to the response type. Render a compact table/list in `QualityCheckTab` below the quality checks. Use existing card styling, `toSafeReactText`, and count formatting.

- [x] **Step 4: Verify frontend data page test passes**

Run: `cd frontend && pnpm test src/app/data/page.test.tsx`

Expected: PASS.

### Task 4: Verification, Push, And PR Update

**Files:**
- All files above
- Modify: `work/pr-895-body.md` outside repo for PR body update if needed

**Interfaces:**
- Produces: pushed PR #895 update

- [x] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest -q tests/test_attachment_parser.py tests/test_data_api.py
```

- [x] **Step 2: Run focused frontend test**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
```

- [x] **Step 3: Run full backend verification**

Run:

```bash
cd backend
python -m pytest -q
ruff check .
```

- [x] **Step 4: Run repository whitespace check**

Run: `git diff --check`

- [x] **Step 5: Commit, push, and update PR**

Run:

```bash
git add backend/services/attachment_parser.py backend/tests/test_attachment_parser.py backend/api/data.py backend/tests/test_data_api.py frontend/src/components/data-layout/types.ts frontend/src/components/data-layout/QualityCheckTab.tsx frontend/src/app/data/page.test.tsx frontend/tests/e2e/helpers.ts docs/superpowers/plans/2026-07-02-attachment-parser-registry-drilldown.md
git commit -m "feat: add attachment parser coverage drilldown"
git push origin HEAD:plan/email-dom-paragraph-kg-2026-07-02
gh pr edit 895 --body-file /Users/seonghobae/Documents/Codex/2026-07-02/https-github-com-contextualwisdomlab-noema-figma-2/work/pr-895-body.md
```
