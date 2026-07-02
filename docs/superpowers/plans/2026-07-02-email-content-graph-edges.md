# Email Content Graph Edge Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist deterministic knowledge graph edges from parsed email body and text attachment content graphs, then expose graph-edge readiness in the data quality surface.

**Architecture:** Keep `backend/services/content_graph/` as the internal library boundary. Do not split into a submodule or external package yet: the current blast radius is backend-only, the parser and import aggregate already share ORM transactions, and a package split would add release/versioning overhead before reuse is proven. The new `knowledge_graph_edges` table links existing `content_nodes` and `content_segments` with stable edge UIDs, safe non-secret labels, and scoped `email_id`/optional `attachment_id`.

**Tech Stack:** Python 3.14, SQLAlchemy async ORM, Alembic, PostgreSQL pgvector already present, FastAPI, pytest, ruff, stdlib hashing.

## Global Constraints

- Figma Code Connect is not used.
- Review process is not a blocker; keep implementing and pushing PR #895.
- Do not expose raw email HTML, message IDs, attachment IDs, provider credentials, or full bodies through data quality responses.
- Preserve the existing internal package boundary; no submodule or separate distribution until edge extraction is reused outside this backend.
- Leave unrelated `.Jules/*` worktree changes untouched.

---

### Task 1: Edge ORM And Migration

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/0006_knowledge_graph_edges.py`
- Test: `backend/tests/test_alembic_migrations.py`

**Interfaces:**
- Produces: `KnowledgeGraphEdgeRecord`.
- Consumes: `Email`, `Attachment`, `ContentNodeRecord`, `ContentSegmentRecord`.

- [x] **Step 1: Write failing migration test**

Add `test_knowledge_graph_edges_have_incremental_revision` asserting revision `0006_knowledge_graph_edges`, down revision `0005_content_graph_records`, table `knowledge_graph_edges`, stable `edge_uid`, scoped `email_id`, optional `attachment_id`, node/segment source and target FKs, edge kind/path fields, and idempotent index create/drop calls.

- [x] **Step 2: Run migration test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_alembic_migrations.py::test_knowledge_graph_edges_have_incremental_revision`

Expected: FAIL because the revision file and ORM model do not exist yet.

- [x] **Step 3: Implement model and migration**

Add `KnowledgeGraphEdgeRecord` with deterministic uniqueness on `edge_uid`, owner scoping through `email_id`, optional attachment scope, source/target node and segment references, `edge_kind`, `edge_path`, `ordinal_index`, and `created_at`.

- [x] **Step 4: Verify migration test passes**

Run: `cd backend && python -m pytest -q tests/test_alembic_migrations.py`

Expected: PASS.

### Task 2: Deterministic Edge Generation

**Files:**
- Modify: `backend/services/email_import_service.py`
- Test: `backend/tests/test_email_import_service.py`

**Interfaces:**
- Consumes: populated `Email.content_nodes` and `Email.content_segments`.
- Produces: `Email.knowledge_graph_edges`.

- [x] **Step 1: Write failing import aggregate test**

Assert that `_build_email_object(...)` creates:

```python
{"node_contains_node", "node_has_segment", "segment_next", "heading_contains_segment"}
```

Also assert deterministic edge UID uniqueness and heading containment from `Launch -> Hello team` and `Plan -> Ship graph`.

- [x] **Step 2: Run import edge test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_email_import_service.py::test_build_email_object_attaches_knowledge_graph_edges`

Expected: FAIL because knowledge graph edges are not populated yet.

- [x] **Step 3: Implement edge builder**

Create deterministic edges after content graph records are appended:
- `node_contains_node`: parent content node to child content node.
- `node_has_segment`: content node to paragraph/heading segment.
- `segment_next`: adjacent segments inside the same source record.
- `heading_contains_segment`: nearest heading segment to following paragraph segments under that heading path.

- [x] **Step 4: Verify import tests pass**

Run: `cd backend && python -m pytest -q tests/test_email_import_service.py tests/test_content_graph_parser.py tests/test_email_parser.py`

Expected: PASS.

### Task 3: Data Quality KG KPI

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `knowledge_graph_inventory` pipeline stage and `knowledge_graph_coverage` quality check.
- Consumes: `KnowledgeGraphEdgeRecord` counts joined to scoped `Email`.

- [x] **Step 1: Write failing data quality test**

Add mocked KG stats `(2, 10)` for 4 scoped emails. Assert:
- `knowledge_graph_inventory` shows 2 of 4 emails with 10 graph edges.
- `knowledge_graph_coverage` reports 2 uncovered scoped emails.
- Evidence source is only `knowledge_graph_edges`.

- [x] **Step 2: Run data API test to verify failure**

Run: `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets`

Expected: FAIL because the API does not query graph-edge coverage yet.

- [x] **Step 3: Implement KPI query and response wiring**

Add `KnowledgeGraphQualityStats`, `_get_knowledge_graph_stats`, pipeline stage wiring, and quality check wiring. Do not return edge payload contents.

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
  tests/test_content_graph_parser.py \
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
git commit -m "feat: add content graph knowledge edges"
git push
gh pr edit 895 --body-file ...
gh pr view 895 --json ...
```

Expected: PR #895 contains Phase 3 scope, tests, and FigJam Phase 3 section evidence.
