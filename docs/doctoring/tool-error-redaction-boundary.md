# Tool Error Redaction Boundary

## Scope
The Naruon backend provides an execution boundary for dynamic tools (e.g. webhooks, decoders). When these tools encounter internal errors or connection failures, the exact exception detail MUST NOT be leaked to the client response, as this can reveal sensitive network topology or internal runtime state.

## Rules
- Webhook execution failures must raise exactly `Webhook execution failed` as the `ValueError` message, discarding the internal `httpx.HTTPError` string.
- Base64 decoding failures must raise exactly `Invalid Base64 string` as the `ValueError` message, discarding the internal `binascii.Error` string.
- The dedicated regression test `backend/tests/test_tool_error_redaction.py` enforces exact string matching for these boundaries and explicitly asserts the absence of injected/mocked error details.

## Changes
When modifying tool definitions in `backend/api/tools.py`, ensure any exception handling blocks map back to safe, generic strings before bubbling up to the client response wrapper.
