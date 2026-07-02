# Semantic KG Readiness Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a buyer-visible semantic KG readiness manifest that distinguishes deterministic DOM/paragraph graph edges from future entity/relation extraction without exposing raw email or attachment content.

**Architecture:** Extend the existing data quality surface and evidence snapshot contracts in `backend/api/data.py` with a static, server-authored readiness manifest and a quality check. Reuse the existing quality tab and snapshot JSON copy flow in the frontend; no new parser package, submodule, migration, dependency, or Figma Code Connect is needed.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy aggregate-backed data surface, React/TypeScript, Vitest, pytest, ruff, Figma/FigJam.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 14 files.
- Do not add dependencies, migrations, submodules, package splits, raw-content export, LLM calls, provider writes, browser-stored bearer tokens, public identity headers, or Figma Code Connect.
- The manifest must be safe for due diligence packets: no raw email body, raw HTML, attachment bytes, stable database IDs, provider credentials, raw sample identifiers, or evidence SQL column strings.
- The manifest must make the current state explicit: deterministic structural KG edges are present, semantic entity/relation extraction is gated behind provenance, confidence, correction-path, and approved extractor evidence.
- Review process and queued/pending CI are not blockers; failed CI is actionable.

---

### Task 1: Backend Contract Tests

**Files:**
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Expects `DataQualitySurfaceResponse.semantic_extraction_manifest`
- Expects `DataEvidenceSnapshotResponse.semantic_extraction_manifest`
- Expects quality check `semantic_kg_readiness`

- [ ] **Step 1: Extend quality-surface assertions**

In `test_data_quality_surface_returns_source_backed_counts_without_secrets`, add assertions for:

```python
assert quality_by_key["semantic_kg_readiness"] == {
    "check_key": "semantic_kg_readiness",
    "display_name": "Semantic KG readiness",
    "status_code": "pending",
    "issue_count": 0,
    "total_count": 1,
    "evidence_source": "knowledge_graph_edges.edge_kind, content_segments.segment_path",
    "detail_text": (
        "Semantic entity/relation extraction is gated until provenance, "
        "confidence, and correction-path evidence are configured."
    ),
    "provider_write_executed": False,
}
```

Also assert `data["semantic_extraction_manifest"]` contains one item with `manifest_key == "entity_relation_extraction"` and `state_code == "provenance_gate_pending"`.

- [ ] **Step 2: Extend evidence-snapshot assertions**

In `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`, update validation totals to include the new pending check:

```python
assert snapshot["validation_status"]["total_checks"] == 11
```

Assert the copied snapshot includes `semantic_extraction_manifest`, the manifest appears in `canonical_payload_fields`, and forbidden raw/private strings are still absent.

- [ ] **Step 3: Verify initial failure**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
```

Expected: FAIL because the API contract does not expose the manifest yet.

### Task 2: Backend Manifest Implementation

**Files:**
- Modify: `backend/api/data.py`

**Interfaces:**
- Produces `DataSemanticExtractionManifest`
- Produces `_semantic_extraction_manifest() -> list[DataSemanticExtractionManifest]`
- Produces `_check_semantic_kg_readiness() -> DataQualityCheck`

- [ ] **Step 1: Add constants and model**

Add evidence-source and allowed snapshot field constants:

```python
SEMANTIC_KG_READINESS_EVIDENCE_SOURCE = (
    "knowledge_graph_edges.edge_kind, content_segments.segment_path"
)
```

Add `DataSemanticExtractionManifest` with:

```python
manifest_key: str
display_name: str
state_code: Literal["provenance_gate_pending", "ready"]
structural_edge_count: int
semantic_relation_count: int
required_evidence: list[str]
detail_text: str
provider_write_executed: bool
```

- [ ] **Step 2: Add manifest helper and quality check**

Implement `_semantic_extraction_manifest(knowledge_graph_edge_count: int)`, returning one safe item:

```python
manifest_key="entity_relation_extraction"
display_name="Entity/relation extraction"
state_code="provenance_gate_pending"
structural_edge_count=knowledge_graph_edge_count
semantic_relation_count=0
required_evidence=[
    "segment_citation",
    "extractor_version",
    "confidence_score",
    "human_correction_path",
]
detail_text="Structural DOM/paragraph edges are stored; semantic entity/relation extraction has not been enabled for buyer-visible evidence."
provider_write_executed=False
```

Implement `_check_semantic_kg_readiness()` with status `pending`, issue count `0`, and total count `1`.

- [ ] **Step 3: Wire response and snapshot**

Add `semantic_extraction_manifest` to `DataQualitySurfaceResponse` and `DataEvidenceSnapshotResponse`, copy it in `_evidence_snapshot_from_surface`, and include it in `get_data_quality_surface(...)` using the current `knowledge_graph_edge_count`.

- [ ] **Step 4: Verify backend pass**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_surface_returns_source_backed_counts_without_secrets tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check api/data.py tests/test_data_api.py
```

