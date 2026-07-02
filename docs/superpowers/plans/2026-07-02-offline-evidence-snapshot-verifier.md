# Offline Evidence Snapshot Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stdlib-only offline verifier so buyer due-diligence JSON copied from `/api/data/quality-surface/evidence-snapshot` can be checked outside Naruon without trusting the browser or server again.

**Architecture:** Keep the verifier as a narrow script under `backend/scripts/` instead of a new package, submodule, or shared library. It must use the same canonical SHA-256 rule as the backend snapshot response: remove digest metadata, serialize stable JSON with sorted keys and compact separators, then compare against `snapshot_digest`. Output stays compact JSON and never echoes raw payload fields.

**Tech Stack:** Python 3.14 stdlib `argparse`, `hashlib`, `json`, `sys`, pytest, ruff, Figma/FigJam.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 13 files.
- Do not add dependencies, migrations, package splits, submodules, key management, HMAC secrets, public CI mail-corpus flows, or Figma Code Connect.
- The verifier must accept a JSON file path or stdin via `-`.
- The canonical payload must exclude `snapshot_digest`, `digest_algorithm`, and `canonical_payload_fields`.
- The verifier must support only `digest_algorithm == "sha256"`.
- The verifier must return exit code `0` for a matching digest and non-zero for malformed JSON, missing digest metadata, unsupported algorithm, or digest mismatch.
- The verifier output must include `ok`, `digest_algorithm`, `expected_digest`, `actual_digest`, and `canonical_payload_fields` on success or mismatch.
- Error output must use short machine-readable JSON and must not echo raw email body, raw HTML, attachment bytes, message IDs, attachment IDs, source record IDs, stable database IDs, provider credentials, DB evidence column strings, or raw sample identifiers.
- Review process and queued/pending CI are not blockers; failed CI is actionable.

---

### Task 1: Verifier Contract Tests

**Files:**
- Create: `backend/tests/test_evidence_snapshot_verifier.py`

**Interfaces:**
- Consumes: `backend/scripts/verify_evidence_snapshot.py`
- Expects: `verify_snapshot_payload(snapshot: dict[str, object]) -> VerificationResult`
- Expects CLI: `python scripts/verify_evidence_snapshot.py <path-or->`

- [x] **Step 1: Add a helper that builds a valid snapshot**

Create a fixture-like helper that builds a safe minimal snapshot, removes digest metadata, canonicalizes with:

```python
json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
```

Then sets:

```python
snapshot["snapshot_digest"] = hashlib.sha256(canonical_payload).hexdigest()
snapshot["digest_algorithm"] = "sha256"
snapshot["canonical_payload_fields"] = sorted(payload)
```

- [x] **Step 2: Test in-process success**

Import `scripts.verify_evidence_snapshot` and assert:

```python
result = verifier.verify_snapshot_payload(snapshot)
assert result.ok is True
assert result.exit_code == 0
assert result.actual_digest == snapshot["snapshot_digest"]
assert result.expected_digest == snapshot["snapshot_digest"]
assert result.canonical_payload_fields == snapshot["canonical_payload_fields"]
```

- [x] **Step 3: Test mismatch without raw leakage**

Change a safe count in the snapshot without updating `snapshot_digest`. Assert `ok is False`, `exit_code == 4`, expected and actual digests differ, and `result.to_output()` does not include forbidden raw/private strings.

- [x] **Step 4: Test malformed and unsupported metadata paths**

Use `pytest.raises(SystemExit)` only for CLI entry points. In direct function tests, assert:

```python
assert verifier.verify_snapshot_payload({"digest_algorithm": "sha256"}).error_code == "missing_snapshot_digest"
assert verifier.verify_snapshot_payload({"snapshot_digest": "abc", "digest_algorithm": "sha512"}).error_code == "unsupported_digest_algorithm"
```

- [x] **Step 5: Test CLI file and stdin modes**

Use `subprocess.run` with:

```bash
python scripts/verify_evidence_snapshot.py snapshot.json
python scripts/verify_evidence_snapshot.py -
```

Assert both return code `0` for the valid snapshot and output JSON has `ok: true`.

- [x] **Step 6: Verify initial failure**

