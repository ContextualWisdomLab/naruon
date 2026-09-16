# Runner signal exception telemetry boundary

## Authority and scope

Issue #1698 owns the repository-wide logging-confidentiality gap. This slice is a stacked consumer of #1700 (`2d6800aea110ac04eeedcd5faa91479f62877408`) and changes only the outbound runner control-plane telemetry in `backend/api/runner_ws.py` plus focused regressions. It does not copy the shared redaction helper, change WebSocket or writeback contracts, or claim the remaining #1698 sinks complete.

Two runner paths on the current owner lineage still attached raw exception information to normal application logs:

- `ConnectionManager.dispatch_command()` used `logger.exception()` for arbitrary runner transport/dispatch failures;
- `_record_connector_signal_event_safely()` used `exc_info=True` for SQLAlchemy persistence failures.

Python logging attaches exception information when `exc_info` is truthy. The ordinary current-exception path includes the caught exception value and traceback. A provider/transport exception can therefore carry token-shaped data or internal filesystem details, while a database exception can contain a credential-bearing connection string or query/system metadata.

## Decision

Both sites retain their existing severity and fixed operation message but pass the caught exception through #1700's `core.safe_logging.redacted_exception_info()` contract.

The emitted record keeps only the bounded diagnostic surface established by #1700:

- fixed operation message;
- exception class;
- one-way 16-hex failure-site fingerprint;
- no raw exception value;
- no original traceback attachment.

The runner's public response, retry classification, signal persistence attempt, request identifiers, connection ownership, transaction scope, and provider-writeback behavior are unchanged. The persistence helper still treats `SQLAlchemyError` as best-effort telemetry failure; the dispatch path still returns the existing deterministic `runner_dispatch_failed` result and preserves ERROR severity.

## Alternatives rejected

Leaving `logger.exception()` or `exc_info=True` in these sinks is rejected because those mechanisms preserve the exact exception object/traceback that #1700 exists to bound. Removing exception diagnostics entirely is also rejected because operations still need a type and stable-per-build failure-site correlation key for RCA.

A runner-local sanitizer is rejected. The confidentiality contract belongs to #1700; duplicating hashing/redaction logic here would create a second security authority and allow the two implementations to drift.

## RED → repair verification

`backend/tests/test_runner_signal_exception_telemetry.py` injects two realistic secret-bearing failures through the actual runner logging sinks:

1. a `SQLAlchemyError` containing a PostgreSQL URI plus token-like text during connector-signal persistence;
2. a `RuntimeError` containing an internal path plus token-like text from `send_text()` during command dispatch.

The regression inspects the rendered logging output through pytest `caplog`. Each path must retain its operation message, exception type, and `exception_fingerprint=` marker while excluding the exact injected detail, token text, and `Traceback (most recent call last)`. The dispatch regression also requires the pre-existing deterministic `runner_dispatch_failed` API result so logging hardening cannot change caller behavior.

The first test-only head was `566f1f737d5aef8b0e7f5711950aecf6936dafd8`; the second test-only extension was `4e8e800e31d1fd2bfbd0d5b0a70c8759ff29df3a`. Production repair begins at `3026bac5d7c23c2bda08c4fa22d962531a247bbc`. Hosted exact-head evidence and independent review remain separate gates.

## Traceability

CWE-532 treats sensitive information written to log files as a security weakness and recommends considering the sensitivity of logged data. The OWASP Logging Cheat Sheet specifically lists access tokens, authentication passwords, database connection strings, encryption keys, and other primary secrets among data that should ordinarily be removed, masked, sanitized, hashed, or encrypted before logging. Python 3.14 logging documentation confirms that truthy `exc_info` adds exception information to the logging message; when no explicit tuple or exception instance is supplied, the current exception information is used.

### References

MITRE. (2026). *CWE-532: Insertion of sensitive information into log file* (CWE Version 4.20). https://cwe.mitre.org/data/definitions/532.html

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. Retrieved September 17, 2026, from https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Python Software Foundation. (2026). *logging — Logging facility for Python* (Python 3.14.7 documentation). https://docs.python.org/3/library/logging.html
