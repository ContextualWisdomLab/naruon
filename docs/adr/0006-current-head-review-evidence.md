# ADR-0006: Let exact-head robot evidence supersede stale aggregate review state

- Status: Accepted
- Date: 2026-08-20
- Decision owners: Naruon maintainers

## Context

GitHub exposes `reviewDecision=CHANGES_REQUESTED` as an aggregate pull-request
field. The field can remain `CHANGES_REQUESTED` after the requesting review was
submitted against an older commit and a later exact-head CodeRabbit or
structured OpenCode review has passed. Treating that stale aggregate as a
current blocker stranded protected merges even when current review threads and
required checks were clean.

The GitHub REST review response includes each review's `state` and `commit_id`,
so the gate can distinguish a current request from a request attached to an
older head (GitHub, 2026).

## Decision

The metadata-only gate will:

1. Read all pull-request review metadata when the aggregate decision is
   `CHANGES_REQUESTED`.
2. Keep the blocker when any `CHANGES_REQUESTED` review targets the current
   head, when review metadata cannot be read, or when current-head robot review
   evidence is absent or pending.
3. Treat the aggregate decision as superseded only when all requested reviews
   target older commits and current-head CodeRabbit or structured OpenCode
   evidence passes.
4. Never dismiss reviews, rewrite review state, use an administrator merge, or
   bypass required checks.

## Consequences

Protected merges can proceed after a later exact-head review supersedes stale
aggregate state. A current requested change remains a hard blocker, and an API
failure fails closed. The gate performs an additional read-only reviews API
call only for pull requests whose aggregate decision is `CHANGES_REQUESTED`;
the CodeRabbit-absent path may already have read the same endpoint while
checking for structured OpenCode approval.

## Verification

`bash scripts/ci/test_pr_governance_gate.sh` proves both stale-review
supersession and blocking of current-head requested changes.

## Reference

GitHub. (2026). *REST API endpoints for pull request reviews*. GitHub Docs.
https://docs.github.com/en/rest/pulls/reviews?apiVersion=2022-11-28
