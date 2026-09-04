# Email-writing review API contract

Status: **active Draft implementation on PR #1536; not protected-branch truth**.

Architecture authority remains [ADR-0005](../adr/0005-inkspan-backed-llm-email-writing-guidance.md). This document records the concrete Naruon HTTP boundary introduced by Task 10 without promoting that active PR to shipped product behavior.

## Responsibility

Naruon owns the authenticated mail-review transport and authorized context boundary. Inkspan owns revision-bound editor and diagnostic interaction. `contextual-orchestrator` owns semantic model routing. `fast-mlsirm` owns independent criterion-level Judge and calibration contracts.

The review endpoint is advisory. It has no authority to mutate the editor, send mail, weaken an email request, select an upstream model provider, publish calibration evidence, or replace unavailable semantic review with lexical heuristics.

## HTTP boundary

The active Task-10 route is:

```text
POST /api/email-writing/review
```

It consumes the existing strict `EmailWritingReviewRequest` contract and returns `EmailWritingReviewResponse`. The application supplies the authenticated `AuthContext` and scoped database session; callers cannot provide or override either authority in the request body.

The request retains the reviewed source email identifier, exact SHA-256 document revision, Inkspan-compatible text projection identity/version, draft text, language tag, review mode, optional W3C `TextPositionSelector`, and bounded reply objective. Transport/schema validation occurs before the review service executes.

A successful HTTP response can still contain an advisory review state such as `abstained`, `unavailable`, `stale`, `context_insufficient`, or `judge_disagreement`. Such a response does not disable ordinary editing or sending.

## Error contract

The API exposes a typed `EmailWritingReviewErrorResponse` for 403, 404, and 503 responses and never returns raw causal service text:

| Condition | HTTP | Stable response |
| --- | ---: | --- |
| source email is unavailable under the authorized scope | 404 | `{"error_code":"email_unavailable"}` |
| authenticated owner scope cannot be established | 403 | `{"error_code":"review_owner_scope_unavailable"}` |
| allowlisted review evidence/runtime/provider failure | 503 | the corresponding bounded public error code |
| production review runtime has not been admitted | 503 | `{"error_code":"review_runtime_unavailable"}` |
| non-allowlisted service error code | 503 | `{"error_code":"review_unavailable"}` |
| request transport/schema is invalid | 422 | FastAPI/Pydantic validation response |

The allowlist contains only codes intentionally admitted to the browser contract. A future internal `EmailWritingReviewServiceError` code is not automatically public: unknown values collapse to `review_unavailable`. This prevents a later lower-level error string from becoming browser-visible merely because it was wrapped in the service error type.

The endpoint does not return raw prompts, raw model/Judge output, provider credentials, source email bodies, internal exception text, or stack traces as error evidence.

## Current runtime assembly gate

Task 10 intentionally does **not** install a fake production review service. `get_email_writing_review_service()` returns no assembled runtime until the dependency-root stack is admissible. Consequently the active Draft endpoint returns `review_runtime_unavailable` by default.

This is a preparatory fail-closed boundary. It must be replaced by the admitted Task-9 service assembly only after the exact immutable `fast-mlsirm` distributable/package source, integrity digest, source provenance, Python 3.14 compatibility and Naruon hash lock are verified and the current Judge/policy/service lineage is reconstructed from those immutable inputs.

Tests inject a review service through FastAPI dependency overrides solely to exercise the real HTTP transport contract. That test seam is not a production semantic fallback.

## No lexical semantic fallback

The transport may deterministically validate authorization, request/schema bounds, revision/hash identity, selector bounds, Unicode and safety constraints. It must not decide spelling, grammar, clarity, concision, tone, workplace pragmatics, audience fit, technical precision, actionability or intent preservation from keywords, regular expressions, phrase lists, sender domains, recipient counts, language names, sentiment tables, nearest-text search or text position.

Provider/model/Judge failure or insufficient evidence therefore produces abstention or review unavailability rather than a lexical substitute.

## Verification contract

Task-10 acceptance requires current-head evidence for:

- authenticated scope and database-session pass-through to Task 9;
- advisory response preservation;
- stable redacted 404/403/503 error mapping;
- unknown internal service-code masking;
- OpenAPI declaration of the bounded 403/404/503 error envelope;
- fail-closed unassembled runtime;
- invalid request rejection before service execution;
- exactly one registered production POST route;
- Python 3.14;
- 100% statement and branch coverage for the Task-10 production module;
- public docstrings, Ruff and compile checks;
- every then-live repository/organization security, dependency, package, SBOM, provenance and review requirement before integration.

Queued, pending, skipped-required, cancelled, absent, neutral, failed, stale, predecessor, synthetic, model-only, status-only or author-only evidence is not passing.

## Integration order

The canonical runtime order is:

```text
Candidate Reviewer
→ independent Judge
→ immutable fast-mlsirm dependency admission
→ calibrated publication/admission policy
→ review service
→ review API
→ immutable Inkspan consumer
→ EmailDetail composer
→ feedback / benchmark / live evaluation
→ protected release
```

If an earlier predecessor moves or is reconstructed, this active API branch must be ordinarily restacked/reconstructed from the new exact predecessor and regenerate all head-sensitive evidence. Predecessor checks and reviews do not transfer.
