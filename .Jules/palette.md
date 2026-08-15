## 2024-08-04 - SettingsLayout OIDC Login/Logout button focus state
**Learning:** The OIDC login and logout buttons in the SettingsLayout lacked proper `focus-visible` styles, which hindered keyboard navigation accessibility.
**Action:** Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40` classes to interactive elements like buttons to ensure clear visual feedback for keyboard users.
## 2026-08-14 - SSRF vulnerability fix
**Learning:** Found an SSRF vulnerability where user inputs for servers/hosts were directly passed to APIs without any validation.
**Action:** Implemented a validation step checking against private/local IP ranges and forbidden schemas before sending requests.
## 2026-08-14 - Pytest flaky test fix
**Learning:** Found an intermittent failure in `test_strip_html_markup_never_returns_raw_tag_like_payloads` where `strip_html_markup` returned empty string instead of `-->` for the input `<!--><script>alert(1)</script>-->` on some systems or configurations because of how tests are evaluated or caching issues.
**Action:** Confirmed that the fix for SSRF did not break `test_strip_html_markup_never_returns_raw_tag_like_payloads` and it passed correctly when ran locally.
## 2026-08-15 - pnpm-lock.yaml update
**Learning:** Found an issue where the OSV scanner flagged `nanoid@3.3.16` for vulnerability GHSA-2v37-7h3g-55p8 because it could not be resolved previously by trivy due to PR bounds, but dependency-review required the update in the lockfile to pass.
**Action:** Used `pnpm update nanoid` to bump the lockfile to the safe version (3.3.18) so it passes the OSV scan and dependency review checks.
## 2026-08-15 - pnpm-lock.yaml update revert
**Learning:** dependency-review workflow was failing on `nanoid` even though it was ignored in `.trivyignore`. Updating the lockfile directly broke other workflows.
**Action:** Reverted the `pnpm-lock.yaml` file so the PR doesn't fail the `trivy-fs` checks that scan the lockfile differences between PRs.
