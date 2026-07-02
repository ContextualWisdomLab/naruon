# Email Content Graph Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist email body and text attachment content graph nodes and paragraph segments during import, then expose content graph coverage in the data quality surface.

**Architecture:** Keep `backend/services/content_graph/` as an internal library, not a submodule or external package. The email parser exposes safe display text plus internal parse-only source content; the import aggregate builds `Email`, `Attachment`, `ContentNodeRecord`, and `ContentSegmentRecord` in one transaction. The data quality API reports segment coverage without returning raw email bodies, message IDs, attachment IDs, or active HTML.

**Tech Stack:** Python 3.14, SQLAlchemy async ORM, Alembic, PostgreSQL pgvector already present, FastAPI, pytest, ruff, stdlib email/html parsing.

## Global Constraints

- Figma Code Connect is not used.
- Do not add a parser dependency for Phase 2; reuse stdlib and existing `strip_html_markup`.
- Do not persist raw HTML or active markup to user-facing fields.
- Do not touch existing `.Jules/*` case-collision changes.
- Review process is not a blocker; implement on PR #895 branch and keep pushing.

---

### Task 1: Parser Metadata Contract

**Files:**
- Modify: `backend/services/email_parser.py`
- Test: `backend/tests/test_email_parser.py`

**Interfaces:**
- Produces: `EmailData["body_content_type"] -> str`, `EmailData["body_parse_content"] -> str`, attachment `content_type`.
- Consumes: existing parser functions and `strip_html_markup`.

- [x] **Step 1: Write failing parser tests**

Add assertions to `test_parse_eml_multipart_html_fallback`:

```python
assert parsed["body_content_type"] == "text/html"
assert parsed["body_parse_content"] == "<p>This is HTML content</p>"
```

Add assertion to `test_parse_eml_strips_active_html_from_attachment_display_fields`:

```python
assert parsed["attachments"] == [
    {"filename": ".txt", "content": "report", "content_type": "text/plain"}
]
```

- [x] **Step 2: Run parser tests to verify failure**

Run: `cd backend && python -m pytest -q tests/test_email_parser.py`

Expected: FAIL because `body_content_type`, `body_parse_content`, and attachment `content_type` do not exist yet.

- [x] **Step 3: Implement metadata**

Update `EmailData` with `NotRequired[str]` keys for `body_content_type` and `body_parse_content`. Return selected body MIME type and NUL-sanitized parse content while keeping `body` display-safe.

- [x] **Step 4: Verify parser tests pass**

Run: `cd backend && python -m pytest -q tests/test_email_parser.py`

Expected: PASS.

### Task 2: ORM And Migration

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/0005_content_graph_records.py`
- Test: `backend/tests/test_alembic_migrations.py`

**Interfaces:**
- Produces: `ContentNodeRecord`, `ContentSegmentRecord`.
- Consumes: `Email`, `Attachment`, SQLAlchemy `Base`.

- [x] **Step 1: Write migration scaffold test**

Add `test_content_graph_records_have_incremental_revision` asserting:

```python
assert 'revision = "0005_content_graph_records"' in revision_text
assert 'down_revision = "0004_ai_hub_workflow_runs"' in revision_text
assert '"content_nodes"' in revision_text
assert '"content_segments"' in revision_text
assert '"content_node_uid"' in revision_text
assert '"content_segment_uid"' in revision_text
assert '"email_id"' in revision_text
assert '"attachment_id"' in revision_text
assert "ix_content_nodes_email_source" in revision_text
assert "ix_content_segments_email_source" in revision_text
assert "has_table" in revision_text
assert "op.create_table(" in revision_text
assert "op.create_index(" in revision_text
assert "if_not_exists=True" in revision_text
assert "op.drop_index(" in revision_text
assert "if_exists=True" in revision_text
```

- [x] **Step 2: Run migration test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_alembic_migrations.py::test_content_graph_records_have_incremental_revision`

Expected: FAIL because the revision file does not exist.

- [x] **Step 3: Implement models and migration**

Add `ContentNodeRecord` and `ContentSegmentRecord` SQLAlchemy models with owner scope via `email_id`, optional `attachment_id`, deterministic UID uniqueness, and cascade relationships from `Email` and `Attachment`.

- [x] **Step 4: Verify migration test passes**

Run: `cd backend && python -m pytest -q tests/test_alembic_migrations.py`

Expected: PASS.

### Task 3: Import Persistence

**Files:**
- Modify: `backend/services/email_import_service.py`
- Test: `backend/tests/test_email_import_service.py`

