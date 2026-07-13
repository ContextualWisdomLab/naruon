#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="$repo_root/scripts/ci/pr_governance_gate.sh"

make_fake_gh() {
  local bin_dir="$1"
  cat > "$bin_dir/gh" <<'FAKEGH'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" >> "$GH_LOG"

head_sha="0123456789abcdef0123456789abcdef01234567"
args="$*"

if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  case "${GH_SCENARIO:-pass}" in
    changes_requested)
      printf '{"number":42,"isDraft":false,"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","reviewDecision":"CHANGES_REQUESTED","statusCheckRollup":[]}'
      ;;
    *)
      printf '{"number":42,"isDraft":false,"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","reviewDecision":"","statusCheckRollup":[]}'
      ;;
  esac
  exit 0
fi

if [ "$1" = "api" ] && [[ "$2" == repos/*/pulls/42 ]]; then
  if [[ "$args" == *".base.sha"* ]]; then
    printf 'abcdefabcdefabcdefabcdefabcdefabcdefabcd'
  else
    printf '%s' "$head_sha"
  fi
  exit 0
fi

if [ "$1" = "api" ] && [[ "$2" == repos/*/commits/* ]] && [[ "$2" != */check-runs* ]]; then
  printf '2026-05-19T00:00:00Z'
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "graphql" ]; then
  printf '{"data":{"repository":{"pullRequest":{"headRefOid":"%s","mergeStateStatus":"CLEAN","reviewThreads":{"nodes":[]}}}}}' "$head_sha"
  exit 0
fi

if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then
  if [ "${GH_SCENARIO:-pass}" = "no_required_checks" ]; then
    printf 'no required checks reported on the test branch\n' >&2
    exit 1
  fi
  case "${GH_SCENARIO:-pass}" in
    pending)
      printf '[{"name":"Application CI","state":"IN_PROGRESS","link":"https://checks/app-ci"}]'
      ;;
    startup_failure)
      printf '[{"name":"Application CI","state":"STARTUP_FAILURE","link":"https://checks/app-ci"}]'
      ;;
    failed)
      printf '[{"name":"Application CI","state":"FAILED","link":"https://checks/app-ci"}]'
      ;;
    failure|failed_existing)
      printf '[{"name":"Application CI","state":"FAILURE","link":"https://checks/app-ci"}]'
      ;;
    self_gate_failed)
      printf '[{"name":"metadata-only gate evaluation","state":"FAILURE","link":"https://checks/governance"},{"name":"Application CI","state":"SUCCESS","link":"https://checks/app-ci"}]'
      ;;
    *)
      printf '[{"name":"Application CI","state":"SUCCESS","link":"https://checks/app-ci"}]'
      ;;
  esac
  exit 0
fi

