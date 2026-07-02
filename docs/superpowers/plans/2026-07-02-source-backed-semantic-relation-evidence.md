# Source-Backed Semantic Relation Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect existing source-backed sender relationship records to the data quality surface and evidence snapshot so buyers can verify semantic relation evidence without raw email, attachment content, stable IDs, or provider credentials.

**Architecture:** Reuse the existing `sender_relationships` ontology table as the semantic relation evidence source and keep it inside the current backend/frontend product boundary. Extend `backend/api/data.py` with scoped aggregate stats, safe hashed samples, a source-backing quality check, and a manifest that reports real relation counts; update the existing React quality tab with the same card pattern. No parser engine split, dependency, submodule, migration, or Figma Code Connect is needed for this phase.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy aggregate queries, existing ontology service/table, React/TypeScript, Vitest, pytest, ruff, Figma/FigJam.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 15 files.
- Do not add dependencies, migrations, submodules, package splits, raw-content export, LLM calls, provider writes, browser-stored bearer tokens, public identity headers, or Figma Code Connect.
- The API and copied evidence snapshot must not expose `sender_email`, `parent_sender_email`, raw `source_message_id`, raw `source_thread_id`, raw body/content, stable database IDs, provider credentials, or SQL evidence-source strings.
- The semantic relation evidence must be scoped through the signed user and organization context, matching the ontology API owner boundary.
- Review process and queued/pending CI are not blockers; failed CI is actionable.

---

### Task 1: Backend Contract Tests

**Files:**
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Expects `DataQualitySurfaceResponse.semantic_relation_evidence_samples`
- Expects `DataEvidenceSnapshotResponse.semantic_relation_evidence_samples`
- Expects `DataSemanticExtractionManifest.source_backed_relation_count`
- Expects quality check `semantic_relation_source_backing`

- [ ] **Step 1: Extend mock query fixtures**

Add a semantic relation stats tuple immediately after the knowledge graph evidence samples mock result:

```python
(3, 2),  # semantic relation evidence stats
```

Add safe semantic relation sample rows immediately after it:

```python
[
    (
        "partner@example.com",
        "<asset-ready@example.com>",
        "thread-ready",
        "Vendor",
        0.92,
    ),
    (
        "updates@example.com",
        "<newsletter@example.com>",
        None,
        "Newsletter",
        0.86,
    ),
],  # semantic relation evidence samples
```

- [ ] **Step 2: Extend quality-surface assertions**

In `test_data_quality_surface_returns_source_backed_counts_without_secrets`, assert:

```python
assert quality_by_key["semantic_relation_source_backing"] == {
    "check_key": "semantic_relation_source_backing",
    "display_name": "Semantic relation source backing",
    "status_code": "needs_attention",
    "issue_count": 1,
    "total_count": 3,
    "evidence_source": (
        "sender_relationships.source_message_id, "
        "sender_relationships.source_thread_id"
    ),
    "detail_text": "Some semantic relations need source message or thread evidence.",
    "provider_write_executed": False,
}
```

Update `semantic_extraction_manifest` to expect:

```python
"state_code": "ready",
"semantic_relation_count": 3,
"source_backed_relation_count": 2,
"detail_text": (
    "Semantic relation evidence is available from source-backed ontology "
    "relationship records."
),
```

Assert `data["semantic_relation_evidence_samples"]` contains two hashed safe samples with `sample_key`, `relationship_type`, `confidence_bucket`, `source_scope`, and `next_action`.

- [ ] **Step 3: Extend snapshot assertions**

In `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`, assert:

```python
assert snapshot["validation_status"] == {
    "status_code": "needs_attention",
    "checks_passed": 3,
    "checks_with_issues": 8,
    "total_checks": 12,
}
assert "semantic_relation_evidence_samples" in snapshot["canonical_payload_fields"]
```

Add the safe semantic sample fields to `allowed_sample_fields`, and assert forbidden raw sender/source values are absent from both surface and snapshot serialized text.