**Interfaces:**
- Consumes: `parse_content(...) -> ParseResult`, `EmailData.body_parse_content`, attachment `content_type`.
- Produces: `_append_content_graph(email_obj, parsed, message_id)`.

- [x] **Step 1: Write failing import aggregate test**

Add a unit test that calls `_build_email_object(...)` with an HTML body parse source and one Markdown attachment. Assert that:

```python
assert [segment.safe_text_content for segment in email_obj.content_segments] == [
    "Launch",
    "Hello team",
    "Plan",
    "Ship graph",
]
assert email_obj.content_segments[0].segment_kind == "heading"
assert email_obj.content_segments[1].heading_path == "Launch"
assert email_obj.attachments[0].content_segments[0].safe_text_content == "Plan"
```

- [x] **Step 2: Run test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_email_import_service.py::test_build_email_object_attaches_content_graph_records`

Expected: FAIL because content graph ORM relationships are not populated.

- [x] **Step 3: Implement aggregate appending**

Call `parse_content` for the email body and each text attachment. Create `ContentNodeRecord` and `ContentSegmentRecord` objects from parse results, attach body records to `Email`, and attach attachment records through both `Email` and `Attachment` relationships.

- [x] **Step 4: Verify import tests pass**

Run: `cd backend && python -m pytest -q tests/test_email_import_service.py tests/test_content_graph_parser.py tests/test_email_parser.py`

Expected: PASS.

### Task 4: Data Quality KPI

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: quality check `content_graph_coverage` and pipeline stage `content_graph_inventory`.
- Consumes: `ContentSegmentRecord` counts joined to scoped `Email`.

- [x] **Step 1: Write failing quality surface test**

Update `mock_db` result sequence to include content graph stats `(4, 6)`, where 4 emails and 6 segments are covered. Assert:

```python
assert any(stage["stage_key"] == "content_graph_inventory" for stage in data["pipeline_stages"])
assert quality_by_key["content_graph_coverage"]["issue_count"] == 0
assert quality_by_key["content_graph_coverage"]["evidence_source"] == "content_segments"
```

- [x] **Step 2: Run test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets`

Expected: FAIL because the API does not query content segment coverage yet.

- [x] **Step 3: Implement KPI query and response wiring**

Add `ContentGraphQualityStats`, `_get_content_graph_stats`, `_check_content_graph_coverage`, and a `content_graph_inventory` pipeline stage. Do not expose raw content.

- [x] **Step 4: Verify data API tests pass**

Run: `cd backend && python -m pytest -q tests/test_data_api.py`

Expected: PASS.

### Task 5: Final Verification And PR Update

**Files:**
- All changed files above.

**Interfaces:**
- Produces: pushed PR #895 update.

- [x] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest -q \
  tests/test_content_graph_parser.py \
  tests/test_email_parser.py \
  tests/test_email_import_service.py \
  tests/test_data_api.py \
  tests/test_alembic_migrations.py
```

Expected: PASS.

- [x] **Step 2: Run lint and formatting checks**

Run:

```bash
cd backend
python -m ruff check services/content_graph services/email_parser.py services/email_import_service.py api/data.py db/models.py tests/test_content_graph_parser.py tests/test_email_parser.py tests/test_email_import_service.py tests/test_data_api.py tests/test_alembic_migrations.py
python -m ruff format --check services/content_graph services/email_parser.py services/email_import_service.py api/data.py db/models.py tests/test_content_graph_parser.py tests/test_email_parser.py tests/test_email_import_service.py tests/test_data_api.py tests/test_alembic_migrations.py
```

Expected: PASS.

- [x] **Step 3: Sync CodeGraph and check git diff**

Run:

```bash
codegraph sync
codegraph status
git diff --check
git status --short
```

Expected: CodeGraph index up to date; only intended files plus pre-existing `.Jules/*` changes.

- [x] **Step 4: Commit and push**

Run:

```bash
git add backend/services/email_parser.py backend/db/models.py backend/alembic/versions/0005_content_graph_records.py backend/services/email_import_service.py backend/api/data.py backend/tests/test_email_parser.py backend/tests/test_email_import_service.py backend/tests/test_data_api.py backend/tests/test_alembic_migrations.py docs/superpowers/plans/2026-07-02-email-content-graph-persistence.md
git commit -m "feat: persist email content graph segments"
git push origin plan/email-dom-paragraph-kg-2026-07-02
```

Expected: PR #895 updates to the new head.