if [ "$1" = "api" ] && [[ "$2" == repos/*/commits/*/check-runs* ]]; then
  case "${GH_SCENARIO:-pass}" in
    coderabbit_pending)
      printf '{"check_runs":[{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"in_progress","conclusion":null,"html_url":"https://checks/coderabbit"}]}'
      ;;
    missing_coderabbit)
      printf '{"check_runs":[]}'
      ;;
    coderabbit_failed)
      printf '{"check_runs":[{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"completed","conclusion":"failure","html_url":"https://checks/coderabbit"}]}'
      ;;
    coderabbit_neutral)
      printf '{"check_runs":[{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"completed","conclusion":"neutral","output":{"title":"CodeRabbit","summary":"Review completed","text":"No skip evidence"},"html_url":"https://checks/coderabbit"}]}'
      ;;
    coderabbit_review_skipped)
      printf '{"check_runs":[{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"completed","conclusion":"neutral","output":{"title":"CodeRabbit","summary":"Review skipped","text":"Review skipped"},"html_url":"https://checks/coderabbit"}]}'
      ;;
    existing_gate)
      printf '{"check_runs":[{"id":999,"name":"metadata-only gate evaluation","external_id":"pr-governance:42:0123456789abcdef0123456789abcdef01234567","app":{"slug":"github-actions"},"status":"completed","conclusion":"failure"},{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"completed","conclusion":"success","html_url":"https://checks/coderabbit"}]}'
      ;;
    *)
      printf '{"check_runs":[{"name":"CodeRabbit","app":{"slug":"coderabbitai"},"status":"completed","conclusion":"success","html_url":"https://checks/coderabbit"}]}'
      ;;
  esac
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "--method" ] && [ "$3" = "POST" ] && [[ "$4" == repos/*/check-runs ]]; then
  if [ "${GH_SCENARIO:-pass}" = "check_publish_failure" ]; then
    printf 'check publication failed\n' >&2
    exit 1
  fi
  printf '{"id":999}'
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "--method" ] && [ "$3" = "PATCH" ] && [[ "$4" == repos/*/check-runs/* ]]; then
  printf '{"id":999}'
  exit 0
fi

if [ "$1" = "api" ] && [[ "$args" == *repos/*/issues/42/comments* ]]; then
  if [[ "$args" == *"--jq"* ]]; then
    if [ "${GH_SCENARIO:-pass}" = "failed_existing" ]; then
      printf '555\n'
    fi
    exit 0
  fi
  if [[ "$args" == *"--paginate"* ]]; then
    case "${GH_SCENARIO:-pass}" in
      coderabbit_blocking_comment)
        printf '[{"id":777,"user":{"login":"coderabbitai[bot]"},"created_at":"2026-05-19T00:01:00Z","body":"Pre-merge warning for 0123456789abcdef0123456789abcdef01234567"}]'
        ;;
      coderabbit_stale_blocking_comment)
        printf '[{"id":777,"user":{"login":"coderabbitai[bot]"},"created_at":"2026-05-19T00:01:00Z","body":"Pre-merge warning for older head"}]'
        ;;
      *)
        printf '[]'
        ;;
    esac
    exit 0
  fi
  printf 'posted\n'
  exit 0
fi

if [ "$1" = "api" ] && [[ "$args" == *repos/*/pulls/42/comments* ]]; then
  case "${GH_SCENARIO:-pass}" in
    coderabbit_current_review_comment)
      printf '[{"id":888,"user":{"login":"coderabbitai[bot]"},"commit_id":"0123456789abcdef0123456789abcdef01234567","original_commit_id":"old","created_at":"2026-05-19T00:01:00Z","body":"Potential issue on current head"}]'
      ;;
    coderabbit_stale_review_comment)
      printf '[{"id":888,"user":{"login":"coderabbitai[bot]"},"commit_id":"old","original_commit_id":"old","created_at":"2026-05-19T00:01:00Z","body":"Potential issue on stale head"}]'
      ;;
    *)
      printf '[]'
      ;;
  esac
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "--method" ] && [ "$3" = "PATCH" ] && [[ "$4" == repos/*/issues/comments/555 ]]; then
  printf 'patched\n'
  exit 0
fi

if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
  printf 'merge requested\n'
  exit 0
fi

printf 'unexpected gh invocation: %s\n' "$*" >&2
exit 99
FAKEGH
  chmod +x "$bin_dir/gh"
}

run_gate() {
  local scenario="$1"
  local temp_dir="$2"
  mkdir -p "$temp_dir/bin"
  make_fake_gh "$temp_dir/bin"
  set +e
  GH_LOG="$temp_dir/gh.log" \
  GH_SCENARIO="$scenario" \
  PATH="$temp_dir/bin:$PATH" \
  GITHUB_REPOSITORY="owner/repo" \
  GH_TOKEN="fake" \
  EVENT_NAME="pull_request_target" \
  TARGET_PR_NUMBER="42" \
  DIRECT_PR_NUMBER="" \
  WORKFLOW_RUN_PR_NUMBER="" \
    bash "$script" > "$temp_dir/output.txt" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" > "$temp_dir/status.txt"
}

