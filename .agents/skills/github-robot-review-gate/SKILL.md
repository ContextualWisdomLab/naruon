---
name: github-robot-review-gate
description: >-
  Use when GitHub PR merge gates, CodeRabbit robot-review policy, required
  review settings, stale status contexts, or temporary required-check rollbacks
  are blocking or being misdiagnosed.
---

# GitHub Robot Review Gate

## Core rule

Diagnose the exact merge blocker from the live protected branch, rulesets, PR
head, review state, threads, and check runs before changing code or repository
settings. CodeRabbit/check-run success can satisfy this repository's
robot-review evidence path only when current-head blocking findings, warnings,
and failures are fixed, rebutted with evidence, or superseded. Robot-review
evidence does not replace a live GitHub approval-count rule unless the evidence
is itself a qualifying `APPROVED` review object.

The active organization ruleset currently requires one qualifying independent
approval (`required_approving_review_count=1`) and review-thread resolution. Do
not lower that count, add a bypass, dismiss a review, or reinterpret a status or
check as an approval merely to land a PR. If the canonical organization owner
later changes the rule, refetch the live ruleset first and update this skill and
the merge-gate policy from that evidence.

## Root-cause-first workflow

1. Capture the PR head SHA, base tip, mergeability, review decision, submitted
   reviews, unresolved threads, required checks, and active rulesets.
2. Separate four signals: GitHub approval state, robot-review evidence,
   required status/workflow contexts, and ruleset settings.
3. Identify the narrow blocker: missing current-head robot evidence, unresolved
   robot findings, missing qualifying independent approval, unresolved threads,
   stale status context, queued runner acquisition, or a failing check.
4. Apply only a causal fix inside the correct ownership boundary. Do not mutate
   a clean source head just to retrigger infrastructure and do not change the
   approval count or bypass policy for an individual PR.
5. Re-capture the same evidence on the exact current head before any lifecycle
   action. Predecessor reviews/checks do not transfer after a head movement.

## Evidence commands

```bash
gh pr view <pr> \
  --json number,headRefOid,baseRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,latestReviews
gh pr checks <pr> --required
gh api repos/<owner>/<repo>/pulls/<pr>/reviews
gh api repos/<owner>/<repo>/commits/<sha>/status
gh api repos/<owner>/<repo>/commits/<sha>/check-runs
gh api repos/<owner>/<repo>/rulesets \
  --jq '.[] | {id, name, enforcement, conditions, rules}'
```

Record the current head SHA with every review, thread, check, screenshot, and
ruleset summary so stale evidence is not mistaken for current-head evidence.

## Guardrails

- Do not bypass branch protection, add bypass actors, use admin merge, force
  push, destructively rebase, self-approve, dismiss reviews, or disable security
  checks for routine delivery.
- Do not lower `required_approving_review_count=1` to unblock a PR.
- Do not treat `Review skipped`, CodeRabbit walkthroughs, overview comments, or
  check-run success as a GitHub `APPROVED` review object.
- Keep `required_review_thread_resolution=true`.
- A qualifying independent approval is still required while the live ruleset
  requires it, even when current-head robot evidence is otherwise satisfactory.
- Pending, queued, requested, waiting, in-progress, absent-required, cancelled,
  failed, stale-head, and predecessor evidence is not permission to merge.

## Stale required status contexts

If a PR that hardens or restores a workflow is blocked by a stale required
context, prefer rerunning or updating the branch when that preserves exact-head
semantics. If the context cannot be emitted until the repair lands, document the
causal cycle and advance the canonical workflow/ruleset owner path instead of
silently weakening Naruon's gate.

A temporary required-context adjustment is exceptional. Use it only when the
canonical ruleset owner explicitly authorizes it and equivalent current-head
evidence is captured. Record before/after ruleset JSON, owner, expiry, current
head SHA, equivalent scanner/test evidence, and a named restore condition. The
approval-count rule is not a stale status context and must not be lowered by
this procedure.

## Common mistakes

- Equating CodeRabbit or OpenCode status/check evidence with a GitHub approval:
  inspect the submitted review object and live approval rule separately.
- Following historical `required_approving_review_count=0` guidance after the
  organization ruleset changed: live ruleset evidence wins; update stale docs
  instead of weakening the rule.
- Treating a queued hosted runner as a product defect: distinguish runner
  acquisition/startup failure from executed test failure and advance the
  canonical CI owner path while other safe Naruon lanes continue.
- Removing a required scanner permanently to unblock its own repair: preserve
  the dependency and use only an owner-authorized, evidenced, reversible
  recovery path when a true bootstrap cycle is proven.
- Disabling scanners or dismissing reviews to merge faster: fix the underlying
  gate, workflow, source, or ownership-path defect instead.