- [ ] **Step 4: Verify initial failure**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
```

Expected: FAIL because the API contract does not expose semantic relation evidence yet.

### Task 2: Backend Implementation

**Files:**
- Modify: `backend/api/data.py`

**Interfaces:**
- Produces `DataSemanticRelationEvidenceSample`
- Produces `_get_semantic_relation_evidence_stats(db, auth_context) -> SemanticRelationEvidenceStats`
- Produces `_get_semantic_relation_evidence_samples(db, auth_context) -> list[DataSemanticRelationEvidenceSample]`
- Produces `_check_semantic_relation_source_backing(total_count, issue_count) -> DataQualityCheck`

- [ ] **Step 1: Import model and add constants**

Import `SenderRelationship` from `db.models`, add:

```python
SEMANTIC_RELATION_SOURCE_BACKING_EVIDENCE_SOURCE = (
    "sender_relationships.source_message_id, "
    "sender_relationships.source_thread_id"
)
```

- [ ] **Step 2: Add data models and snapshot allowlist fields**

Add:

```python
class SemanticRelationEvidenceStats(NamedTuple):
    total_count: int
    source_backed_count: int


class DataSemanticRelationEvidenceSample(BaseModel):
    sample_key: str
    relationship_type: str
    confidence_bucket: Literal["high", "medium", "low", "unknown"]
    source_scope: Literal["message_thread", "message", "thread", "unknown"]
    next_action: str
```

Add `source_backed_relation_count: int` to `DataSemanticExtractionManifest`.

Add `semantic_relation_evidence_samples` to both response models and snapshot copy path.

Add `relationship_type`, `confidence_bucket`, `source_scope`, `next_action`, and `source_backed_relation_count` to `SNAPSHOT_ALLOWED_SAMPLE_FIELDS`.

- [ ] **Step 3: Add safe row helpers**

Implement:

```python
def _confidence_bucket(value: float | None) -> Literal["high", "medium", "low", "unknown"]:
    if value is None:
        return "unknown"
    if value >= 0.8:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _semantic_relation_source_scope(
    source_message_id: str | None,
    source_thread_id: str | None,
) -> Literal["message_thread", "message", "thread", "unknown"]:
    if source_message_id and source_thread_id:
        return "message_thread"
    if source_message_id:
        return "message"
    if source_thread_id:
        return "thread"
    return "unknown"
```

Generate sample keys from a SHA-256 digest over `sender_email`, `source_message_id`, `source_thread_id`, and `relationship_type`, exposing only a `relation_<16 hex>` value.

- [ ] **Step 4: Add scoped aggregate queries**

Use the same owner/org scoping style as the ontology API:

```python
organization_filter = (
    SenderRelationship.organization_id == auth_context.organization_id
    if auth_context.organization_id is not None
    else SenderRelationship.organization_id.is_(None)
)
```

Count all scoped relations and source-backed relations where either `source_message_id` or `source_thread_id` is not null. Fetch up to 8 samples ordered by `confidence_score.desc()`, `updated_at.desc()`, `relationship_type.asc()`.

- [ ] **Step 5: Wire quality checks, manifest, and snapshot**

Compute:

```python
semantic_relation_stats = await _get_semantic_relation_evidence_stats(db, auth_context)
semantic_relation_evidence_samples = await _get_semantic_relation_evidence_samples(db, auth_context)
semantic_relation_issue_count = max(
    0,
    semantic_relation_stats.total_count - semantic_relation_stats.source_backed_count,
)
```

Pass counts into `_quality_checks` and `_semantic_extraction_manifest`.

The manifest is `ready` when `source_backed_relation_count > 0`; otherwise keep `provenance_gate_pending`.

- [ ] **Step 6: Verify backend pass**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check api/data.py tests/test_data_api.py
```

Expected: PASS.

### Task 3: Real Postgres Smoke Coverage

**Files:**
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Reuses `sender_relationships` table created by existing metadata bootstrap.

- [ ] **Step 1: Seed source-backed and rival semantic relations**

In `_seed_smoke_test_data`, insert one scoped relation with `source_message_id` and `source_thread_id`, plus one rival relation. Use realistic but test-only sender addresses.

- [ ] **Step 2: Teardown semantic relations**

In `_teardown_smoke_test_data`, delete scoped and rival `sender_relationships` rows before deleting emails.

