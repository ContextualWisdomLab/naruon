# Naruon Security Governance Follow-up

Date: 2026-07-02 KST

## Scope

This follow-up addresses issue #634, `Track post-merge security gate failure on PR #631`, as part of the 20B KRW commercial-readiness work.

The issue tracks a governance failure mode:

- A PR can have blocker evidence, such as `CHANGES_REQUESTED` or failed required-check metadata.
- The PR governance script can publish a blocker comment.
- Before this patch, the script still exited `0`, allowing the `metadata-only gate evaluation` check to appear green.

That is not acceptable for enterprise sale readiness because the status check and governance comment can disagree.

## Decision

Patch one central gate instead of each workflow.

The current `.github/workflows/pr-governance.yml` materializes and runs `scripts/ci/pr_governance_gate.sh` from the trusted base ref. The workflow does not need a structural change for this fix. The central script now exits non-zero whenever it posts or updates a blocker comment.

## Implementation

Changed files:

- `scripts/ci/pr_governance_gate.sh`
- `scripts/ci/test_pr_governance_gate.sh`

Behavior after the patch:

```text
BLOCKERS present  -> post/update marker comment -> exit 1
WAITING present   -> print waiting evidence     -> exit 0
No issues present -> print ready evidence       -> exit 0
```

The waiting state remains green because pending required checks remain separately pending under branch protection. Concrete blocker evidence is now fail-closed.

## Regression Coverage

The shell test now records the gate process exit code and asserts:

- failed required checks exit `1`
- `STARTUP_FAILURE` exits `1`
- `CHANGES_REQUESTED` exits `1`
- current-head CodeRabbit blocking evidence exits `1`
- pending required checks exit `0`
- missing or pending CodeRabbit evidence exits `0`
- passing governance exits `0`

Validation commands:

```text
bash scripts/ci/test_pr_governance_gate.sh
test_pr_governance_gate: PASS

cd backend && python3 -m pytest tests/test_release_governance.py -q
29 passed in 0.21s
```

## Residual Risk

This patch will govern future PRs after it lands on the trusted base branch. The current pull request's `pull_request_target` governance job still uses the existing trusted base script until this change is merged. Therefore issue #634 should remain open until the fix is merged and a follow-up governance run proves blocker comments produce a failing check on the base branch.

## Sale-readiness Impact

This reduces a P0 governance risk for the 20B KRW package, but it does not complete the full sale-readiness goal. Remaining blockers still include production deployment proof, live provider execution evidence, buyer security/compliance packaging, full responsive design QA, and measured ROI evidence.
