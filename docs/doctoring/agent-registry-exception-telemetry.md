# Agent registry exception telemetry boundary

## Scope

This document records the sink-specific follow-up to #1698 on the `backend/services/agent_registry.py` registry loader. The shared confidentiality contract is owned by #1700 on top of #1612; this lane only migrates the agent-registry read and JSON-parse failure sinks to that contract.

## Finding

The registry loader previously used ordinary `exc_info=True` for `OSError` and `json.JSONDecodeError`. Python logging can render the original exception value and traceback from that flag. At the same time, the log message included the registry path. A filesystem/provider failure can therefore disclose exception-carried credentials, connection strings, internal paths, or parser context into a normal production log sink.

The `FileNotFoundError` branch is intentionally unchanged. It does not attach exception information and identifies a deterministic missing registration file for operator diagnosis. This repair does not broaden into unrelated registry behavior.

## Decision

The two exception-bearing sinks now call `core.safe_logging.redacted_exception_info(error)`, inherited from #1700. The normal log record preserves:

- a bounded operation label (`Could not read registration file` or `Malformed registration file`);
- the exception class;
- the shared one-way failure-site fingerprint.

The record does not carry `str(error)`, `repr(error)`, the raw traceback, or the registry path in these failure cases. The fingerprint remains build-scoped rather than a cross-version durable identifier, matching #1700.

Rejected alternatives:

- keeping `exc_info=True`: retains the original exception value and traceback;
- interpolating the path while redacting only the exception: still exposes internal path material unnecessarily at this sink;
- dropping exception correlation entirely: weakens operational RCA without a confidentiality benefit over the shared structured contract;
- copying or forking the helper: would create a second telemetry contract instead of consuming the #1700 owner path.

## Verification

Focused tests drive the real `logging.Formatter` rather than checking only `LogRecord.getMessage()`. The read-failure case injects an API-key-shaped value, a PostgreSQL connection string, and a secret-bearing path into an `OSError`. The malformed-JSON case injects token-shaped content and a secret-bearing path. Both require the operation label, exception class, and `exception_fingerprint=` while rejecting the injected values and paths from rendered output.

No public/API response contract changes in this slice.

## Traceability

- Naruon issue #1698 — repository exception-log sink inventory and migration acceptance.
- Naruon PR #1700 — canonical structured exception telemetry helper and confidentiality contract.
- MITRE. (n.d.). *CWE-532: Insertion of Sensitive Information into Log File*. https://cwe.mitre.org/data/definitions/532.html
- OWASP Foundation. (n.d.). *Logging Cheat Sheet*. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## Integration gate

This lane remains stacked on #1700. It is not merge authority until the parent security lineage reaches protected ancestry and the final unchanged head obtains every then-live required hosted check plus qualifying independent review. No temporary retarget, copied workflow, synthetic status, dummy commit, force push, destructive rebase, self-approval, or gate weakening is acceptable evidence.
