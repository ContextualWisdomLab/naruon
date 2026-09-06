# Repository asset inline-preview payload bound

Status: Proposed

## Problem

The repository-asset preview service could return every recognized HWPX paragraph and also join the same paragraphs into `preview_text`. A valid recognized package can therefore turn one authenticated preview request into a multi-megabyte response and a correspondingly large frontend render. The source document remains authoritative; the inline preview is only a bounded reading surface.

## Constraints

- Do not truncate recognized text silently. A partial preview must not be presented as complete source evidence.
- Do not delete or shorten stored source text or content-graph segments.
- Do not change HWPX/PDF recognition semantics or call a provider/model from the preview path.
- Keep pending and failed recognition states distinct from a display-capacity limit.
- Preserve the existing response shape while a paginated preview contract is not yet available.

## Decision

`backend/services/repository_asset_preview.py` now applies a 64 KiB inline text budget before returning recognized content.

- Workspace documents are checked against the stored source length before paragraph splitting.
- Attachment content-graph segments are accumulated against the same budget before sanitization/joining; fallback stored attachment text is checked before paragraph splitting.
- The final serialized paragraph payload is checked again including paragraph separators.
- If the bound is exceeded, the service returns `preview_state="unavailable"`, no `paragraph_texts`, no `preview_text`, and `error_code="repository_asset_preview_too_large"`.
- Stored source and recognition evidence are unchanged. The service does not silently truncate or duplicate a multi-megabyte payload into the API response.

The 64 KiB value is a conservative inline-display safety bound, not a claim that 64 KiB is a globally optimal UX or transport threshold. Representative browser/API profiling and a paginated or source-opening flow remain follow-up work before this decision can become Accepted.

## Test-first evidence

- RED `2f645cf27332d0ba5c87447b972cd3a5957e8de7` required an oversized workspace document to fail closed instead of returning recognized text.
- RED extension `2c3267d416323276098235d41fd143dc5cf7c3fc` added the equivalent HWPX content-segment case. The pre-fix service reproduced both failures as `recognized` responses.
- Causal fix `d1e8316b4f24121cb56f22f326d69d075134a254` adds the source, segment, and serialized-payload guards and the explicit unavailable error category.
- Focused isolated service/status harness after the fix: 4 passed, 0 failed. This is not a clean-lock repository run, PostgreSQL/API/browser evidence, coverage evidence, hosted Check, or protected GREEN.

## Alternatives rejected

- Silent truncation was rejected because it would make incomplete recognized text look authoritative.
- Removing only `preview_text` was rejected because `paragraph_texts` could still transfer and render a multi-megabyte payload.
- Raising the parser/recognition size limit was rejected because source-recognition capacity and inline-display capacity are separate contracts.

## Follow-up

A buyer-facing large-document flow should provide an explicit bounded pagination or source-opening contract, with normal/loading/empty/error/permission states and representative API/browser p95 measurements. Until that exists, oversized recognized source remains intact but unavailable through the inline preview.
