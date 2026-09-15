# Tool error-redaction boundary

Date: 2026-09-16
Status: Proposed security doctoring for PR #1696

## Finding

`POST /api/tools/{code}/execute` returns handler failures through `ExecuteResponse.message`. The shared `_safe_tool_failure_message()` bounds and escapes exception text, but it does not remove credentials, provider responses, paths, connection details, or other sensitive values that may be present in the exception string. A handler that embeds a downstream exception into its own `ValueError` can therefore expose that detail to an authenticated API caller.

The reproduced boundary is narrow. `make_webhook_handler()` previously included the `httpx.HTTPError` text in `ValueError("Webhook execution failed: ...")`; `base64_decoder_handler()` likewise propagated arbitrary decoder exception text. The repair keeps the existing common failure envelope and substitutes stable public messages at those two handlers. Regression tests inject sensitive-looking exception details and require the final `ExecuteResponse` to contain only the stable message.

## Decision

Do not generalize this finding into a repository-wide rule that every caught exception must be removed from logs or replaced by `exc_info=True`.

`exc_info=True` preserves the traceback and the exception value for diagnostics. It is therefore not, by itself, a sensitive-log redaction mechanism. Log safety depends on the trust boundary, data classification, access controls, retention, and what the exception contains. Repository-wide logging changes require sink-specific evidence under the logging/security owner rather than a generated blanket rewrite.

Likewise, internal exception types that are already converted to generic HTTP responses are not changed merely to make their internal messages shorter. The security invariant owned here is the public tool response: untrusted downstream exception text must not reach `ExecuteResponse.message` through the retained webhook and Base64 handlers.

## Rejected alternatives

- Logging every exception with `exc_info=True` as a universal fix: rejected because traceback output still contains exception details and can itself become a CWE-532 sink.
- Replacing `_safe_tool_failure_message()` with one global generic string: rejected because existing domain validation errors intentionally communicate bounded, useful failure reasons; a global behavior change needs a separate API-contract decision.
- Keeping broad changes to email, import, archive, SMTP, parser, embedding, worker, and LLM code in this PR: rejected because the generated sweep mixed independent boundaries and surfaced unrelated findings. Those components require their own owner evidence.

## Verification

`backend/tests/test_tool_error_redaction.py` exercises the API execution envelope directly. It injects downstream detail strings that resemble secrets/internal paths and requires:

- `status == "failed"`;
- `result is None`;
- an exact stable public failure message; and
- absence of the injected detail from the returned message.

The PR remains Draft until the final integrated head receives all live required checks and a qualifying independent review. Because PR #1695 also writes `backend/api/tools.py`, neither branch should be independently merged over the other; the later validated lane must ordinary-adopt the other owner or a verified successor without force rewrite.

## References

MITRE. (2026). *CWE-209: Generation of error message containing sensitive information* (CWE Version 4.20). https://cwe.mitre.org/data/definitions/209.html

MITRE. (2026). *CWE-532: Insertion of sensitive information into log file* (CWE Version 4.20). https://cwe.mitre.org/data/definitions/532.html

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. Retrieved September 16, 2026, from https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
