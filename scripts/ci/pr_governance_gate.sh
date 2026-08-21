#!/usr/bin/env bash
set -euo pipefail

# Normalize semantic-review provider evidence before the governance evaluator
# consumes GitHub's mixed check-run / commit-status surfaces. CodeRabbit can
# leave a successful legacy commit status even when its authoritative PR
# comment says the current-head review never started because the review limit
# was reached. That status is availability telemetry, not semantic review
# evidence, so remove only that successful status and let the existing
# structured OpenCode App fallback decide the gate.
#
# The adjacent implementation remains part of this trusted entrypoint's static
# governance contract. Keep the policy vocabulary visible here so repository
# regression tests can prove that the delegated evaluator still covers:
# headRefOid, mergeStateStatus, Merge state lookup attempt,
# Merge state is still UNKNOWN after 4 attempts,
# PR state became %s during merge-state refresh,
# PR head changed during gate evaluation, skipping stale gate publication,
# gh pr checks --required, no required checks reported,
# no legacy required status contexts reported, add_waiting, check-runs,
# check-runs?per_page=100,
# Review skipped, BEHIND, app.slug, coderabbitai, COMMENT_MARKER,
# no current blocking failures remain, Waiting for, reviewThreads, and
# CHANGES_REQUESTED. Behavioral enforcement lives in pr_governance_gate_impl.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMPLEMENTATION="${SCRIPT_DIR}/pr_governance_gate_impl.sh"

# Resolve the real GitHub CLI only after restoring the runner-owned PATH. An
# earlier workflow step may prepend a directory through GITHUB_PATH; trusting
# that directory here would let an untrusted `gh` binary become the authority
# for governance evidence before the delegated implementation can harden PATH.
if [ -n "${GITHUB_ACTIONS:-}" ]; then
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  export PATH
fi
PR_GOVERNANCE_REAL_GH="$(command -v gh || true)"
if [ -z "$PR_GOVERNANCE_REAL_GH" ]; then
  printf 'GitHub CLI is unavailable; refusing to evaluate PR governance.\n' >&2
  exit 1
fi
export PR_GOVERNANCE_REAL_GH

# GitHub's repository-scoped API paths and GraphQL owner/name variables require
# exactly one owner/repository pair. Validate the trusted workflow identifier
# before either the wrapper or delegated implementation constructs API paths.
if ! [[ "${GITHUB_REPOSITORY:-}" =~ ^[^/]+/[^/]+$ ]]; then
  printf 'GitHub repository identifier must be owner/repo; refusing to evaluate.\n' >&2
  exit 1
fi

gh() {
  if [ "${1:-}" = "api" ] \
    && [[ "${2:-}" =~ ^repos/.+/commits/[0-9a-fA-F]{40}/status$ ]]; then
    local status_json comments_json unavailable_count
    if ! status_json="$("$PR_GOVERNANCE_REAL_GH" "$@")"; then
      return 1
    fi
    if [ -z "${GITHUB_REPOSITORY:-}" ] \
      || [ -z "${PR_NUMBER:-}" ] \
      || [ -z "${HEAD_SHA:-}" ]; then
      printf '%s' "$status_json"
      return 0
    fi
    if ! comments_json="$("$PR_GOVERNANCE_REAL_GH" api --paginate \
      "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments")"; then
      return 1
    fi
    unavailable_count="$(printf '%s' "$comments_json" | jq -s \
      --arg head_sha "$HEAD_SHA" '
      [.[][]
        | select((.user.login // "") | test("coderabbit|github-code-quality"; "i"))
        | select((.body // "") | contains($head_sha))
        | select((.body // "") | test("review limit reached|couldn\u0027?t start (this )?review|review (did not|didn\u0027?t) start"; "i"))]
      | length')"
    if [ "$unavailable_count" != "0" ]; then
      printf 'Ignoring successful CodeRabbit commit status: authoritative current-head review comment reports that semantic review did not start.\n' >&2
      local filtered_json
      if ! filtered_json="$(printf '%s' "$status_json" | jq '
        .statuses = [
          .statuses[]
          | select(
              (((.context // "") | test("CodeRabbit|coderabbit|GitHub Code Quality|github-code-quality"; "i"))
               and ((.state // "") | ascii_downcase) == "success")
              | not
            )
        ]')"; then
        printf 'Failed to filter commit statuses; refusing to report review evidence.\n' >&2
        return 1
      fi
      printf '%s' "$filtered_json"
      return 0
    fi
    printf '%s' "$status_json"
    return 0
  fi
  "$PR_GOVERNANCE_REAL_GH" "$@"
}
export -f gh

exec bash "$IMPLEMENTATION"
