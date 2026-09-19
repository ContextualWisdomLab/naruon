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

## Review finding verification

The first CodeRabbit review requested regression assertions for extraction, translation, standard drafting and Ollama drafting, which was valid. Its accompanying request to retain traceback-aware `exc_info` was not valid for this threat model: the defect under review is confidentiality of provider-controlled exception text, and Python traceback logging would preserve that text in the log sink. The valid coverage portion was adopted while the unsafe logging recommendation was rejected with this evidence trail.

## Executable evidence

`backend/tests/test_llm_error_redaction.py` supplies a provider exception containing a secret canary and covers all four production failure paths:

- extraction;
- translation;
- standard OpenAI-compatible drafting;
- Ollama native-chat drafting.

For each path the regression proves the exact generic `LLMServiceError` message, absence of provider exception text in rendered logs, suppressed exception chaining, fixed structured operation/error-class metadata, absence of `exc_info`, and the applicable client cleanup. A direct helper test additionally proves the structured logging boundary itself.

The existing `backend/tests/test_llm_service.py` and `backend/tests/test_llm_api.py` continue to cover broader success/error behavior for service and HTTP boundaries. Exact-head hosted evidence remains required before merge.

## Rejected alternatives

`logger.error(..., exc_info=True)` was rejected because Python logging renders the active exception traceback, including exception-controlled text. Logging `str(error)` or `%s` was rejected for the same reason. Blanket regex redaction was not selected because provider error formats are open-ended and denylisting secret shapes is not a complete confidentiality boundary.

## Generated-writer cleanup

The generated first commit also appended task-specific advice to `.jules/sentinel.md`, including the incorrect claim that `exc_info=True` was the secure remedy. After the source fix was captured in production code, tests and this doctoring record, `.jules/sentinel.md` was restored byte-for-byte to protected-base blob `9208f58b118f11d0983c3a62df96916ec61a3384`. The effective PR therefore carries no Sentinel self-modification.

## Intervening generated-writer regression and repair

After the reviewed `7e8321bb5a059e6076a1ab1daa4f35ad8a6ae266` generation, generated commit `1da2457c0e8cfa71a620515a93611b97d4aad200` arrived as an ordinary child. The production source and four-path regression remained intact, but the doctoring file was partially rolled back: the review-finding verification, explicit four-path evidence, generated-writer cleanup record, and exact repair lineage were removed.

That is a documentation/traceability regression rather than a new product implementation. The generated commit is retained in ancestry and this ordinary-forward repair restores the stronger evidence record without force push, destructive rebase, receipt transfer, or product-source churn. Hosted checks and reviews from predecessor heads remain predecessor evidence only.

## Rollback

If the structured metadata breaks an operational consumer, roll back only the metadata fields while retaining fixed-message logging and fixed public exceptions. Do not restore traceback logging or provider exception interpolation without a reviewed redaction contract and regression evidence.

## Traceability

- Naruon PR #1733: generated finding and repaired owner lane.
- Protected source before repair: `develop@042b0c70531b229af3acbd0421a2f23098d848b3`.
- Generated first head: `41644c0d51801547a4b408e23f7cad029c989c0d`.
- Production redaction repair: `74650fc5a813808a74b0895fe93293f557879007`.
- Initial hostile-canary regression: `6c45794e692a259a9c672588e4b29040ed45b782`.
- Generated-guidance cleanup reaches exact byte-for-byte restore at `1ce246d8b8452dae4bc408ad534ecda1fbc61134`.
- Four-path review finding coverage: `cff4bf7234032dedcba5463e69a71dc491db6e9d`.
- Reviewed traceability generation: `7e8321bb5a059e6076a1ab1daa4f35ad8a6ae266`.
- Intervening generated doctoring rollback retained in ancestry: `1da2457c0e8cfa71a620515a93611b97d4aad200`.

## References

OWASP Foundation. (n.d.). *Logging cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

OWASP Foundation. (n.d.). *Microservices security cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html
