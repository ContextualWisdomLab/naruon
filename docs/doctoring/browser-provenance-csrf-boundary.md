# Browser-provenance CSRF boundary

## Decision status

Proposed. This change is not merge-ready until the exact protected-base PR head has hosted tests/security checks and qualifying independent review.

## Problem

Protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3` applies the backend CSRF middleware to every state-changing `/api/*` request, but `_is_trusted_browser_origin(None)` treats missing Origin/Referer as trusted. A request that carries browser-controlled Fetch Metadata such as `Sec-Fetch-Site: same-origin` while omitting both Origin and Referer therefore reaches the authenticated API boundary instead of failing closed.

At the same time, Naruon has legitimate non-browser API clients that may carry no browser provenance headers. Treating every provenance-free request as a browser request would conflate browser CSRF defenses with service/client authentication and would break that boundary without evidence.

## RED and causal repair

- RED commit: `181ce1cc108db0d48c3d97dbf50fdb9b3d8e9dc2`
  - adds a regression requiring a state-changing request with `Sec-Fetch-Site: same-origin` and no Origin/Referer to return `csrf_referer_rejected`;
  - preserves the existing expectation that a provenance-free non-browser request reaches the normal authentication gate.
- causal fix: `23e59fd27415ef81b297c36fcdb46c608f2e240d`
  - `_requires_browser_origin_check()` now activates only when a state-changing `/api/*` request carries `Origin`, `Referer`, or `Sec-Fetch-Site`;
  - `_is_trusted_browser_origin(None)` becomes fail-closed inside that browser-provenance path;
  - the Origin rejection guard no longer consumes the `None` case before Referer fallback runs.

The change does not weaken the existing `Sec-Fetch-Site: cross-site` rejection or the allowlisted Origin/Referer checks.

## Boundary and rejected alternatives

Naruon's Next.js API proxy already owns a stricter browser-only boundary: merged #653 rejects state-changing proxy requests when neither Origin nor Referer is present. The backend serves both browser-derived traffic and non-browser authenticated clients, so this PR does not copy the proxy's unconditional missing-header rejection into the backend.

Rejected alternatives:

- **Trust `Sec-Fetch-Site: same-origin` without Origin/Referer.** Rejected because the backend already has an explicit allowlisted-origin contract and Fetch Metadata is a contextual signal, not a replacement for target-origin verification.
- **Reject every state-changing request with no Origin/Referer.** Rejected because it would silently redefine non-browser API authentication as browser traffic.
- **Treat this as a complete CSRF solution.** Rejected. Legacy user agents may omit Fetch Metadata. Existing Origin/Referer and frontend-proxy protections remain necessary, and session/cookie policy is a separate control.

## Standards and research traceability

World Wide Web Consortium. (2025, April 1). *Fetch Metadata Request Headers* (Working Draft). https://www.w3.org/TR/fetch-metadata/

OWASP Foundation. (n.d.). *Cross-Site Request Forgery Prevention Cheat Sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

Barth, A., Jackson, C., & Mitchell, J. C. (2008). Robust defenses for cross-site request forgery. In *Proceedings of the 15th ACM Conference on Computer and Communications Security (CCS '08)*. Association for Computing Machinery.

The W3C Fetch Metadata specification defines `Sec-Fetch-Site` as browser-generated context about the initiator/target relationship and uses the `Sec-` prefix so web content cannot forge those headers. OWASP recommends `Sec-Fetch-Site` as a CSRF signal while retaining Origin/Referer verification for compatibility. Barth, Jackson, and Mitchell provide the peer-reviewed basis for server-side origin-validation defenses against CSRF.

## Acceptance

Before Ready/merge:

1. exact-head backend tests must prove the browser-provenance missing-Origin/Referer rejection and the provenance-free non-browser authentication path;
2. existing cross-site Fetch Metadata, untrusted Origin, trusted Origin, and Referer canonicalization regressions must remain GREEN;
3. all then-live required CI/security checks must be terminal-success on the unchanged head;
4. no valid current-head review thread may remain unresolved and a qualifying independent approval is required;
5. #1361 must no longer carry this CSRF delta once this owner lane exists, so the checksum PR returns to a pure checksum-owned diff.

Refs #1705, #1361, #653. Historical #563 text mentioned backend CSRF hardening, but its merged diff contains only frontend AI Hub files; it is therefore narrative history rather than source authority for this backend change.
