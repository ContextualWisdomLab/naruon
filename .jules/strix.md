## 2026-08-24 - Trigger CI Rebuild for Strix

**Learning:** When the Strix security scan fails with "Strix could not complete authoritative vulnerability analysis because its provider/backend was unavailable", it is an infrastructure flake (rate limit, unavailable model, etc.), not a codebase vulnerability.
**Action:** Simply append a trivial comment (e.g. `// Trigger CI rebuild for Strix failure`) to the modified file and push again to trigger a new CI run.