Expected: PASS.

### Task 3: Frontend Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes `semantic_extraction_manifest` from both surface and snapshot.

- [ ] **Step 1: Update TypeScript contracts and fixtures**

Add `semantic_extraction_manifest` arrays to `DataQualitySurfaceResponse` and `DataEvidenceSnapshotResponse`. Update test fixtures and `canonical_payload_fields` to include `semantic_extraction_manifest`.

- [ ] **Step 2: Render buyer-visible readiness**

In `QualityCheckTab`, derive:

```ts
const semanticExtractionManifest = dataQualitySurface?.semantic_extraction_manifest ?? [];
```

Render a compact section titled `Semantic KG readiness` after the KG evidence samples. Show display name, state, structural edge count, semantic relation count, required evidence, detail text, and write boundary. Do not show backend evidence-source strings.

- [ ] **Step 3: Verify frontend assertions**

In `renders API-backed pipeline embedding and quality tabs`, assert the UI contains:

```ts
expect(container.textContent).toContain("Semantic KG readiness");
expect(container.textContent).toContain("Entity/relation extraction");
expect(container.textContent).toContain("provenance_gate_pending");
expect(container.textContent).toContain("segment_citation");
expect(container.textContent).not.toContain("knowledge_graph_edges.edge_kind");
```

Also assert copied snapshot contains `semantic_extraction_manifest`.

- [ ] **Step 4: Verify frontend pass**

Run:

```bash
cd frontend
npm test -- --run src/app/data/page.test.tsx
```

Expected: PASS.

### Task 4: Figma/FigJam Evidence

**Files:**
- No repo file unless screenshot is intentionally stored outside the repo.

- [ ] **Step 1: Add Phase 14 diagram**

Use `generate_diagram` on FigJam board `zXkcwT2E2aBtNhMVznLT4l` with a flowchart showing:

- DOM/paragraph structural KG edges
- Semantic extraction manifest
- Provenance/confidence/correction gate
- Buyer snapshot packet
- Future approved entity/relation extractor

- [ ] **Step 2: Group and screenshot**

Group generated nodes as `Phase 14 Semantic KG Readiness Manifest Group` and download a screenshot for local visual inspection.

### Task 5: Ship

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-semantic-kg-readiness-manifest.md`
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

Expected: PASS/no output.

- [ ] **Step 2: Commit implementation**

Stage only Phase 14 files and commit:

```bash
git commit -m "feat: add semantic kg readiness manifest"
```

- [ ] **Step 3: Push**

Push to `plan/email-dom-paragraph-kg-2026-07-02`.

- [ ] **Step 4: Update PR body**

Add Phase 14 scope, validation results, FigJam screenshot path, and current head SHA to PR #895.

- [ ] **Step 5: Mark plan complete and commit docs**

Check off completed ship steps, commit:

```bash
git commit -m "docs: mark phase 14 plan complete"
```

- [ ] **Step 6: Live PR check**

Re-check PR #895 head, mergeability, reviewThreads, checks, and body. Treat queued/pending/review status as non-blocking and failed checks as actionable.
