# Content Graph Topology Audit Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose stored DOM paragraph and knowledge graph topology in the Data Quality Surface without returning raw email text, raw HTML, attachment bytes, message IDs, or attachment IDs.

**Architecture:** Extend the existing `/api/data/quality-surface` contract with two small aggregate arrays: one for `content_segments` grouped by source and segment kind, and one for `knowledge_graph_edges` grouped by source and edge kind. Keep the implementation inside `backend/api/data.py` and the existing Data Quality tab; no migration, submodule, package split, or new dependency is needed.

**Tech Stack:** Python 3.14, FastAPI/Pydantic, SQLAlchemy async ORM, React/TypeScript, pytest, Vitest, ruff. No Figma Code Connect.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 7 files.
- Do not add entity extraction, PDF/DOCX/PPTX/XLSX parsing, or new parser dependencies in this phase.
- Do not expose raw segment text, raw HTML, unsupported binary bytes, message IDs, attachment IDs, provider credentials, or full bodies through user-facing APIs.
- Review process and pending CI are not blockers; failed CI is actionable.
- Figma board updates are documentation/design artifacts only, not Code Connect metadata.

---

### Task 1: Backend Response Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataContentGraphBreakdown`
- Produces: `DataKnowledgeGraphBreakdown`
- Extends: `DataQualitySurfaceResponse.content_graph_breakdown`
- Extends: `DataQualitySurfaceResponse.knowledge_graph_breakdown`

- [x] **Step 1: Write failing API contract test**

In `test_data_quality_surface_returns_source_backed_counts_without_secrets`, extend the mock DB result queue after knowledge graph stats with:

```python
[
    ("email_body", "paragraph", 6),
    ("attachment", "heading", 2),
],  # content graph breakdown
[
    ("email_body", "node_has_segment", 8),
    ("attachment", "heading_contains_segment", 2),
],  # knowledge graph breakdown
```

Assert the response includes:

```python
assert data["content_graph_breakdown"] == [
    {
        "source_kind": "email_body",
        "segment_kind": "paragraph",
        "object_count": 6,
        "evidence_source": "content_segments.source_kind, content_segments.segment_kind",
        "provider_write_executed": False,
    },
    {
        "source_kind": "attachment",
        "segment_kind": "heading",
        "object_count": 2,
        "evidence_source": "content_segments.source_kind, content_segments.segment_kind",
        "provider_write_executed": False,
    },
]
assert data["knowledge_graph_breakdown"] == [
    {
        "source_kind": "email_body",
        "edge_kind": "node_has_segment",
        "object_count": 8,
        "evidence_source": "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
        "provider_write_executed": False,
    },
    {
        "source_kind": "attachment",
        "edge_kind": "heading_contains_segment",
        "object_count": 2,
        "evidence_source": "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
        "provider_write_executed": False,
    },
]
```

Also extend the forbidden serialized values check to keep `"segmented body text"` and `"<asset-ready@example.com>"` absent.

- [x] **Step 2: Run API test to verify failure**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets
```

Expected: FAIL because the response model has no topology breakdown fields.

- [x] **Step 3: Add Pydantic models and evidence constants**

In `backend/api/data.py`, add:

```python
CONTENT_GRAPH_BREAKDOWN_EVIDENCE_SOURCE = (
    "content_segments.source_kind, content_segments.segment_kind"
)
KNOWLEDGE_GRAPH_BREAKDOWN_EVIDENCE_SOURCE = (
    "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind"
)

class DataContentGraphBreakdown(BaseModel):
    source_kind: str
    segment_kind: str
    object_count: int
    evidence_source: str
    provider_write_executed: bool

class DataKnowledgeGraphBreakdown(BaseModel):
    source_kind: str
    edge_kind: str
    object_count: int
    evidence_source: str
    provider_write_executed: bool
```

Extend `DataQualitySurfaceResponse` with:

```python
content_graph_breakdown: list[DataContentGraphBreakdown]
knowledge_graph_breakdown: list[DataKnowledgeGraphBreakdown]
```

- [x] **Step 4: Add safe row builders**

Add helpers:

```python
def _content_graph_breakdown_row(
    source_kind: str | None,
    segment_kind: str | None,
    object_count: int,
) -> DataContentGraphBreakdown:
    return DataContentGraphBreakdown(
        source_kind=_safe_display_text(source_kind, "unknown")[:64],
        segment_kind=_safe_display_text(segment_kind, "unknown")[:64],
        object_count=int(object_count or 0),
        evidence_source=CONTENT_GRAPH_BREAKDOWN_EVIDENCE_SOURCE,
        provider_write_executed=False,
    )


