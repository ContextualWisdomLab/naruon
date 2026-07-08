# Email Attachment Parser Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make email attachment parsing auditable by preserving supported text/HTML/Markdown attachments as parseable content graph inputs and preserving unsupported binary attachments as visible metadata rows with quality-surface coverage gaps.

**Architecture:** Keep the parser boundary inside the backend. Add a small stdlib-first attachment parsing adapter module that normalizes MIME content into safe display text, internal parse source, parse status, and error code. Persist attachment parse metadata on `email_attachments`, and expose attachment parse coverage through the existing data quality surface.

**Tech Stack:** Python 3.14, stdlib `email`, SQLAlchemy async ORM, Alembic, FastAPI, pytest, ruff. No new parser dependency in this phase.

## Global Constraints

- Figma Code Connect is not used.
- Review process is not a blocker; continue on PR #895 and keep pushing.
- Do not add PDF/DOCX/PPTX/XLSX parser dependencies until the adapter boundary and unsupported-format observability are proven.
- Do not expose raw HTML, unsupported binary bytes, message IDs, attachment IDs, provider credentials, or full bodies through user-facing APIs.
- Preserve unrelated `.Jules/*` worktree changes.

---

### Task 1: Attachment Parser Adapter

**Files:**
- Create: `backend/services/attachment_parser.py`
- Modify: `backend/services/email_parser.py`
- Test: `backend/tests/test_attachment_parser.py`
- Test: `backend/tests/test_email_parser.py`

**Interfaces:**
- Produces: `parse_email_attachment(filename: str | None, content_type: str | None, raw_content: object) -> AttachmentParseResult`.
- Produces: attachment payload keys `filename`, `content`, `content_type`, `parse_content`, `parse_content_type`, `parse_status`, `parse_error_code`.
- Consumes: existing `strip_html_markup` and `_sanitize_nul` semantics.

- [x] **Step 1: Write failing adapter tests**

Add tests asserting:
- HTML attachment display text strips active markup but `parse_content` keeps NUL-sanitized HTML for DOM parsing.
- Markdown attachment keeps `parse_content_type == "text/markdown"`.
- Unsupported PDF attachment returns `content == ""`, `parse_content == ""`, `parse_status == "unsupported_content_type"`, and no raw bytes.

- [x] **Step 2: Run adapter tests to verify failure**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py`

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement adapter module and email parser wiring**

Create `AttachmentParseResult` as a frozen dataclass. Support `text/plain`, `text/html`, `text/markdown`, `text/x-markdown`, and `application/markdown`. For unsupported content types, preserve filename/content type/status only.

- [x] **Step 4: Verify parser tests pass**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py tests/test_email_parser.py`

Expected: PASS.

### Task 2: Attachment Metadata Persistence

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/0007_attachment_parse_metadata.py`
- Modify: `backend/services/email_import_service.py`
- Test: `backend/tests/test_alembic_migrations.py`
- Test: `backend/tests/test_email_import_service.py`

**Interfaces:**
- Consumes: attachment payload parse metadata from Task 1.
- Produces: `Attachment.content_type`, `Attachment.parse_status`, `Attachment.parse_error_code`.

- [x] **Step 1: Write failing migration and import tests**

Add migration test for revision `0007_attachment_parse_metadata`, down revision `0006_knowledge_graph_edges`, columns `content_type`, `parse_status`, `parse_error_code`, and idempotent `op.add_column` / `op.drop_column` guards.

Add import test asserting one HTML attachment is persisted with `content_type == "text/html"` and `parse_status == "parsed"`, and one PDF attachment is persisted with `parse_status == "unsupported_content_type"` without content graph segments.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
python -m pytest -q \
  tests/test_alembic_migrations.py::test_attachment_parse_metadata_has_incremental_revision \
  tests/test_email_import_service.py::test_build_email_object_persists_attachment_parse_metadata
```

Expected: FAIL because the migration/model fields do not exist.

- [x] **Step 3: Implement model, migration, and import mapping**

Add nullable-safe defaults:
- `content_type`: `text/plain`
- `parse_status`: `parsed`
- `parse_error_code`: nullable

Import service should parse content graph records only when `parse_status == "parsed"` and `parse_content` is non-empty.

- [x] **Step 4: Verify migration/import tests pass**

Run: `cd backend && python -m pytest -q tests/test_alembic_migrations.py tests/test_email_import_service.py`

Expected: PASS.

### Task 3: Attachment Parse Coverage KPI

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `Attachment.parse_status` and scoped `Email` join.
- Produces: `attachment_parse_inventory` pipeline stage and `attachment_parse_coverage` quality check.

- [x] **Step 1: Write failing data API test**

Update mocked stats to include parsed attachment count and unsupported count. Assert:
- `attachment_parse_inventory` uses `email_attachments.parse_status`.
- `attachment_parse_coverage` reports unsupported or unparsed scoped attachments.
- Serialized response does not include filenames beyond existing repository asset summaries or raw parse content.

- [x] **Step 2: Run data API test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets`

Expected: FAIL because the API does not query attachment parse metadata yet.

- [x] **Step 3: Implement KPI query and response wiring**

Add `AttachmentParseQualityStats`, `_get_attachment_parse_stats`, `attachment_parse_inventory`, and `attachment_parse_coverage`.

- [x] **Step 4: Verify data API tests pass**

Run: `cd backend && python -m pytest -q tests/test_data_api.py`

Expected: PASS.

### Task 4: Final Verification And PR Update

**Files:**
- All changed files above.

**Interfaces:**
- Produces: pushed PR #895 update and refreshed PR body/check status.

- [x] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest -q \
  tests/test_attachment_parser.py \
  tests/test_email_parser.py \
  tests/test_email_import_service.py \
  tests/test_data_api.py \
  tests/test_alembic_migrations.py
```

- [x] **Step 2: Run full verification**

Run:

```bash
cd backend
python -m pytest -q
ruff check .
git diff --check
```

- [x] **Step 3: Sync CodeGraph and push**

Run:

```bash
codegraph sync
codegraph status
git status --short
git add ...
git commit -m "feat: add attachment parser metadata"
git push
gh pr edit 895 --body-file ...
gh pr view 895 --json ...
```
