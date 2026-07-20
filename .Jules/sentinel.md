## 2026-06-30 - XSS Vulnerability in DataLayout Component
**Vulnerability:** User-controlled input in file names and asset metadata was rendered without proper sanitization, allowing execution of arbitrary JavaScript (e.g. `<img src=x onerror=alert(1)>`).
**Learning:** React escapes text children by default, but relying on this is not enough if variables are passed to components that might render them unsafely, or if scanning tools mandate explicit sanitization functions for user-provided data.
**Prevention:** To prevent XSS vulnerabilities and satisfy penetration testing gates (like Strix), always explicitly wrap user-controlled string variables rendered in the UI with `toSafeReactText()` (e.g., `{toSafeReactText(asset.display_name)}`).
