# UI localization content resource bounds

Status: Proposed with PR #1740. This record describes the pure-domain contract only; it does not claim that persistence, HTTP admission, browser rendering, or publication workflows are shipped.

## Problem

The localization policy already bounded locale tags, `Accept-Language`, `screen_key`, and `message_key`, but translation content and placeholder metadata remained syntactically constrained and operationally unbounded. A caller could submit an arbitrarily large translated message, a placeholder name of arbitrary length, or a tuple/list containing an arbitrary number of placeholder identities. The policy would then scan the whole message, run formatter parsing, allocate placeholder collections, and copy the complete schema before any downstream persistence or transport boundary had an opportunity to refuse the work.

That is inconsistent with the catalog's fail-closed resource policy. PostgreSQL `text` being variable-length does not define a safe product message budget, and an outer HTTP/proxy field or body limit cannot be the only guard for code paths that may also be called from offline authoring, tests, migrations, or future publication jobs.

MITRE CWE-400 describes uncontrolled resource consumption as an architecture/design weakness class and explicitly recommends placing specific limits of scale on protocols and resource-triggering inputs. This record uses that guidance only as resource-design traceability; it does not label this PR as a CVE or assign security severity from CWE-400 alone.

## RED

Commit `e1bdccc3b95bc41a8e03d29f3c581457cf586da5` adds focused boundary cases that are false on the predecessor policy:

- translation text accepts exactly 16,384 Python characters and rejects 16,385 with `ui_translation_input_invalid`;
- one placeholder name accepts exactly 64 characters and rejects 65 with `ui_placeholder_schema_invalid`;
- one message/schema accepts 32 unique placeholder names and rejects the 33rd with `ui_placeholder_schema_invalid`;
- direct placeholder extraction also rejects a 33rd unique placeholder, so callers cannot bypass the versioned-schema guard by invoking the extractor directly.

These are product limits, not values supplied by PostgreSQL, Unicode, Python, or an IETF specification.

## Decision

Causal fix `8cf8880fb86a87af22b9f18afd36f45acfb0e70d` adds three domain ceilings:

- `_MAX_TRANSLATION_MESSAGE_CHARS = 16_384`;
- `_MAX_PLACEHOLDER_NAME_CHARS = 64`;
- `_MAX_PLACEHOLDER_SCHEMA_ITEMS = 32`.

The checks are intentionally ordered to bound work before expensive or allocating steps:

1. translation text type and character count are checked before scanning Unicode scalar validity, lexical placeholder checks, or `Formatter.parse()`;
2. tuple/list schema length is checked before copying it to a tuple;
3. placeholder-name length is checked before accepting the identifier as catalog metadata;
4. direct extraction refuses a new unique placeholder once 32 names are already retained.

Over-limit input is rejected and never truncated. Truncation could alias distinct catalog content or placeholder identity and would make the immutable publication record dishonest.

The 16,384-character text ceiling is deliberately generous for a single UI message while making parser work finite. It is a character/code-point boundary in Python rather than a byte budget. Transport, persistence, export, or rendering owners may impose a stricter byte-size limit when their own contract requires it, but they must not silently accept a larger value by bypassing this domain policy.

## Rejected alternatives

### Leave content unbounded because the future API can cap request size

Rejected. The policy is callable outside HTTP, and resource safety would depend on every future caller reproducing the same limit correctly.

### Rely on PostgreSQL `text`

Rejected. PostgreSQL describes `text` as variable-length character data; that storage type is not a Naruon semantic or parser-work budget. Letting storage failure or memory pressure define the product limit would also move the failure away from the typed catalog boundary.

### Truncate text or placeholder metadata

Rejected. Truncation can change rendered meaning, collapse distinct placeholder identities, or publish a resource different from the reviewed source.

### Count UTF-8 bytes in this pure policy

Not selected for this layer. Python parsing cost here is driven primarily by the in-memory string and placeholder structure. A later transport/persistence owner can add an explicit byte budget if required, but that must be a separately tested contract rather than an implicit codec side effect.

## Downstream contract

Future persistence/publication and screen-scoped HTTP owners must preserve the 16,384/64/32 limits or enforce stricter documented limits without silent truncation. Publication completeness, immutable resource versions, placeholder equality, and the existing KO/EN/JA/ZH/VI/ES/DE/FR release set remain unchanged.

Realistic API/k6/E2E acceptance should cover normal payloads, exact-boundary payloads, and over-limit rejection on the final endpoint without sample shrinking or cache-only measurement. This pure-policy PR does not claim those runtime receipts.

## Traceability

- RED: `e1bdccc3b95bc41a8e03d29f3c581457cf586da5`.
- Causal source fix: `8cf8880fb86a87af22b9f18afd36f45acfb0e70d`.
- Canonical product Gap: #1731.
- Product/technical Gap ledger owner: #1602.

## References

MITRE. (2026). *CWE-400: Uncontrolled resource consumption (Version 4.20)*. Common Weakness Enumeration. https://cwe.mitre.org/data/definitions/400.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: Data types*. https://www.postgresql.org/docs/18/datatype.html
