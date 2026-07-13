#!/usr/bin/env bash
set -euo pipefail

# Inside Actions, ignore PATH entries prepended via GITHUB_PATH by earlier
# steps so gh/jq/coreutils resolve from the runner's system directories only.
if [ -n "${GITHUB_ACTIONS:-}" ]; then
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
fi

COMMENT_MARKER='<!-- pr-governance:metadata-gate -->'
CHECK_NAME='metadata-only gate evaluation'

PR_NUMBER="${DIRECT_PR_NUMBER:-${TARGET_PR_NUMBER:-${WORKFLOW_RUN_PR_NUMBER:-${CHECK_RUN_PR_NUMBER:-}}}}"
if [ -z "$PR_NUMBER" ]; then
  printf 'No pull request number is available for event %s; nothing to evaluate.\n' "${EVENT_NAME:-unknown}"
  exit 0
fi
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  # Do not echo the value: a crafted PR number could smuggle workflow commands
  # into the run log.
  printf 'Pull request number is not a positive integer; refusing to evaluate.\n'
  exit 1
fi

OWNER="${GITHUB_REPOSITORY%/*}"
REPO="${GITHUB_REPOSITORY#*/}"
BLOCKERS=()
WAITING=()
PR_CHECKS_ERROR_FILE="$(mktemp)"
ISSUE_COMMENTS_ERROR_FILE="$(mktemp)"
REVIEW_COMMENTS_ERROR_FILE="$(mktemp)"
RUN_DETAILS_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID:-unknown}"

cleanup_temp_files() {
  rm -f "$PR_CHECKS_ERROR_FILE" "$ISSUE_COMMENTS_ERROR_FILE" "$REVIEW_COMMENTS_ERROR_FILE"
}

trap cleanup_temp_files EXIT

publish_gate_error_check() {
  # Fail closed: replace any previously published gate result so a transient
  # evaluation error cannot leave a stale success pinned to the head.
  [ -n "${HEAD_SHA:-}" ] || return 0
  if [ -z "${CHECK_RUNS:-}" ]; then
    CHECK_RUNS='{"check_runs":[]}'
  fi
  publish_gate_check \
    completed \
    failure \
    'PR governance metadata gate errored' \
    "Gate evaluation failed unexpectedly for PR ${PR_NUMBER}; see the workflow run log." || true
}

trap publish_gate_error_check ERR

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
  # shellcheck disable=SC2016  # Markdown backticks are literal.
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

