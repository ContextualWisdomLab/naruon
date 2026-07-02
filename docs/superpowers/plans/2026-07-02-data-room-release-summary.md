# Data Room Release Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a buyer data-room release summary to the redacted evidence snapshot so diligence reviewers can see whether the release bundle is safe to share and what still blocks close.

**Architecture:** Derive the release summary from already-redacted snapshot fields: `data_room_package_manifest`, `privacy_redaction_policy`, `verification_handoff`, and `diligence_close_acceptance_summary`. Keep it inside `DataEvidenceSnapshotResponse`, include it in the tamper-evident digest, and render it in the existing Data Quality snapshot card before detailed manifest entries.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles, FigJam.

## Global Constraints

- Do not use Figma Code Connect.
- Do not add dependencies, package splits, git submodules, provider writes, raw-content export, raw email bodies, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` worktree changes.
- Review process and queued GitHub checks are not blockers; failed local validation or failed live checks are actionable.
- Keep the summary deterministic and derived only from existing safe snapshot fields.

---

### Task 1: Backend Release Summary Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces `DataRoomReleaseSummary`
- Produces `data_room_release_summary: DataRoomReleaseSummary` on `DataEvidenceSnapshotResponse`
- Produces `_data_room_release_summary(snapshot: DataEvidenceSnapshotResponse) -> DataRoomReleaseSummary`

- [x] **Step 1: Add expected backend fixture**

Add `_expected_data_room_release_summary()` to `backend/tests/test_data_api.py` and assert:

```python
{
    "release_key": "buyer_data_room_release",
    "release_status": "release_blocked",
    "total_artifact_count": 10,
    "ready_artifact_count": 7,
    "needs_attention_artifact_count": 3,
    "required_for_close_count": 10,
    "blocked_artifact_files": [
        "acquisition-readiness-summary.json",
        "buyer-evidence-packet-checklist.json",
        "remediation-actions.json",
    ],
    "privacy_exposure_count": 0,
    "raw_content_exposure_count": 0,
    "stable_identifier_exposure_count": 0,
    "provider_credential_exposure_count": 0,
    "snapshot_verification_required": True,
    "verification_command": "python scripts/verify_evidence_snapshot.py <snapshot.json>",
    "acceptance_blocker_count": 9,
    "acceptance_blocker_keys": [
        "exception_attach_kg_evidence_endpoints",
        "exception_backfill_content_graph_coverage",
        "exception_backfill_dedupe_fingerprints",
        "exception_backfill_knowledge_graph_coverage",
        "exception_backfill_semantic_relation_sources",
        "exception_expand_attachment_parse_coverage",
        "exception_recover_attachment_content",
        "exception_repair_segment_text_readiness",
        "exception_repair_thread_id_integrity",
    ],
    "buyer_summary_text": (
        "Data-room release remains blocked by 3 artifact(s), 9 blocker key(s), "
        "and 0 privacy exposure(s)."
    ),
    "next_action_text": (
        "Resolve blocked artifact states, clear acceptance blockers, run the "
        "offline verifier, and reissue the release bundle."
    ),
    "provider_write_executed": False,
}
```

- [x] **Step 2: Add backend model and helper**

Add `DataRoomReleaseStatus = Literal["release_ready", "release_blocked"]`, `DataRoomReleaseSummary`, `_default_data_room_release_summary()`, and `_data_room_release_summary(snapshot)`.

- [x] **Step 3: Include summary in digest**

Populate `data_room_release_summary` after `diligence_close_acceptance_summary` and before `_snapshot_digest_payload(snapshot)`.

- [x] **Step 4: Run backend validation**

Run:

```bash
python3 -m pytest backend/tests/test_data_api.py -q
python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py
```

### Task 2: Frontend Release Summary Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes `dataEvidenceSnapshot.data_room_release_summary`
- Renders an existing-style snapshot card section titled `Data room release summary`

- [x] **Step 1: Add TypeScript type and fixture**

Mirror the backend fixture in `frontend/src/app/data/page.test.tsx` and add the response type in `frontend/src/components/data-layout/types.ts`.

- [x] **Step 2: Render release summary**

Show release status, buyer summary, next action, artifact readiness counts, privacy exposure counts, verification command, acceptance blocker count, blocked artifact chips, acceptance blocker chips, and write boundary.

- [x] **Step 3: Assert UI and copied JSON**

Assert visible text includes `Data room release summary`, `release_blocked`, `Data-room release remains blocked`, `blocked 3`, `privacy exposures 0`, `verify-evidence-snapshot.py`, `buyer-evidence-packet-checklist.json`, and `exception_attach_kg_evidence_endpoints`. Assert copied JSON includes `data_room_release_summary` exactly.

- [x] **Step 4: Run frontend validation**

Run:

```bash
cd frontend && npm test -- src/app/data/page.test.tsx
cd frontend && npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx
```

### Task 3: FigJam, Ponytail, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-data-room-release-summary.md`

- [x] **Step 1: Generate FigJam flowchart**

Add a Phase 32 flowchart to the existing FigJam board showing manifest, privacy policy, verifier, and acceptance summary rolling into release blocked or release ready.

- [x] **Step 2: Run Ponytail diff review**

Confirm the diff does not add dependencies, speculative package boundaries, or a separate library/submodule for one derived snapshot projection.

- [x] **Step 3: Push and verify PR**

Commit, push to `plan/email-dom-paragraph-kg-2026-07-02`, and verify live PR #901 head, unresolved review thread count, and check state.

## Evidence

- Backend validation: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed and 1 skipped.
- Backend lint: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend coverage: `npm test -- src/app/data/page.test.tsx` passed with 13 tests.
- Frontend lint: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- FigJam: https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R
- Ponytail complexity review: Lean already. Ship.
- Product/design decision: no separate library or submodule is warranted yet because this is a deterministic buyer handoff summary over existing safe snapshot fields.
