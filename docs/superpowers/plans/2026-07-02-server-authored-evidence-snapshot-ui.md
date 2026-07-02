# Server-Authored Evidence Snapshot UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Data workspace `실사 스냅샷` copy action use the backend-authored `/api/data/quality-surface/evidence-snapshot` contract instead of reconstructing the snapshot in the browser.

**Architecture:** Keep the evidence snapshot inside the existing Data API and Data UI boundary. Fetch the full operational quality surface for cards and fetch the redacted evidence snapshot separately for buyer/auditor copy; do not add a package split, dependency, migration, submodule, or Figma Code Connect metadata.

**Tech Stack:** React/TypeScript, existing `apiClient`, FastAPI/Pydantic contract, Vitest, pytest, ruff, Figma/FigJam.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 11 files.
- The UI must not construct buyer-facing redaction policy, parser manifest, validation status, generated timestamp, or allowlist fields locally.
- The browser request must use same-origin credentials and must not send public identity headers or bearer credentials.
- If snapshot fetch fails, keep the normal quality tab usable and disable snapshot copy with a clear unavailable state.
- Do not expose raw email body, raw HTML, attachment bytes, message IDs, attachment IDs, source record IDs, stable database IDs, provider credentials, DB evidence column strings, or sample raw identifiers in visible UI.
- Review process and queued/pending CI are not blockers; failed CI is actionable.

---

### Task 1: Frontend Snapshot Contract Test

**Files:**
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Expects: `GET /api/data/quality-surface/evidence-snapshot`
- Expects: `DataEvidenceSnapshotResponse`

- [x] **Step 1: Add backend snapshot fixture**

Create a `dataEvidenceSnapshot` fixture derived from the backend response contract, with a deterministic `generated_at` such as `2026-07-02T00:00:00Z`, parser manifest entries including `plain_text`, redaction policy fields, and opaque sample keys distinct from the visible paths.

- [x] **Step 2: Extend `mockWebdavFetch`**

Return `dataEvidenceSnapshot` when `path === "/api/data/quality-surface/evidence-snapshot"`.

- [x] **Step 3: Assert signed snapshot fetch**

In the signed quality surface test, assert that the snapshot endpoint is requested with `credentials: "same-origin"` and without `authorization`, `x-user-id`, `x-organization-id`, `x-group-id`, `x-group-ids`, `x-user-role`, or `x-dev-auth-token`.

- [x] **Step 4: Assert backend-authored values render/copy**

In the quality tab test, assert visible snapshot counts come from `dataEvidenceSnapshot`, and that the copied JSON contains `generated_at: "2026-07-02T00:00:00Z"` and `parser_manifest_summary[0].parser_key: "plain_text"`.

- [x] **Step 5: Add graceful degradation test**

Add one test where `/api/data/quality-surface/evidence-snapshot` returns a 500. The quality tab should still render quality checks, but no copy button should be available and raw identifiers should remain absent.

### Task 2: Fetch Backend Snapshot In DataLayout

**Files:**
- Modify: `frontend/src/components/DataLayout.tsx`
- Modify: `frontend/src/components/data-layout/types.ts` if imports need tightening

**Interfaces:**
- Consumes: `DataEvidenceSnapshotResponse`
- Produces: `dataEvidenceSnapshot` prop for `QualityCheckTab`

- [x] **Step 1: Import `DataEvidenceSnapshotResponse`**

Add the type to the existing DataLayout type import list.

- [x] **Step 2: Add snapshot state**

Add:

```ts
const [dataEvidenceSnapshot, setDataEvidenceSnapshot] = useState<DataEvidenceSnapshotResponse | null>(null);
```

- [x] **Step 3: Fetch snapshot in the existing mount effect**

Call:

```ts
apiClient.get<DataEvidenceSnapshotResponse>('/api/data/quality-surface/evidence-snapshot')
```

Validate `snapshot_version === "data_quality_evidence_snapshot.v1"` and `privacy_redaction_policy.raw_content_exposed === false`; otherwise throw. On success, set the snapshot. On failure, log a safe summary and set it to `null`.

- [x] **Step 4: Refresh snapshot with quality surface reload**

In `loadDataQualitySurface`, fetch the quality surface and snapshot together. If the snapshot fails but the quality surface succeeds, keep the quality surface ready and set snapshot to `null`.

- [x] **Step 5: Pass snapshot to `QualityCheckTab`**

Add `dataEvidenceSnapshot={dataEvidenceSnapshot}` to the quality tab props.

### Task 3: Remove Browser-Built Snapshot

**Files:**
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot: DataEvidenceSnapshotResponse | null`

- [x] **Step 1: Extend props**

Add `dataEvidenceSnapshot` to `QualityCheckTabProps`.

- [x] **Step 2: Delete `buildEvidenceSnapshot`**

Remove the local helper that reconstructs snapshot policy, parser manifest, and validation counts from `DataQualitySurfaceResponse`.

- [x] **Step 3: Render backend snapshot**

Use `dataEvidenceSnapshot` for the `실사 스냅샷` panel and copy payload. Keep the rest of the quality tab sourced from `dataQualitySurface`.

- [x] **Step 4: Disable unavailable copy path**

Render the snapshot panel only when `dataEvidenceSnapshot` exists. This avoids a misleading local fallback when the audited backend contract is unavailable.

### Task 4: Validation

**Files:**
- Test only

- [x] **Step 1: Run frontend focused tests**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
pnpm typecheck
```

Expected: all tests pass.

- [x] **Step 2: Run backend focused contract test**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check api/data.py tests/test_data_api.py
```

Expected: all checks pass.

- [x] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

### Task 5: Figma/FigJam Evidence

**Files:**
- No repo file unless screenshot is intentionally stored outside the repo

- [x] **Step 1: Add Phase 11 diagram**

Use `generate_diagram` on the existing FigJam board `zXkcwT2E2aBtNhMVznLT4l` with a flowchart showing:

- Data quality surface
- Evidence snapshot endpoint
- Same-origin Data UI fetch
- Backend-authored redaction policy
- Buyer copy packet
- Failure path where quality cards remain but copy is disabled

- [x] **Step 2: Group and screenshot**

Group the generated nodes as `Phase 11 Server-Authored Evidence Snapshot Group` and download a screenshot for local visual inspection.

### Task 6: Ship

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-server-authored-evidence-snapshot-ui.md`
- Modify: PR body via `gh pr edit`

- [x] **Step 1: Mark completed plan steps**

Check off all completed steps.

- [x] **Step 2: Commit**

Stage only Phase 11 files and commit:

```bash
git commit -m "feat: use server-authored evidence snapshot"
```

- [x] **Step 3: Push**

Push to `plan/email-dom-paragraph-kg-2026-07-02`.

- [x] **Step 4: Update PR body**

Add Phase 11 scope, validation results, FigJam screenshot path, and current head SHA to PR #895.

- [x] **Step 5: Live PR check**

Re-check PR #895 head, mergeability, checks, and body. Treat queued/pending/review status as non-blocking and failed checks as actionable.
