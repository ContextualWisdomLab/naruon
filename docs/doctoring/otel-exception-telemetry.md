# OpenTelemetry setup exception telemetry boundary

## Scope

This document records a sink-specific follow-up to #1698 for `backend/core/telemetry.py`. The shared bounded exception-correlation contract is owned by #1700 on top of #1612. This lane only migrates the OpenTelemetry setup-failure sink to that contract; it does not change telemetry enablement, endpoint validation, exporter configuration, instrumentation lifecycle, or the existing bootstrap environment-variable boundary.

## Finding

`setup_telemetry()` previously handled an arbitrary setup failure with `logger.exception("OpenTelemetry setup failed; continuing without tracing.")`. Python 3.14 logging attaches exception information when `exc_info` is truthy, and `logger.exception()` is the exception-logging convenience path. A dependency, exporter, DNS/TLS, or instrumentation failure can therefore place its original exception value and traceback into the normal application log.

That value may contain a credential-bearing connection string, provider response text, token-shaped data, or an internal path. CWE-532 and the OWASP Logging Cheat Sheet treat those values as data that should not be written directly to ordinary logs. The operational requirement is still to retain enough bounded evidence to correlate repeated setup failures.

## RED → minimal causal fix

Test-first commit `d7289799e2661ad3ebbf5c309579ec8bdc45738b` injects a `RuntimeError` from the real import boundary used by `setup_telemetry()`. Its message contains a token-shaped value, a PostgreSQL connection string, and an internal file path. The regression formats the resulting `LogRecord` and requires the fixed operation label, exception type, and `exception_fingerprint=` marker while rejecting the injected values and traceback header. On the predecessor implementation, ordinary `logger.exception()` renders the original failure and cannot satisfy that contract.

Production repair `96446d87fdbf59de1868a55f01be999990d31df8` catches the same setup exception and passes it to #1700's `core.safe_logging.redacted_exception_info()` helper. The error severity and operation message remain unchanged. The helper emits only a bounded exception class plus a one-way failure-site fingerprint and attaches no raw traceback.

The application still continues without tracing after setup failure, exactly as before. No API response, database transaction, provider-routing, telemetry endpoint, or instrumentation-success behavior changes in this slice.

Rejected alternatives:

- retaining `logger.exception()` or raw `exc_info=True`: preserves the original exception value and traceback;
- logging only a static message: avoids disclosure but removes bounded correlation evidence that #1700 already standardizes;
- creating a telemetry-local sanitizer: duplicates the canonical structured exception-telemetry contract;
- changing the OTEL bootstrap configuration source in the same PR: expands ownership beyond the verified logging sink and is not causal to this disclosure.

## Verification boundary

The focused regression exercises the actual `setup_telemetry()` exception boundary without requiring a real OTLP collector. It verifies the fully formatted record rather than only `LogRecord.getMessage()`, because exception rendering occurs during formatting.

This branch has not acquired executable hosted evidence merely by adding the regression. The exact final head must still receive repository-required checks and qualifying independent review after the complete source/test/doctoring delta is present. Parent #1700 evidence does not transfer.

## Traceability

- Naruon issue #1698 — repository exception-log sink inventory and migration acceptance.
- Naruon PR #1700 — canonical structured exception telemetry helper and confidentiality contract.
- Python Software Foundation. (2026). *logging — Logging facility for Python (Python 3.14.6 documentation)*. https://docs.python.org/3.14/library/logging.html
- The MITRE Corporation. (2026). *CWE-532: Insertion of Sensitive Information into Log File (CWE 4.20)*. https://cwe.mitre.org/data/definitions/532.html
- OWASP Foundation. (n.d.). *Logging Cheat Sheet*. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## Integration gate

Keep this lane stacked on #1700. It is not merge authority until the canonical exception-redaction/telemetry lineage reaches protected ancestry and the unchanged final head obtains every then-live required hosted context plus qualifying independent review. Do not temporary-retarget to `develop`, copy workflows, synthesize status, push a dummy/no-op evidence commit, self-approve, force-push, destructively rebase, or weaken a gate.
