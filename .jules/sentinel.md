## 2024-07-08 - [Path Traversal bypass via URL encoding]
**Vulnerability:** Path traversal bypass in DAV adapter local path validation.
**Learning:** URL-encoded dots and slashes (`%2e%2e`, `%2f`) can bypass dot-segment validation checks if the raw string is split and validated before being decoded.
**Prevention:** Always decode paths (e.g., using `urllib.parse.unquote`) *before* applying character and segment restrictions.