def _knowledge_graph_breakdown_row(
    source_kind: str | None,
    edge_kind: str | None,
    object_count: int,
) -> DataKnowledgeGraphBreakdown:
    return DataKnowledgeGraphBreakdown(
        source_kind=_safe_display_text(source_kind, "unknown")[:64],
        edge_kind=_safe_display_text(edge_kind, "unknown")[:64],
        object_count=int(object_count or 0),
        evidence_source=KNOWLEDGE_GRAPH_BREAKDOWN_EVIDENCE_SOURCE,
        provider_write_executed=False,
    )
```

- [x] **Step 5: Verify API test passes after Task 2 implementation**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets
```

Expected: PASS after Task 2 wires the query.

### Task 2: Scoped Topology Queries

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `ContentSegmentRecord.source_kind`, `ContentSegmentRecord.segment_kind`
- Consumes: `KnowledgeGraphEdgeRecord.source_kind`, `KnowledgeGraphEdgeRecord.edge_kind`
- Produces: `_get_content_graph_breakdown(...)`
- Produces: `_get_knowledge_graph_breakdown(...)`

- [x] **Step 1: Add content graph aggregate query**

Add:

```python
async def _get_content_graph_breakdown(
    db: AsyncSession,
    email_scope: EmailScopeFilter,
) -> list[DataContentGraphBreakdown]:
    object_count = func.count(ContentSegmentRecord.content_segment_id).label(
        "object_count"
    )
    result = await db.execute(
        select(
            ContentSegmentRecord.source_kind,
            ContentSegmentRecord.segment_kind,
            object_count,
        )
        .join(Email, ContentSegmentRecord.email_id == Email.id)
        .where(*email_scope)
        .group_by(ContentSegmentRecord.source_kind, ContentSegmentRecord.segment_kind)
        .order_by(
            object_count.desc(),
            ContentSegmentRecord.source_kind.asc(),
            ContentSegmentRecord.segment_kind.asc(),
        )
        .limit(12)
    )
    return [
        _content_graph_breakdown_row(
            source_kind=source_kind,
            segment_kind=segment_kind,
            object_count=count,
        )
        for source_kind, segment_kind, count in result.all()
    ]
```

- [x] **Step 2: Add knowledge graph aggregate query**

Add:

```python
async def _get_knowledge_graph_breakdown(
    db: AsyncSession,
    email_scope: EmailScopeFilter,
) -> list[DataKnowledgeGraphBreakdown]:
    object_count = func.count(KnowledgeGraphEdgeRecord.knowledge_graph_edge_id).label(
        "object_count"
    )
    result = await db.execute(
        select(
            KnowledgeGraphEdgeRecord.source_kind,
            KnowledgeGraphEdgeRecord.edge_kind,
            object_count,
        )
        .join(Email, KnowledgeGraphEdgeRecord.email_id == Email.id)
        .where(*email_scope)
        .group_by(KnowledgeGraphEdgeRecord.source_kind, KnowledgeGraphEdgeRecord.edge_kind)
        .order_by(
            object_count.desc(),
            KnowledgeGraphEdgeRecord.source_kind.asc(),
            KnowledgeGraphEdgeRecord.edge_kind.asc(),
        )
        .limit(12)
    )
    return [
        _knowledge_graph_breakdown_row(
            source_kind=source_kind,
            edge_kind=edge_kind,
            object_count=count,
        )
        for source_kind, edge_kind, count in result.all()
    ]
```

- [x] **Step 3: Wire queries into `get_data_quality_surface`**

After reading `knowledge_graph_stats`, call:

```python
content_graph_breakdown = await _get_content_graph_breakdown(db, email_scope)
knowledge_graph_breakdown = await _get_knowledge_graph_breakdown(db, email_scope)
```

Return them through `DataQualitySurfaceResponse`.

- [x] **Step 4: Run focused API tests**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py
```

Expected: PASS.

### Task 3: Frontend Quality Tab Topology Drilldown

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`
- Modify: `frontend/tests/e2e/helpers.ts`

**Interfaces:**
- Consumes: `content_graph_breakdown[]`
- Consumes: `knowledge_graph_breakdown[]`
- Produces: Korean Data Quality UI sections for DOM/paragraph and KG topology

- [x] **Step 1: Write failing frontend fixture/test**

Extend `dataQualitySurface` in `frontend/src/app/data/page.test.tsx`:

