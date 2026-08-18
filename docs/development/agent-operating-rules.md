# Agent operating rules

Internal rules for agents and committers working in this repository. Customer
and operator onboarding lives in the root [`README.md`](../../README.md). Merge
evidence and required-check behavior live in
[`merge-gate-policy.md`](merge-gate-policy.md).

## Writer boundary

- Do not merge. Open or update a pull request; the separate landing path
  performs any allowed merge action after current-head gates pass.
- Do not treat PR review comments as the fix. Change source, tests, or docs.
- Respect other agents' concurrent work. Do not overwrite or dismiss unfamiliar
  changes.
- Keep each PR an atomic, focused change. Do not rewrite the platform plan or
  weaken auth, egress, or tenancy to land a docs or feature slice.
- HMAC fallback sessions are local/control-plane compatibility credentials, not
  authoritative workspace-membership evidence.

## PR stacking and exact-head evidence

- Stack work as sequential atomic PRs. A phase or stacked change ends when it
  is merged; do not proceed on the assumption that an open PR has landed.
- Gate evidence must name the exact current head SHA. Stale-head reviews,
  `github-actions` reviews, and insufficient-probe approvals do not satisfy
  the robot-review path. See [`merge-gate-policy.md`](merge-gate-policy.md).
- Pending or queued required checks, pending CodeRabbit evidence, and a missing
  structured OpenCode fallback approval are wait states, not hard failures.
- PR Governance stays metadata-only: no PR-head checkout, no admin merge, no
  auto-merge, review dismissal, or security-check suppression.

## Phase 10 development rules

- **Stepwise execution**: Each phase requires an atomic PR, GitHub PR Tracking,
  Push, and Robot Review. A phase only ends when merged. Do not proceed without
  merge.
- **TDD + DDD**: Practice TDD, micro TDD, nano TDD, Domain Driven Development,
  and Context Driven Development.
- **API Wiring**: Always work with API wiring completed.
- **Collaboration**: Respect other agents' concurrent work; do not overwrite or
  dismiss unfamiliar changes.
- **Subagent Delegation**: Actively delegate tasks to Subagents.
- **UI/Browser Testing**: Use a real browser for testing (do not rely on
  assumptions).
- **Strict Errors**: Treat `Timeout`, `Fatal`, `Warn`, and `Denied` outputs as
  hard failures.
- **Goal**: Actively manage tasks to ensure open PR counts converge to 0.

## Central review automation

OpenCode Review, Strix Security Scan, and PR Review Merge Scheduler come from
ContextualWisdomLab central required workflows. Do not reintroduce repo-local
copies. Details and the exact-head robot-review contract are in
[`merge-gate-policy.md`](merge-gate-policy.md).
