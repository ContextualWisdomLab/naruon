#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  echo "usage: reject_terminal_output.sh command [args...]" >&2
  exit 64
fi

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

set +e
"$@" 2>&1 | tee "$output_file"
command_status=${PIPESTATUS[0]}
set -e

if ((command_status != 0)); then
  exit "$command_status"
fi

if grep -Eq 'Timeout|Fatal|Warn|Denied' "$output_file"; then
  echo "Execution output contained a policy-denied terminal result." >&2
  exit 65
fi