- [ ] **Step 3: Assert smoke scope**

In `test_data_quality_surface_real_postgres_smoke_uses_signed_scope`, assert:

```python
assert quality_by_key["semantic_relation_source_backing"]["issue_count"] == 0
assert data["semantic_extraction_manifest"][0]["semantic_relation_count"] == 1
assert data["semantic_relation_evidence_samples"][0]["relationship_type"] == "Vendor"
assert "rival-semantic@example.com" not in response.text
```

### Task 4: Frontend Contract and UI

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes `semantic_relation_evidence_samples` from surface and snapshot.
- Consumes `source_backed_relation_count` from `semantic_extraction_manifest`.

- [ ] **Step 1: Update TypeScript types and fixtures**

Add the semantic relation sample array type to `DataQualitySurfaceResponse` and `DataEvidenceSnapshotResponse`. Add `source_backed_relation_count` to both manifest types.

Update the page test fixtures with two semantic relation samples and the updated snapshot canonical/allowlist fields.

- [ ] **Step 2: Render semantic relation evidence**

In `QualityCheckTab`, derive:

```ts
const semanticRelationEvidenceSamples = dataQualitySurface?.semantic_relation_evidence_samples ?? [];
```

Render a section titled `Semantic relation evidence` after `Semantic KG readiness`, showing relationship type, confidence bucket, source scope, next action, and write boundary. Do not show raw sender/source identifiers or backend evidence-source strings.

- [ ] **Step 3: Verify frontend assertions**

In `renders API-backed pipeline embedding and quality tabs`, assert the UI contains:

```ts
expect(container.textContent).toContain("Semantic relation evidence");
expect(container.textContent).toContain("Vendor");
expect(container.textContent).toContain("message_thread");
expect(container.textContent).toContain("prepare_response_draft");
```

Assert it does not contain raw sample IDs, sender emails, message IDs, or `sender_relationships.source_message_id`.

- [ ] **Step 4: Verify frontend pass**

Run:

```bash
cd frontend
npm test -- --run src/app/data/page.test.tsx
```

Expected: PASS.

### Task 5: Figma/FigJam Evidence

**Files:**
- No repo file unless screenshot is intentionally stored outside the repo.

- [ ] **Step 1: Add Phase 15 diagram**

Use `generate_diagram` on FigJam board `zXkcwT2E2aBtNhMVznLT4l` with a flowchart showing:

- `sender_relationships` source-backed ontology records
- signed scope aggregate count
- source-backing quality check
- safe hashed semantic relation samples
- evidence snapshot copy path
- buyer due-diligence review without raw content or IDs

- [ ] **Step 2: Group and screenshot**

Group generated nodes as `Phase 15 Source-Backed Semantic Relation Evidence Group` and download a screenshot for local visual inspection.

### Task 6: Ship

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-source-backed-semantic-relation-evidence.md`
- Modify: PR body via `gh pr edit`

- [ ] **Step 1: Run final focused validation**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check api/data.py tests/test_data_api.py
cd ../frontend
npm test -- --run src/app/data/page.test.tsx
cd ..
git diff --check
```

- [ ] **Step 2: Commit implementation**

Stage only Phase 15 backend/frontend files:

```bash
git add backend/api/data.py backend/tests/test_data_api.py frontend/src/components/data-layout/types.ts frontend/src/components/data-layout/QualityCheckTab.tsx frontend/src/app/data/page.test.tsx
git commit -m "feat: add source-backed semantic relation evidence"
```

- [ ] **Step 3: Mark plan complete and commit docs**

Change all checkboxes in this plan to `[x]`, then:

```bash
git add docs/superpowers/plans/2026-07-02-source-backed-semantic-relation-evidence.md
git commit -m "docs: mark phase 15 plan complete"
```

- [ ] **Step 4: Push and update PR**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, update PR #895 with Phase 15 summary, validation, FigJam evidence, final HEAD, and the no-new-library/submodule decision.

- [ ] **Step 5: Live status check**

Check:

```bash
gh pr view 895 --repo ContextualWisdomLab/naruon --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup,reviewDecision,url
```

Summarize failed, pending, and queued checks without treating queued review processes as blockers.
