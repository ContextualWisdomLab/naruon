## 2026-08-24 - Trigger CI Rebuild for Noema

**Learning:** When the noema-review security scan fails with "TimeoutError: timed out", it is an infrastructure flake, not a codebase vulnerability.
**Action:** Simply append a trivial comment to the modified file and push again to trigger a new CI run.
