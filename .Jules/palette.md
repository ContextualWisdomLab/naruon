## 2024-08-04 - SettingsLayout OIDC Login/Logout button focus state
**Learning:** The OIDC login and logout buttons in the SettingsLayout lacked proper `focus-visible` styles, which hindered keyboard navigation accessibility.
**Action:** Added `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40` classes to interactive elements like buttons to ensure clear visual feedback for keyboard users.
