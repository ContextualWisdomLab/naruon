# Attachment Parse Source Audit Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist attachment parser audit metadata so fallback decisions such as `application/octet-stream` plus `.md` becoming `text/markdown` are visible in storage, API aggregates, and the Data Quality UI.

**Architecture:** Keep the parser boundary in `backend/services/attachment_parser.py` and persist the already-produced `parse_content_type` plus a deterministic `parser_key` on `email_attachments`. Extend the scoped Data Quality Surface breakdown to group by raw MIME, parse source MIME, status, and parser key without exposing raw attachment content or identifiers. No separate package, submodule, or new parser dependency is needed.

**Tech Stack:** Python 3.14, FastAPI/Pydantic, SQLAlchemy async ORM, Alembic, React/TypeScript, pytest, Vitest, ruff. No Figma Code Connect.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 6 files.
- Do not add PDF/DOCX/PPTX/XLSX parser dependencies in this phase.
- Do not expose raw HTML, unsupported binary bytes, message IDs, attachment IDs, provider credentials, or full bodies through user-facing APIs.
- Review process and pending CI are not blockers; failed CI is actionable.
- Figma board updates are documentation/design artifacts only, not Code Connect metadata.

---

### Task 1: Parser Key Contract

**Files:**
- Modify: `backend/services/attachment_parser.py`
- Test: `backend/tests/test_attachment_parser.py`

**Interfaces:**
- Produces: `AttachmentParseResult.parser_key: str`
- Preserves: `parse_email_attachment(filename, content_type, raw_content) -> AttachmentParseResult`

- [x] **Step 1: Write failing parser-key tests**

Add assertions:

```python
def test_generic_binary_content_type_can_fall_back_to_markdown_extension():
    result = parse_email_attachment(
        filename="plan.md",
        content_type="application/octet-stream",
        raw_content="# Plan\n\nShip graph",
    )

    assert result.content_type == "application/octet-stream"
    assert result.parse_content_type == "text/markdown"
    assert result.parser_key == "markdown"
    assert result.parse_status == "parsed"
    assert result.content == "# Plan Ship graph"
```

Also assert unsupported binary returns `parser_key == "unsupported_binary"` and oversized text keeps the source parser key, e.g. `plain_text`.

- [x] **Step 2: Run parser test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py`

Expected: FAIL because `AttachmentParseResult` has no `parser_key`.

- [x] **Step 3: Implement parser key lookup**

Add a private lookup from `parse_content_type` and `parse_status` to manifest descriptor. Return `parser_key` in every `AttachmentParseResult`.

- [x] **Step 4: Verify parser tests pass**

Run: `cd backend && python -m pytest -q tests/test_attachment_parser.py`

Expected: PASS.

### Task 2: Attachment Persistence Columns

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/0008_attachment_parser_audit_metadata.py`
- Modify: `backend/services/email_parser.py`
- Modify: `backend/services/email_import_service.py`
- Test: `backend/tests/test_email_parser.py`
- Test: `backend/tests/test_email_import_service.py`

**Interfaces:**
- Produces: `Attachment.parse_content_type: str`
- Produces: `Attachment.parser_key: str`
- Consumes: attachment payload keys `parse_content_type`, `parser_key`

- [x] **Step 1: Write failing parser/import tests**

Assert parsed email attachments include `parser_key`, and imported `Attachment` objects persist `parse_content_type` and `parser_key`.

- [x] **Step 2: Run targeted tests to verify failure**

Run:

```bash
cd backend
python -m pytest -q tests/test_email_parser.py tests/test_email_import_service.py
```

Expected: FAIL because the model/import path lacks persisted fields.

- [x] **Step 3: Add ORM fields and Alembic migration**

Add non-null string columns:

```python
parse_content_type: Mapped[str] = mapped_column(
    String(120), default="text/plain", nullable=False
)
parser_key: Mapped[str] = mapped_column(
    String(64), default="plain_text", nullable=False
)
```

Migration defaults:

```python
op.add_column(
    "email_attachments",
    sa.Column("parse_content_type", sa.String(length=120), nullable=False, server_default="text/plain"),
)
op.add_column(
    "email_attachments",
    sa.Column("parser_key", sa.String(length=64), nullable=False, server_default="plain_text"),
)
```

