# UI Localization Catalog identity resource bounds

## Status and owned boundary

**Proposed.** This record belongs to #1740's pure UI Localization Catalog policy. It changes only validation of product-owned `screen_key` and `message_key` identities; persistence, Alembic ownership, HTTP routing, browser caching and UI composition remain outside this PR.

## Verified finding

The policy described `screen_key` and `message_key` as stable bounded product identities, but the implementation bounded only their character grammar. Any syntactically valid lowercase identifier could therefore grow without limit before later persistence, indexing, cache-key construction and observability boundaries.

That was a contract mismatch. The future catalog schema uses `(screen_key, message_key)` as durable identity, so accepting unbounded valid identifiers in the pure policy would push resource control downstream and make database/index/API behavior deployment-dependent.

## RED and causal repair

RED `c0d802d33bf68ca6a8fbe70e4aaee5726b6d4a65` adds executable boundaries for both identities:

- a valid 128-character `screen_key` is accepted and the 129th character is rejected with `ui_screen_key_invalid`;
- a valid 128-character `message_key` is accepted and the 129th character is rejected with `ui_message_key_invalid`.

Causal fix `c40e2aa244249878405896fc1255d8c1df9d9dc5` introduces `_MAX_SCREEN_KEY_CHARS = 128` and `_MAX_MESSAGE_KEY_CHARS = 128` before the existing regex acceptance. Over-limit values fail closed and are never truncated.

The 128-character limits are Naruon product constraints, not PostgreSQL or IETF constants. They are intentionally aligned with the existing explicit-locale ceiling so product-owned textual identifiers have a deterministic upper bound before persistence and cache/index composition. The future persistence owner may choose narrower physical column/index constraints only if the API/domain contract is updated first; it must not silently truncate these identities.

## Rejected alternatives

Relying on PostgreSQL `text`, B-tree implementation limits, reverse proxies, or application-memory pressure is rejected because none of those is the domain contract. Truncation is rejected because `(screen_key, message_key)` is semantic identity: shortening it can alias two different product messages. Bounding only the eventual database column is also rejected because this pure policy is callable before persistence exists.

## Verification boundary

The RED and causal fix are committed. This runtime could not obtain an exact repository checkout because outbound Git resolution is unavailable, so no local/container PASS is claimed. Current-head hosted CI/security and qualifying independent post-last-push review remain the acceptance authority.

Future persistence/API tests must prove that the same 128/128 contract is preserved at write/read boundaries, that no transport or migration silently truncates values, and that indexed screen-scoped lookup remains within the buyer-path performance budget.

## TRACEABILITY

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: Character types*. https://www.postgresql.org/docs/18/datatype-character.html

Naruon's limits are product architecture decisions layered above PostgreSQL. PostgreSQL `text` does not supply the semantic identity ceiling required by the product; the domain therefore owns and tests the limit explicitly.
