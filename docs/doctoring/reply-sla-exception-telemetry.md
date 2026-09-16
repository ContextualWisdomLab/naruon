# Reply SLA scheduler exception telemetry boundary

## Scope

This document records the Reply SLA scheduler sink-specific migration required by issue #1698. The shared exception-telemetry contract remains owned by #1700; this lane consumes `core.safe_logging.redacted_exception_info(...)` and does not fork or copy that helper.

The affected production sinks are both in `backend/services/reply_sla_scheduler.py`:

- the scheduler loop catch-all around `_sync()`;
- the per-owner escalation catch-all around `create_reply_sla_escalation_tasks(...)`.

## Verified finding

Both sinks previously used ordinary `exc_info=True`. Python logging formats the original exception value and traceback for that form, so provider responses, database connection strings, credentials, tokens, filesystem paths, and other exception-carried data can reach the normal application log. The per-owner sink additionally interpolated `config.user_id` into the same failure record.

The disclosure is not theoretical for the logging contract: a representative secret-bearing `RuntimeError` rendered through the old sink includes the exception value and traceback, and the owner-level record includes the configured owner identifier. The regression tests in this lane encode those values as failure cases.

## Decision

Both exception-bearing sinks now call the #1700 `redacted_exception_info(error)` boundary. The rendered record retains:

- a bounded operation label;
- the exception class;
- the shared one-way failure-site fingerprint.

The record does not retain the original exception value, raw traceback, or owner identifier.

The owner identifier is deliberately removed rather than hashed ad hoc in this lane. OWASP guidance identifies access tokens, database connection strings, file paths, and personal identifiers as data that should generally be removed, sanitized, encrypted, or de-identified before logging. A durable tenant-correlation identifier would need an explicit purpose, rotation/stability contract, access boundary, and retention policy; inventing one inside this sink would create a second telemetry contract.

Rejected alternatives:

- keeping `exc_info=True` with a static message: the traceback renderer still exposes the original exception value and source location;
- keeping raw `config.user_id`: it is unnecessary for this failure-site diagnostic and can be personal or tenant-identifying data;
- suppressing exception evidence entirely: removes useful incident correlation;
- copying the #1700 helper: violates the canonical telemetry owner boundary.

## Verification

`backend/tests/test_reply_sla_scheduler_exception_telemetry.py` exercises both real scheduler failure paths through a production `logging.Formatter`.

The owner-level case injects an email-shaped owner identifier, API-key-shaped text, and a PostgreSQL credential-bearing connection string. The loop case injects a provider token and internal filesystem path. Each regression requires the operation label, exception class, and `exception_fingerprint=` while rejecting the injected sensitive values from rendered output.

The existing scheduler behavior tests remain authoritative for cancellation, lease acquisition/release, continuation after one owner failure, and scheduler lifecycle. This change does not alter escalation, transaction, advisory-lock, or retry semantics.

## Traceability

- Naruon issue #1698 — repository exception-log sink inventory and migration acceptance.
- Naruon PR #1700 — canonical structured exception telemetry helper and confidentiality contract.
- MITRE. (2026). *CWE-532: Insertion of Sensitive Information into Log File* (CWE 4.20). https://cwe.mitre.org/data/definitions/532.html
- OWASP Foundation. (n.d.). *Logging Cheat Sheet*. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## Integration gate

This lane remains stacked on #1700. It is not merge authority until the canonical exception-redaction/telemetry lineage reaches protected ancestry and the final unchanged head obtains every then-live required hosted context plus qualifying post-last-push independent review. Do not use a temporary `develop` retarget, copied workflow, dummy/no-op evidence commit, synthetic status, self-approval, force push, destructive rebase, or gate weakening as substitute evidence.