Run:

```bash
cd backend
python -m pytest -q tests/test_evidence_snapshot_verifier.py
```

Expected: FAIL because the verifier script does not exist yet.

### Task 2: Stdlib Verifier Implementation

**Files:**
- Create: `backend/scripts/verify_evidence_snapshot.py`

**Interfaces:**
- Produces: `VerificationResult`
- Produces: `verify_snapshot_payload(snapshot: dict[str, object]) -> VerificationResult`
- Produces CLI: `main(argv: list[str] | None = None) -> int`

- [x] **Step 1: Add constants and result dataclass**

Use:

```python
DIGEST_EXCLUDED_FIELDS = {
    "snapshot_digest",
    "digest_algorithm",
    "canonical_payload_fields",
}
SUPPORTED_ALGORITHM = "sha256"
```

Add `VerificationResult` with fields:

```python
ok: bool
exit_code: int
digest_algorithm: str | None
expected_digest: str | None
actual_digest: str | None
canonical_payload_fields: list[str]
error_code: str | None = None
```

and `to_output(self) -> dict[str, object]` returning only those safe fields.

- [x] **Step 2: Add canonical digest helpers**

Add `_digest_payload(snapshot)` and `_sha256_digest(payload)` using the same JSON canonicalization rule as the backend API and tests.

- [x] **Step 3: Add `verify_snapshot_payload`**

Validation order:

1. `snapshot_digest` must be a non-empty string, else return `missing_snapshot_digest`, exit code `2`.
2. `digest_algorithm` must be `"sha256"`, else return `unsupported_digest_algorithm`, exit code `3`.
3. Remove digest metadata, recompute digest, compare with supplied digest.
4. Match returns `ok=True`, exit code `0`; mismatch returns `ok=False`, error code `digest_mismatch`, exit code `4`.

- [x] **Step 4: Add CLI input and JSON output**

`main()` must parse one positional `snapshot`, where `-` reads from stdin and any other value reads UTF-8 JSON from that file. Malformed JSON or non-object JSON returns:

```json
{"ok": false, "error_code": "invalid_json"}
```

with exit code `1`.

- [x] **Step 5: Verify backend pass**

Run:

```bash
cd backend
python -m pytest -q tests/test_evidence_snapshot_verifier.py
ruff check scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py
```

Expected: PASS.

### Task 3: Figma/FigJam Evidence

**Files:**
- No repo file unless screenshot is intentionally stored outside the repo

- [x] **Step 1: Add Phase 13 diagram**

Use `generate_diagram` on FigJam board `zXkcwT2E2aBtNhMVznLT4l` with a flowchart showing:

- Copied evidence snapshot JSON
- Offline verifier script
- Canonical payload without digest metadata
- SHA-256 recomputation
- Match result
- Buyer accepts packet or investigates tampering

- [x] **Step 2: Group and screenshot**

Group generated nodes as `Phase 13 Offline Evidence Snapshot Verification Group` and download a screenshot for local visual inspection.

### Task 4: Ship

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-offline-evidence-snapshot-verifier.md`
- Modify: PR body via `gh pr edit`

- [ ] **Step 1: Run final focused validation**

Run:

```bash
cd backend
python -m pytest -q tests/test_evidence_snapshot_verifier.py tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py api/data.py tests/test_data_api.py
git diff --check
```

Expected: PASS/no output.

- [ ] **Step 2: Commit implementation**

Stage only Phase 13 files and commit:

```bash
git commit -m "feat: add offline evidence snapshot verifier"
```

- [ ] **Step 3: Push**

Push to `plan/email-dom-paragraph-kg-2026-07-02`.

- [ ] **Step 4: Update PR body**

Add Phase 13 scope, validation results, FigJam screenshot path, and current head SHA to PR #895.

- [ ] **Step 5: Mark plan complete and commit docs**

Check off completed ship steps, commit:

```bash
git commit -m "docs: mark phase 13 plan complete"
```

- [ ] **Step 6: Live PR check**

Re-check PR #895 head, mergeability, reviewThreads, checks, and body. Treat queued/pending/review status as non-blocking and failed checks as actionable.
