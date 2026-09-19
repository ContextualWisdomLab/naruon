# LLM provider error redaction

## Problem

Generated PR #1733 correctly identified that `backend/services/llm_service.py` rendered provider exception text into `LLMServiceError`, but its first fix still called `logger.error(..., exc_info=True)`. That preserved the same provider-controlled exception message and traceback in application logs. Provider SDK errors may contain request URLs, headers, identifiers, response fragments, or credentials; moving the value from an API exception into a centralized log sink does not remove the disclosure boundary.

## Decision

The service now records only bounded operational metadata for provider failures:

- a fixed event message, `LLM provider request failed`;
- a fixed operation identifier (`extraction`, `translation`, or `drafting`);
- the exception class name as `error_type`;
- no exception string, traceback, provider response body, request body, key, token, URL query, or header value.

The public/internal service exception keeps a fixed operation-specific message and is raised `from None`, so an upstream logger that renders the sanitized exception does not automatically include the provider exception chain. API handlers already map `LLMServiceError` to a generic HTTP 500 detail.

This deliberately trades raw provider traceback detail for purpose-bound security logging. Future diagnostics that need provider-specific detail must introduce an explicitly redacted structured contract rather than re-enable generic `exc_info` or exception interpolation.

## Executable evidence

`backend/tests/test_llm_error_redaction.py` supplies a provider exception containing a secret canary and proves that:

- the rendered log does not contain the secret;
- the log record contains only the fixed message, operation, and exception class;
- `exc_info` is absent;
- the raised `LLMServiceError` contains only the fixed message;
- exception chaining is suppressed;
- client cleanup still executes.

The existing `backend/tests/test_llm_service.py` and `backend/tests/test_llm_api.py` continue to cover success/error behavior for service and HTTP boundaries. Exact-head hosted evidence remains required before merge.

## Rejected alternatives

`logger.error(..., exc_info=True)` was rejected because Python logging renders the active exception traceback, including exception-controlled text. Logging `str(error)` or `%s` was rejected for the same reason. Blanket regex redaction was not selected because provider error formats are open-ended and denylisting secret shapes is not a complete confidentiality boundary.

## Rollback

If the structured metadata breaks an operational consumer, roll back only the metadata fields while retaining fixed-message logging and fixed public exceptions. Do not restore traceback logging or provider exception interpolation without a reviewed redaction contract and regression evidence.

## Traceability

- Naruon PR #1733: generated finding and repaired owner lane.
- Protected source before repair: `develop@042b0c70531b229af3acbd0421a2f23098d848b3`.
- Generated first head: `41644c0d51801547a4b408e23f7cad029c989c0d`.
- Repair commits begin at `74650fc5a813808a74b0895fe93293f557879007` and `6c45794e692a259a9c672588e4b29040ed45b782`.

## References

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

OWASP Foundation. (n.d.). *Microservices security cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html
