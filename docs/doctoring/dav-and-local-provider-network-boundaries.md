# DAV/WebDAV single-decode and tenant boundary

## Scope

This decision is limited to Naruon's DAV/WebDAV edge and workspace-document authorization boundary. The historical filename is retained to avoid churn, but LLM-provider routing, provider URL admission, DNS rebinding controls, and provider-network policy are not owned by this change.

## Problem

A DAV path can cross an authorization boundary if percent-encoding is decoded more than once. For example, a residual encoded slash can become a hierarchy separator during a second decode after the edge has already authorized a different canonical path. The DAV surface must also advertise only capabilities that the server actually implements, and workspace-document access must remain scoped by organization identity.

## Decision

- Decode the incoming DAV path exactly once at the edge.
- Reject a decoded path that still contains a syntactically valid percent triplet whose second decoding could change path semantics.
- Normalize and authorize the repository-relative path only after that single decode.
- Downstream DAV/WebDAV services consume the canonical path and do not decode it again.
- Advertise DAV Level 1 capability truth only; do not claim unsupported DAV levels or extension tokens.
- Workspace-document reads and creates require the caller's `org_id` and preserve organization scoping through the repository boundary.

These rules keep path interpretation, capability truth, and tenant authorization inside the Naruon DAV/document bounded context.

## Verification

The executable contract is covered by:

- `backend/tests/test_dav_path_canonicalization.py`
- `backend/tests/test_dav_auth.py`
- `backend/tests/test_dav_integration.py`
- `backend/tests/test_dav_propfind.py`
- `backend/tests/test_webdav_security.py`
- `backend/tests/test_workspace_document_tenancy.py`

The PR must also pass the repository's current exact-head required workflows. Evidence from a predecessor SHA is not merge authority.

## External owner boundary

LLM-provider selection, provider URL/routing policy, provider-network SSRF policy, DNS-rebinding protection, credentials, and fallback behavior belong to the released `contextual-orchestrator` owner path. This PR restores `backend/services/llm_provider_urls.py` and `backend/tests/test_llm_provider_urls.py` to the protected `develop` versions and does not change provider policy. Broader removal or migration of Naruon's protected legacy direct-provider implementation is handled by the canonical docs/governance and contextual-orchestrator integration lane rather than by this DAV repair.

## Rollback

Rollback reverts only the DAV/document changes in this branch. It must not introduce a second decoder or expand DAV capability advertisement. Provider-policy files remain at the protected-base versions throughout this repair.

## Traceability

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform Resource Identifier (URI): Generic syntax* (RFC 3986, §§ 2.1, 2.4). Internet Engineering Task Force. https://doi.org/10.17487/RFC3986

Dusseault, L. (Ed.). (2007). *HTTP extensions for Web Distributed Authoring and Versioning (WebDAV)* (RFC 4918, § 10.1). Internet Engineering Task Force. https://doi.org/10.17487/RFC4918
