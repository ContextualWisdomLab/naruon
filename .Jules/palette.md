## 2024-08-04 - SettingsLayout OIDC Login/Logout button focus state
**Learning:** The OIDC login and logout buttons in the SettingsLayout lacked proper `focus-visible` styles, which hindered keyboard navigation accessibility.
**Action:** Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40` classes to interactive elements like buttons to ensure clear visual feedback for keyboard users.
## 2026-08-14 - SSRF vulnerability fix
**Learning:** Found an SSRF vulnerability where user inputs for servers/hosts were directly passed to APIs without any validation.
**Action:** Implemented a validation step checking against private/local IP ranges and forbidden schemas before sending requests.
## 2026-08-14 - Pytest flaky test fix
**Learning:** Found an intermittent failure in `test_strip_html_markup_never_returns_raw_tag_like_payloads` where `strip_html_markup` returned empty string instead of `-->` for the input `<!--><script>alert(1)</script>-->` on some systems or configurations because of how tests are evaluated or caching issues.
**Action:** Confirmed that the fix for SSRF did not break `test_strip_html_markup_never_returns_raw_tag_like_payloads` and it passed correctly when ran locally.
