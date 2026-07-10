#!/usr/bin/env bash
set -euo pipefail

COMMENT_MARKER='<!-- pr-governance:metadata-gate -->'

PR_NUMBER="${DIRECT_PR_NUMBER:-${TARGET_PR_NUMBER:-${WORKFLOW_RUN_PR_NUMBER:-${CHECK_RUN_PR_NUMBER:-}}}}"
if [ -z "$PR_NUMBER" ]; then
  printf 'No pull request number is available for event %s; nothing to evaluate.\n' "${EVENT_NAME:-unknown}"
  exit 0
fi

OWNER="${GITHUB_REPOSITORY%/*}"
REPO="${GITHUB_REPOSITORY#*/}"
BLOCKERS=()
WAITING=()
PR_CHECKS_ERROR_FILE="$(mktemp)"
ISSUE_COMMENTS_ERROR_FILE="$(mktemp)"
REVIEW_COMMENTS_ERROR_FILE="$(mktemp)"

cleanup_temp_files() {
  rm -f "$PR_CHECKS_ERROR_FILE" "$ISSUE_COMMENTS_ERROR_FILE" "$REVIEW_COMMENTS_ERROR_FILE"
}

trap cleanup_temp_files EXIT

add_blocker() {
  BLOCKERS+=("$1")
}

add_waiting() {
  WAITING+=("$1")
}

join_items() {
  local item
  for item in "$@"; do
    printf -- '- %s\n' "$item"
  done
}

post_or_update_blocker_comment() {
  local head_ref_oid="$1"
  local body existing_comment_id
  body="$(printf '%s\nPR governance metadata gate is not ready for `%s`:\n\n%s' \
    "$COMMENT_MARKER" \
    "$head_ref_oid" \
    "$(join_items "${BLOCKERS[@]}")")"

  existing_comment_id="$(gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" \
    --jq ".[] | select(.body | contains(\"${COMMENT_MARKER}\")) | .id" \
    | tail -n 1 || true)"

  if [ -n "$existing_comment_id" ]; then
    gh api --method PATCH "repos/${GITHUB_REPOSITORY}/issues/comments/${existing_comment_id}" -f body="$body"
  else
    gh api "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" -f body="$body"
  fi
}

PR_JSON="$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --json number,isDraft,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup)"
HEAD_SHA="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}" --jq '.head.sha')"
HEAD_REF_OID="$HEAD_SHA" # headRefOid equivalent for REST metadata paths.
MERGE_STATE="$(printf '%s' "$PR_JSON" | jq -r '.mergeStateStatus')"
IS_DRAFT="$(printf '%s' "$PR_JSON" | jq -r '.isDraft')"
REVIEW_DECISION="$(printf '%s' "$PR_JSON" | jq -r '.reviewDecision // ""')"

if [ "$IS_DRAFT" = "true" ]; then
  add_blocker 'Draft PR: merge automation is paused.'
fi

if [ "$MERGE_STATE" = "BEHIND" ]; then
  add_blocker 'Branch is BEHIND the base branch; update the branch and re-run checks.'
fi

if [ "$MERGE_STATE" = "DIRTY" ] || [ "$MERGE_STATE" = "UNKNOWN" ]; then
  add_blocker "Merge state is ${MERGE_STATE}; resolve conflicts or refresh mergeability."
fi

if [ "$REVIEW_DECISION" = "CHANGES_REQUESTED" ]; then
  add_blocker 'Review decision is CHANGES_REQUESTED; address requested changes before merge.'
fi

THREADS_JSON="$(gh api graphql \
  -F owner="$OWNER" \
  -F repo="$REPO" \
  -F number="$PR_NUMBER" \
  -f query='query($owner:String!, $repo:String!, $number:Int!) { repository(owner:$owner, name:$repo) { pullRequest(number:$number) { headRefOid mergeStateStatus reviewThreads(first:100) { nodes { id isResolved isOutdated } } } } }')"
UNRESOLVED_THREADS="$(printf '%s' "$THREADS_JSON" | jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false and .isOutdated == false)] | length')"
if [ "$UNRESOLVED_THREADS" != "0" ]; then
  add_blocker "${UNRESOLVED_THREADS} unresolved current review thread(s) remain."
fi

if ! REQUIRED_CHECKS="$(gh pr checks "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --required --json name,state,link 2>"$PR_CHECKS_ERROR_FILE")"; then
  add_blocker "Required check metadata could not be read: $(<"$PR_CHECKS_ERROR_FILE")."
