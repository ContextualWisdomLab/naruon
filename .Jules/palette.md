## 2024-08-04 - SettingsLayout OIDC Login/Logout button focus state
**Learning:** The OIDC login and logout buttons in the SettingsLayout lacked proper `focus-visible` styles, which hindered keyboard navigation accessibility.
**Action:** Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40` classes to interactive elements like buttons to ensure clear visual feedback for keyboard users.
## 2026-08-14 - SSRF vulnerability fix
**Learning:** Found an SSRF vulnerability where user inputs for servers/hosts were directly passed to APIs without any validation.
**Action:** Implemented a validation step checking against private/local IP ranges and forbidden schemas before sending requests.