publish_gate_check() {
  local status="$1"
  local conclusion="$2"
  local title="$3"
  local summary="$4"
  local external_id existing_check existing_check_id existing_check_status

  external_id="pr-governance:${PR_NUMBER}:${HEAD_SHA}"
  existing_check="$(printf '%s' "$CHECK_RUNS" | jq -r \
    --arg name "$CHECK_NAME" \
    --arg external_id "$external_id" '
      [.check_runs[]
        | select(.name == $name)
        | select(.external_id == $external_id)
        | select(.app.slug == "github-actions")]
      | last
      | if . == null then empty else "\(.id) \(.status)" end
    ')"
  existing_check_id="${existing_check%% *}"
  existing_check_status="${existing_check##* }"

  # The check-runs API silently refuses to move a completed check-run back to a
  # non-completed status (PATCH returns 200 but the run stays completed), which
  # leaves a stale failure pinned to the head. Publish non-completed states as a
  # fresh check-run instead; required-check evaluation follows the newest run.
  if [ "$status" != "completed" ] && [ "$existing_check_status" = "completed" ]; then
    existing_check_id=""
  fi

  # shellcheck disable=SC2016  # Markdown backticks are literal.
  printf 'Publishing `%s` as %s on PR head %s.\n' "$CHECK_NAME" "$status" "$HEAD_SHA"
  if [ -n "$existing_check_id" ]; then
    if [ "$status" = "completed" ]; then
      gh api --method PATCH "repos/${GITHUB_REPOSITORY}/check-runs/${existing_check_id}" \
        -f name="$CHECK_NAME" \
        -f status="$status" \
        -f conclusion="$conclusion" \
        -f details_url="$RUN_DETAILS_URL" \
        -f 'output[title]'="$title" \
        -f 'output[summary]'="$summary"
    else
      gh api --method PATCH "repos/${GITHUB_REPOSITORY}/check-runs/${existing_check_id}" \
        -f name="$CHECK_NAME" \
        -f status="$status" \
        -f details_url="$RUN_DETAILS_URL" \
        -f 'output[title]'="$title" \
        -f 'output[summary]'="$summary"
    fi
    return
  fi

  if [ "$status" = "completed" ]; then
    gh api --method POST "repos/${GITHUB_REPOSITORY}/check-runs" \
      -f name="$CHECK_NAME" \
      -f head_sha="$HEAD_SHA" \
      -f status="$status" \
      -f conclusion="$conclusion" \
      -f external_id="$external_id" \
      -f details_url="$RUN_DETAILS_URL" \
      -f 'output[title]'="$title" \
      -f 'output[summary]'="$summary"
  else
    gh api --method POST "repos/${GITHUB_REPOSITORY}/check-runs" \
      -f name="$CHECK_NAME" \
      -f head_sha="$HEAD_SHA" \
      -f status="$status" \
      -f external_id="$external_id" \
      -f details_url="$RUN_DETAILS_URL" \
      -f 'output[title]'="$title" \
      -f 'output[summary]'="$summary"
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

# shellcheck disable=SC2016  # GraphQL variables must remain literal.
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
  PR_CHECKS_ERROR="$(<"$PR_CHECKS_ERROR_FILE")"
  if printf '%s' "$PR_CHECKS_ERROR" | grep -qi 'no required checks reported'; then
    add_waiting "Ruleset-governed branch: no legacy required status contexts reported for ${HEAD_REF_OID}; relying on ruleset workflows and code-scanning gates."
  else
    # Raw CLI diagnostics stay in the run log (indented so they cannot be
    # parsed as workflow commands); the published blocker stays generic.
    printf 'gh pr checks failed:\n'
    printf '%s\n' "$PR_CHECKS_ERROR" | sed 's/^/    /'
    add_blocker 'Required check metadata could not be read; see the workflow run log.'
  fi
else
  # Fail closed: any state outside the explicit pass and pending lists is a
  # blocker, so unrecognized or errored states cannot slip through as success.
  while IFS= read -r item; do
    [ -n "$item" ] && add_blocker "$item"
  done < <(printf '%s' "$REQUIRED_CHECKS" | jq -r --arg check_name "$CHECK_NAME" '
    .[]
    | select(.name != $check_name)
    | (.state | ascii_upcase) as $state
    | select(["SUCCESS", "PASS", "SKIPPED", "NEUTRAL"] | index($state) | not)
    | select(["PENDING", "QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING", "EXPECTED"] | index($state) | not)
    | "Required check `\(.name | gsub("[`\\r\\n]"; " "))` is \($state) on the current head."
  ')

  PENDING_REQUIRED_COUNT="$(printf '%s' "$REQUIRED_CHECKS" | jq --arg check_name "$CHECK_NAME" '[.[] | select(.name != $check_name) | select((.state | ascii_upcase) as $state | ["PENDING", "QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING", "EXPECTED"] | index($state))] | length')"
  if [ "$PENDING_REQUIRED_COUNT" != "0" ]; then
    add_waiting "Waiting for ${PENDING_REQUIRED_COUNT} required check(s) to finish on ${HEAD_REF_OID}."
  fi
fi

CODERABBIT_BLOCKING_PATTERN='pre[- ]merge|blocking|failure|failed|warning|potential issue|actionable comment|actionable comments'
CHECK_RUNS="$(gh api "repos/${GITHUB_REPOSITORY}/commits/${HEAD_SHA}/check-runs?per_page=100")"
CODERABBIT_MATCHES="$(printf '%s' "$CHECK_RUNS" | jq '
  [.check_runs[]
    | select(.app.slug == "coderabbitai" or (.name | test("CodeRabbit|coderabbit"; "i")))]'
)"
CODERABBIT_COUNT="$(printf '%s' "$CODERABBIT_MATCHES" | jq 'length')"
if [ "$CODERABBIT_COUNT" = "0" ]; then
  # The CodeRabbit app is not installed in this org, so absent evidence must not
  # hold the gate open; CodeRabbit gating applies only once it reports on this head.
  printf 'No CodeRabbit evidence on %s; skipping CodeRabbit gating.\n' "$HEAD_REF_OID"
else
  CODERABBIT_PENDING="$(printf '%s' "$CODERABBIT_MATCHES" | jq '[.[] | select(.status != "completed")] | length')"
  CODERABBIT_FAILED="$(printf '%s' "$CODERABBIT_MATCHES" | jq --arg pattern "$CODERABBIT_BLOCKING_PATTERN" '
    [.[]
      | select(.status == "completed")
      | select((.conclusion // "") as $conclusion
        | if $conclusion == "success" or $conclusion == "skipped" then false
          elif $conclusion == "neutral" then
            # Skip evidence only counts when the output carries no blocking
            # language alongside it.
            (([.output.title, .output.summary, .output.text] | map(. // "") | join("\n")) as $neutral_output
              | (($neutral_output | test("Review skipped"; "i"))
                 and (($neutral_output | test($pattern; "i")) | not))
              | not)
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

if ! ISSUE_COMMENTS_JSON="$(gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" 2>"$ISSUE_COMMENTS_ERROR_FILE")"; then
  printf 'issue comment lookup failed:\n'
  printf '%s\n' "$(<"$ISSUE_COMMENTS_ERROR_FILE")" | sed 's/^/    /'
  add_blocker 'PR issue comments could not be read; see the workflow run log.'
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
  printf 'review comment lookup failed:\n'
  printf '%s\n' "$(<"$REVIEW_COMMENTS_ERROR_FILE")" | sed 's/^/    /'
  add_blocker 'PR review comments could not be read; see the workflow run log.'
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
  BLOCKER_SUMMARY="$(join_items "${BLOCKERS[@]}")"
  printf 'PR governance blockers for %s on %s:\n%s\n' "$PR_NUMBER" "$HEAD_REF_OID" "$BLOCKER_SUMMARY"
  post_or_update_blocker_comment "$HEAD_REF_OID"
  publish_gate_check \
    completed \
    failure \
    'PR governance metadata gate blocked' \
    "$BLOCKER_SUMMARY"
  exit 0
fi

if [ "${#WAITING[@]}" -gt 0 ]; then
  WAITING_SUMMARY="$(join_items "${WAITING[@]}")"
  printf '%s\n' "$WAITING_SUMMARY"
  publish_gate_check \
    in_progress \
    '' \
    'PR governance metadata gate is waiting' \
    "$WAITING_SUMMARY"
  exit 0
fi

# shellcheck disable=SC2016  # Markdown backticks are literal.
printf 'PR governance metadata gate is ready for `%s` on `%s`.\n' "$PR_NUMBER" "$HEAD_REF_OID"
publish_gate_check \
  completed \
  success \
  'PR governance metadata gate is ready' \
  "All current-head governance requirements passed for PR ${PR_NUMBER} on ${HEAD_REF_OID}."