else
  while IFS= read -r item; do
    [ -n "$item" ] && add_blocker "$item"
  done < <(printf '%s' "$REQUIRED_CHECKS" | jq -r '
    .[]
    | select((.state | ascii_upcase) as $state | ["FAILED", "FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"] | index($state))
    | "Required check `\(.name)` is \(.state) on the current head: \(.link // "no link")"
  ')

  PENDING_REQUIRED_COUNT="$(printf '%s' "$REQUIRED_CHECKS" | jq '[.[] | select((.state | ascii_upcase) as $state | ["PENDING", "QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING", "EXPECTED"] | index($state))] | length')"
  if [ "$PENDING_REQUIRED_COUNT" != "0" ]; then
    add_waiting "Waiting for ${PENDING_REQUIRED_COUNT} required check(s) to finish on ${HEAD_REF_OID}."
  fi
fi

CHECK_RUNS="$(gh api "repos/${GITHUB_REPOSITORY}/commits/${HEAD_SHA}/check-runs")"
CODERABBIT_MATCHES="$(printf '%s' "$CHECK_RUNS" | jq '
  [.check_runs[]
    | select(.app.slug == "coderabbitai" or (.name | test("CodeRabbit|coderabbit"; "i")))]'
)"
CODERABBIT_COUNT="$(printf '%s' "$CODERABBIT_MATCHES" | jq 'length')"
if [ "$CODERABBIT_COUNT" = "0" ]; then
  add_waiting "Waiting for current-head CodeRabbit evidence on ${HEAD_REF_OID}."
else
  CODERABBIT_PENDING="$(printf '%s' "$CODERABBIT_MATCHES" | jq '[.[] | select(.status != "completed")] | length')"
  CODERABBIT_FAILED="$(printf '%s' "$CODERABBIT_MATCHES" | jq '
    [.[]
      | select(.status == "completed")
      | select((.conclusion // "") as $conclusion
        | if $conclusion == "success" or $conclusion == "skipped" then false
          elif $conclusion == "neutral" then
            ([.output.title, .output.summary, .output.text] | map(. // "") | join("\n") | test("Review skipped"; "i") | not)
          else true
          end)]
    | length'
  )"
  if [ "$CODERABBIT_FAILED" != "0" ]; then
    add_blocker "Current-head CodeRabbit check has a blocking conclusion on ${HEAD_REF_OID}."
  elif [ "$CODERABBIT_PENDING" != "0" ]; then
    add_waiting "Waiting for current-head CodeRabbit evidence on ${HEAD_REF_OID}."
  fi
fi

CODERABBIT_BLOCKING_PATTERN='pre[- ]merge|blocking|failure|failed|warning|potential issue|actionable comment|actionable comments'
if ! ISSUE_COMMENTS_JSON="$(gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" 2>"$ISSUE_COMMENTS_ERROR_FILE")"; then
  add_blocker "CodeRabbit issue comments could not be read: $(<"$ISSUE_COMMENTS_ERROR_FILE")."
else
  CODERABBIT_ISSUE_BLOCKERS="$(printf '%s' "$ISSUE_COMMENTS_JSON" | jq -s --arg head_sha "$HEAD_SHA" --arg pattern "$CODERABBIT_BLOCKING_PATTERN" '
    [.[][]
      | select((.user.login // "") | test("coderabbit"; "i"))
      | select((.body // "") | test($pattern; "i"))
      | select((.body // "") | contains($head_sha))]
    | length'
  )"
  if [ "$CODERABBIT_ISSUE_BLOCKERS" != "0" ]; then
    add_blocker "Current-head CodeRabbit issue comment has blocking warning/failure evidence on ${HEAD_REF_OID}."
  fi
fi

if ! REVIEW_COMMENTS_JSON="$(gh api --paginate "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments" 2>"$REVIEW_COMMENTS_ERROR_FILE")"; then
  add_blocker "CodeRabbit review comments could not be read: $(<"$REVIEW_COMMENTS_ERROR_FILE")."
else
  CODERABBIT_REVIEW_BLOCKERS="$(printf '%s' "$REVIEW_COMMENTS_JSON" | jq -s --arg head_sha "$HEAD_SHA" --arg pattern "$CODERABBIT_BLOCKING_PATTERN" '
    [.[][]
      | select((.user.login // "") | test("coderabbit"; "i"))
      | select((.body // "") | test($pattern; "i"))
      | select(((.commit_id // "") == $head_sha) or ((.original_commit_id // "") == $head_sha) or ((.body // "") | contains($head_sha)))]
    | length'
  )"
  if [ "$CODERABBIT_REVIEW_BLOCKERS" != "0" ]; then
    add_blocker "Current-head CodeRabbit review comment has blocking warning/failure evidence on ${HEAD_REF_OID}."
  fi
fi

if [ "${#BLOCKERS[@]}" -gt 0 ]; then
  post_or_update_blocker_comment "$HEAD_REF_OID"
  exit 1
fi

if [ "${#WAITING[@]}" -gt 0 ]; then
  join_items "${WAITING[@]}"
  exit 0
fi

printf 'PR governance metadata gate is ready for `%s` on `%s`.\n' "$PR_NUMBER" "$HEAD_REF_OID"