- [x] **Step 4: Persist parser audit fields**

In `email_parser.py`, add `"parser_key": parsed_attachment.parser_key`. In `email_import_service.py`, pass `parse_content_type` and `parser_key` into the `Attachment` constructor.

- [x] **Step 5: Verify parser/import tests pass**

Run:

```bash
cd backend
python -m pytest -q tests/test_email_parser.py tests/test_email_import_service.py
```

Expected: PASS.

### Task 3: Data Quality Breakdown Uses Persisted Audit Fields

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `Attachment.content_type`, `Attachment.parse_content_type`, `Attachment.parse_status`, `Attachment.parser_key`
- Produces: `DataAttachmentParseBreakdown.parse_content_type`

- [x] **Step 1: Write failing API test**

Update the mocked breakdown rows to include parse source and parser key:

```python
[
    ("application/octet-stream", "text/markdown", "parsed", "markdown", 2),
    ("application/pdf", "application/pdf", "unsupported_content_type", "unsupported_binary", 1),
]
```

Assert each response row includes `parse_content_type` and the stored `parser_key`.

- [x] **Step 2: Run API test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets`

Expected: FAIL because the API does not select or serialize `parse_content_type`.

- [x] **Step 3: Update response model and grouped query**

Group by `Attachment.content_type`, `Attachment.parse_content_type`, `Attachment.parse_status`, and `Attachment.parser_key`. Keep the top-12 limit and evidence source string.

- [x] **Step 4: Verify data API tests pass**

Run: `cd backend && python -m pytest -q tests/test_data_api.py`

Expected: PASS.

### Task 4: Frontend Audit Fields

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`
- Modify: `frontend/tests/e2e/helpers.ts`

**Interfaces:**
- Consumes: `attachment_parse_breakdown[].parse_content_type`
- Produces: visible parse source MIME without raw evidence-source column names

- [x] **Step 1: Write failing frontend test**

Add fixture data with `content_type: "application/octet-stream"` and `parse_content_type: "text/markdown"`. Assert the quality tab renders both values and still hides `email_attachments.content_type`.

- [x] **Step 2: Run frontend test to verify failure**

Run: `cd frontend && pnpm test src/app/data/page.test.tsx`

Expected: FAIL because the UI does not render parse source MIME yet.

- [x] **Step 3: Render raw MIME and parse source MIME**

In each drilldown card, show the raw `content_type` and a separate `parse_content_type` line. Keep parser key and write boundary as existing compact fields.

- [x] **Step 4: Verify frontend test passes**

Run: `cd frontend && pnpm test src/app/data/page.test.tsx`

Expected: PASS.

### Task 5: Verification, Push, And PR Update

**Files:**
- All files above
- Modify: `/Users/seonghobae/Documents/Codex/2026-07-02/https-github-com-contextualwisdomlab-noema-figma-2/work/pr-895-body.md`

**Interfaces:**
- Produces: pushed PR #895 update

- [x] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest -q tests/test_attachment_parser.py tests/test_email_parser.py tests/test_email_import_service.py tests/test_data_api.py
```

- [x] **Step 2: Run frontend focused test**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
```

- [x] **Step 3: Run full verification**

Run:

```bash
cd backend
python -m pytest -q
ruff check .
cd ../frontend
pnpm test
pnpm typecheck
cd ..
git diff --check
```

- [ ] **Step 4: Commit and push**

Stage only Phase 6 files. Do not stage `.Jules/*`.

```bash
git commit -m "feat: persist attachment parser audit metadata"
git push origin HEAD:plan/email-dom-paragraph-kg-2026-07-02
```

- [ ] **Step 5: Update PR body and check live PR status**

Run:

```bash
gh pr edit 895 --repo ContextualWisdomLab/naruon --body-file /Users/seonghobae/Documents/Codex/2026-07-02/https-github-com-contextualwisdomlab-noema-figma-2/work/pr-895-body.md
gh pr view 895 --repo ContextualWisdomLab/naruon --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup,url
```