assert_in_file() {
  local pattern="$1"
  local file="$2"
  grep -q -- "$pattern" "$file"
}

assert_not_in_file() {
  local pattern="$1"
  local file="$2"
  if grep -q -- "$pattern" "$file"; then
    printf 'unexpected pattern found in %s: %s\n' "$file" "$pattern" >&2
    printf '%s\n' '--- file contents ---' >&2
    sed -n '1,200p' "$file" >&2
    return 1
  fi
}

assert_exit_code() {
  local expected="$1"
  local temp_dir="$2"
  local actual
  actual="$(<"$temp_dir/status.txt")"
  if [ "$actual" != "$expected" ]; then
    printf 'expected exit code %s, got %s\n' "$expected" "$actual" >&2
    printf '%s\n' '--- output ---' >&2
    sed -n '1,200p' "$temp_dir/output.txt" >&2
    printf '%s\n' '--- gh log ---' >&2
    sed -n '1,200p' "$temp_dir/gh.log" >&2
    return 1
  fi
}

assert_no_comment_or_merge_for_pending_checks() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate pending "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Waiting for 1 required check' "$temp_dir/output.txt"
  assert_in_file 'head_sha=0123456789abcdef0123456789abcdef01234567 -f status=in_progress' "$temp_dir/gh.log"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_startup_failure_creates_marker_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate startup_failure "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file "Required check \`Application CI\` is STARTUP_FAILURE" "$temp_dir/gh.log"
  assert_in_file '<!-- pr-governance:metadata-gate -->' "$temp_dir/gh.log"
  assert_in_file 'head_sha=0123456789abcdef0123456789abcdef01234567 -f status=completed -f conclusion=failure' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_failed_checks_create_marker_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate failed "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is not ready' "$temp_dir/gh.log"
  assert_in_file '<!-- pr-governance:metadata-gate -->' "$temp_dir/gh.log"
  assert_in_file 'Application CI' "$temp_dir/gh.log"
  assert_in_file 'head_sha=0123456789abcdef0123456789abcdef01234567 -f status=completed -f conclusion=failure' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_existing_marker_comment_is_patched() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate failed_existing "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'api --method PATCH repos/owner/repo/issues/comments/555' "$temp_dir/gh.log"
  assert_not_in_file 'repos/owner/repo/issues/42/comments -f body' "$temp_dir/gh.log"
}

assert_coderabbit_pending_waits_without_hard_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_pending "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Waiting for current-head CodeRabbit evidence' "$temp_dir/output.txt"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_missing_coderabbit_waits_without_hard_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate missing_coderabbit "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Waiting for current-head CodeRabbit evidence' "$temp_dir/output.txt"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_failure_creates_marker_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_failed "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Current-head CodeRabbit check has a blocking conclusion' "$temp_dir/gh.log"
  assert_in_file '<!-- pr-governance:metadata-gate -->' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_neutral_without_skip_evidence_blocks() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_neutral "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Current-head CodeRabbit check has a blocking conclusion' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_review_skipped_neutral_is_ready_without_merge() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_review_skipped "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is ready' "$temp_dir/output.txt"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
}

assert_coderabbit_blocking_issue_comment_blocks() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_blocking_comment "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Current-head CodeRabbit issue comment has blocking warning/failure evidence' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_stale_issue_comment_does_not_block() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_stale_blocking_comment "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is ready' "$temp_dir/output.txt"
  assert_not_in_file 'Current-head CodeRabbit issue comment' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_current_review_comment_blocks() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_current_review_comment "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Current-head CodeRabbit review comment has blocking warning/failure evidence' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_coderabbit_stale_review_comment_does_not_block() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate coderabbit_stale_review_comment "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is ready' "$temp_dir/output.txt"
  assert_not_in_file 'Current-head CodeRabbit review comment' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_changes_requested_creates_marker_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate changes_requested "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'Review decision is CHANGES_REQUESTED' "$temp_dir/gh.log"
  assert_in_file '<!-- pr-governance:metadata-gate -->' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_passing_gate_is_metadata_only_without_merge() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate pass "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is ready' "$temp_dir/output.txt"
  assert_in_file 'head_sha=0123456789abcdef0123456789abcdef01234567 -f status=completed -f conclusion=success' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
  assert_not_in_file 'checkout' "$temp_dir/gh.log"
  assert_not_in_file 'dismiss' "$temp_dir/gh.log"
  assert_not_in_file 'continue-on-error' "$temp_dir/gh.log"
}

assert_no_required_checks_waits_without_hard_comment() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate no_required_checks "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'no legacy required status contexts reported' "$temp_dir/output.txt"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_self_gate_failure_does_not_recurse() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate self_gate_failed "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'PR governance metadata gate is ready' "$temp_dir/output.txt"
  assert_not_in_file "Required check \`metadata-only gate evaluation\`" "$temp_dir/output.txt"
  assert_not_in_file 'issues/42/comments -f body' "$temp_dir/gh.log"
  assert_in_file 'conclusion=success' "$temp_dir/gh.log"
}

assert_existing_pr_head_check_is_updated() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate existing_gate "$temp_dir"

  assert_exit_code 0 "$temp_dir"
  assert_in_file 'api --method PATCH repos/owner/repo/check-runs/999' "$temp_dir/gh.log"
  assert_not_in_file 'api --method POST repos/owner/repo/check-runs' "$temp_dir/gh.log"
}

assert_check_publication_failure_fails_closed() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  run_gate check_publish_failure "$temp_dir"

  assert_exit_code 1 "$temp_dir"
  assert_in_file 'check publication failed' "$temp_dir/output.txt"
  assert_not_in_file '^pr merge' "$temp_dir/gh.log"
}

assert_workflow_separates_controller_from_required_check() {
  local workflow="$repo_root/.github/workflows/pr-governance.yml"

	assert_in_file '^  checks: read$' "$workflow"
	assert_in_file '^      checks: write$' "$workflow"
	assert_in_file '^  pull-requests: read$' "$workflow"
	assert_in_file '^      pull-requests: write$' "$workflow"
	assert_in_file '^  issues: read$' "$workflow"
	assert_in_file '^      issues: write$' "$workflow"
  assert_in_file '^    name: PR governance metadata controller$' "$workflow"
  assert_not_in_file '^    name: metadata-only gate evaluation$' "$workflow"
}

assert_current_head_check_lookup_uses_maximum_page_size() {
  assert_in_file 'check-runs?per_page=100' "$repo_root/scripts/ci/pr_governance_gate.sh"
}

assert_no_comment_or_merge_for_pending_checks
assert_startup_failure_creates_marker_comment
assert_failed_checks_create_marker_comment
assert_existing_marker_comment_is_patched
assert_coderabbit_pending_waits_without_hard_comment
assert_missing_coderabbit_waits_without_hard_comment
assert_coderabbit_failure_creates_marker_comment
assert_coderabbit_neutral_without_skip_evidence_blocks
assert_coderabbit_review_skipped_neutral_is_ready_without_merge
assert_coderabbit_blocking_issue_comment_blocks
assert_coderabbit_stale_issue_comment_does_not_block
assert_coderabbit_current_review_comment_blocks
assert_coderabbit_stale_review_comment_does_not_block
assert_changes_requested_creates_marker_comment
assert_passing_gate_is_metadata_only_without_merge
assert_no_required_checks_waits_without_hard_comment
assert_self_gate_failure_does_not_recurse
assert_existing_pr_head_check_is_updated
assert_check_publication_failure_fails_closed
assert_workflow_separates_controller_from_required_check
assert_current_head_check_lookup_uses_maximum_page_size

printf 'test_pr_governance_gate: PASS\n'