```ts
content_graph_breakdown: [
  {
    source_kind: "email_body",
    segment_kind: "paragraph",
    object_count: 6,
    evidence_source: "content_segments.source_kind, content_segments.segment_kind",
    provider_write_executed: false,
  },
  {
    source_kind: "attachment",
    segment_kind: "heading",
    object_count: 2,
    evidence_source: "content_segments.source_kind, content_segments.segment_kind",
    provider_write_executed: false,
  },
],
knowledge_graph_breakdown: [
  {
    source_kind: "email_body",
    edge_kind: "node_has_segment",
    object_count: 8,
    evidence_source: "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
    provider_write_executed: false,
  },
  {
    source_kind: "attachment",
    edge_kind: "heading_contains_segment",
    object_count: 2,
    evidence_source: "knowledge_graph_edges.source_kind, knowledge_graph_edges.edge_kind",
    provider_write_executed: false,
  },
],
```

Assert:

```ts
expect(container.textContent).toContain("DOM/문단 구조별 현황");
expect(container.textContent).toContain("KG edge 형식별 현황");
expect(container.textContent).toContain("email_body");
expect(container.textContent).toContain("paragraph");
expect(container.textContent).toContain("node_has_segment");
expect(container.textContent).not.toContain("content_segments.source_kind");
expect(container.textContent).not.toContain("knowledge_graph_edges.source_kind");
```

- [x] **Step 2: Run frontend test to verify failure**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
```

Expected: FAIL because the sections are not rendered yet.

- [x] **Step 3: Extend TypeScript response type**

Add optional arrays:

```ts
content_graph_breakdown?: Array<{
  source_kind: string;
  segment_kind: string;
  object_count: number;
  evidence_source: string;
  provider_write_executed: boolean;
}>;
knowledge_graph_breakdown?: Array<{
  source_kind: string;
  edge_kind: string;
  object_count: number;
  evidence_source: string;
  provider_write_executed: boolean;
}>;
```

- [x] **Step 4: Render compact topology sections**

In `QualityCheckTab.tsx`, compute:

```ts
const contentGraphBreakdown = dataQualitySurface?.content_graph_breakdown ?? [];
const knowledgeGraphBreakdown = dataQualitySurface?.knowledge_graph_breakdown ?? [];
```

Render two sections only when each array is non-empty. Use cards matching the attachment parser drilldown and show source kind, segment/edge kind, count, and write boundary. Do not render raw `evidence_source` strings.

- [x] **Step 5: Update E2E helper fixture**

Add the same optional arrays to `frontend/tests/e2e/helpers.ts` so browser mocks match the API shape.

- [x] **Step 6: Verify frontend test passes**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
```

Expected: PASS.

### Task 4: Verification, Push, And PR Update

**Files:**
- All files above
- Modify: `docs/superpowers/plans/2026-07-02-content-graph-topology-audit-surface.md`
- Modify: `/Users/seonghobae/Documents/Codex/2026-07-02/https-github-com-contextualwisdomlab-noema-figma-2/work/pr-895-body.md`

**Interfaces:**
- Produces: pushed PR #895 update

- [x] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py
ruff check api/data.py tests/test_data_api.py
```

- [x] **Step 2: Run frontend focused test**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
pnpm typecheck
```

- [x] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: only Phase 7 files plus unrelated `.Jules/*` dirty files. Do not stage `.Jules/*`.

- [ ] **Step 4: Commit and push**

```bash
git add \
  backend/api/data.py \
  backend/tests/test_data_api.py \
  frontend/src/components/data-layout/types.ts \
  frontend/src/components/data-layout/QualityCheckTab.tsx \
  frontend/src/app/data/page.test.tsx \
  frontend/tests/e2e/helpers.ts \
  docs/superpowers/plans/2026-07-02-content-graph-topology-audit-surface.md
git commit -m "feat: add content graph topology audit surface"
git push origin HEAD:plan/email-dom-paragraph-kg-2026-07-02
```

- [ ] **Step 5: Update PR #895 body and check live state**

Update `work/pr-895-body.md` with Phase 7 summary and verification, then run:

```bash
gh pr edit 895 --repo ContextualWisdomLab/naruon --body-file work/pr-895-body.md
gh pr view 895 --repo ContextualWisdomLab/naruon --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup,url
gh pr checks 895 --repo ContextualWisdomLab/naruon --watch=false
```

Pending or queued checks are not blockers. Failed checks must be inspected and fixed.
