# Merge Gate Policy

This repository's merge gate is evidence-based: required checks must pass,
review threads must be resolved, robot-review evidence must be current-head, and
the live organization ruleset currently requires one qualifying independent
approval. Robot-review evidence does not replace the GitHub approval requirement
unless that evidence is itself carried by a qualifying `APPROVED` review object.

## Required gate contract

- Required status checks must pass on the current head SHA.
- Application CI must run backend pytest and frontend test/lint/build checks on
  pull requests to `develop`, `master`, and `release/**`; pushes to `develop`
  and `master` are also checked so the current protected/default path is not
  omitted by legacy master-only guidance.
- The robot-review gate prefers CodeRabbit evidence. When the current head has
  CodeRabbit check-run evidence, it satisfies the robot-evidence gate only when
  current-head blocking findings, warnings, and failures are fixed, rebutted
  with evidence, or superseded. Authoritative current-head `Review skipped`
  evidence satisfies that path only when applicable. When no CodeRabbit
  check-run exists, the gate waits for an exact-current-head `APPROVED` review
  from the `opencode-agent` GitHub App. The review body must name the head SHA
  and include structured adversarial validation with `status=passed` and at
  least two probes whose outcome is `falsified`. Stale-head reviews,
  `github-actions` reviews, and insufficient probe evidence do not satisfy the
  robot-evidence gate.
- The active organization ruleset `CWL Central required workflows` currently
  sets `required_approving_review_count=1`. Do not lower that count, add a
  bypass, or reinterpret robot status/check evidence as an approval merely to
  land a PR. A merge therefore needs one qualifying independent approval in
  addition to the other live gates. If the canonical organization owner later
  changes this contract, refetch the ruleset first and update this document and
  the robot-review skill in the same evidence-backed change.
- PR Governance automation is metadata-only: it must not checkout pull request
  code, clone the head branch, dismiss reviews, enable auto-merge, or use admin
  merge. It may read PR/check/review-thread metadata and post blocker comments;
  the separate human/agent landing path performs any allowed merge action after
  current-head gates are satisfied. Submitted and dismissed review events rerun
  the metadata controller so OpenCode App evidence updates the gate promptly.
- PR Governance runs trusted-base logic only. The workflow materializes the base
  repository script from a trusted tarball and must not execute PR-head scripts.
  Trusted tarball materialization uses bounded retry plus archive validation for
  transient GitHub API truncation and fails closed instead of falling back to
  PR-head or local scripts.
- Pending, queued, requested, waiting, or in-progress checks are wait states, not
  hard failure findings. Success, pass, skipped, and neutral states satisfy the
  repository policy only where the live required workflow/ruleset also accepts
  them. Every other required-check state — including failed, cancelled,
  timed-out, action-required, and any unrecognized state — is a blocker: the
  gate fails closed rather than passing states it does not understand.
- If gate evaluation itself errors (for example a transient GitHub API
  failure), the gate publishes a completed/failure check-run instead of leaving
  a previously published result in place.
- Gate blocker comments publish sanitized check names and generic error text
  only; raw CLI diagnostics stay in the workflow run log. Inside Actions the
  gate runs with a pinned system PATH so earlier steps cannot influence tool
  resolution via GITHUB_PATH.
- Authoritative `Review skipped` evidence counts only when the same check
  output carries no blocking warning/failure language alongside it.
- `reviewDecision=CHANGES_REQUESTED` is a blocker until requested changes are
  addressed or superseded on the current head.
- Blocker comments use the idempotent
  `<!-- pr-governance:metadata-gate -->` marker and are patched in place instead
  of duplicated on repeated workflow events.
- GitHub rulesets must keep `required_review_thread_resolution=true`.
- CodeRabbit `request_changes_workflow` stays enabled so the robot can clear
  its own requested-changes review after comments are resolved. CodeRabbit
  GitHub Checks integration stays disabled because GitHub Actions are already
  evaluated by required checks and PR Governance; duplicating that gate inside
  CodeRabbit can strand stale GitHub `CHANGES_REQUESTED` review objects when an
  unrelated scanner is temporarily failing.
- Bypass actors must not be configured for routine delivery.
- Security workflows and scanners are required gates, not optional paths.

## Evidence commands

Use the same head SHA across all checks:

```bash
gh pr view <pr> \
  --json number,headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
gh pr checks <pr> --required
gh api repos/<owner>/<repo>/pulls/<pr>/reviews
gh api repos/<owner>/<repo>/commits/<sha>/check-runs
gh api repos/<owner>/<repo>/rulesets --jq '.[] | {name, enforcement, rules}'
```

## Robot review versus GitHub approval

CodeRabbit review/check evidence satisfies this repo's preferred robot-review
path only after current-head blocking comments, pre-merge warnings, and failure
findings are resolved or superseded. That evidence is distinct from the live
GitHub approval-count rule. A CodeRabbit or OpenCode review satisfies the
approval rule only when GitHub records it as a qualifying current-head
`APPROVED` review; a check-run, walkthrough, overview comment, or
`github-actions` review is not a substitute.

The active organization ruleset currently requires
`required_approving_review_count=1`. Do not lower the rule to unblock a PR.
Refetch the ruleset before each lifecycle decision, then require the current
approval count together with current-head robot evidence, required checks, and
thread resolution.

## Stale required contexts

A required context can become stale when the PR is fixing the workflow that
emits it. For example, PRs that fix Strix may be blocked by a required `strix`
context before the hardened Strix workflow can emit a valid result.

Handling policy:

1. Prefer branch update or rerun first.
2. If the required context cannot be emitted until the PR lands, document the
   stale context and use only a temporary, reversible ruleset adjustment when
   the canonical ruleset owner explicitly authorizes that path. Capture
   equivalent temporary evidence before merge, such as a trusted-base rerun,
   scanner artifact, SARIF output, or manual security review evidence tied to
   the current head SHA.
3. Restore the required context after the hardened workflow emits it
   successfully on the protected branch.
4. Re-run required-check and live-ruleset evidence after restore.

## PR #108/#109 historical evidence

PR #108 and issue #109 record an earlier repository policy in which the expected
approval count was zero while robot-review evidence was handled separately.
That history explains the old guidance but is not current merge authority. The
active organization ruleset now requires one approval, so current delivery must
follow the live ruleset rather than replaying the historical setting.

The durable lesson from #108/#109 still applies: distinguish robot-review
evidence from GitHub approval objects, preserve review-thread resolution, and
handle stale required contexts with explicit evidence and rollback. Never
change the approval count or required workflows merely because an individual PR
is waiting.

## Rollback and recovery

- Do not add bypass actors, disable security checks, dismiss reviews, use admin
  merge, or lower the live approval count for normal delivery.
- Any explicitly authorized temporary required-context change must have captured
  before/after ruleset JSON, owner, expiry, current head SHA, equivalent
  temporary evidence, and a named restore condition.
- Restore required contexts immediately after the repaired workflow emits them.
- If the platform still rejects merge after policy-aligned settings and passing
  checks, record the rejection as an external blocker with the exact command
  output and head SHA.

## Related operations docs

- `docs/operations/release-deployment-architecture.md`
- `docs/operations/open-source-apm.md`
- `docs/operations/email-relay-proxy-boundary.md`
- `docs/operations/postgresql-physical-replication.md`
- `docs/operations/auth-key-management.md`
- `docs/operations/traefik-evaluation.md`
