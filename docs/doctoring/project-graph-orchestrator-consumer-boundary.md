# Project-graph contextual-orchestrator consumer boundary

## Finding

Naruon's project-graph extractor registry retained three authority-bearing values in `KgExtractorContext`: a provider `api_key`, a raw contextual-orchestrator base URL, and an `orchestrator_model`. The orchestrator selector could therefore reach the local OpenAI-compatible `extract_project_semantics_llm(...)` transport when those values were populated. This was a dormant second routing authority even though the selector currently failed earlier because no released owner contract existed.

A fresh canonical-owner check on 2026-09-04 found no GitHub Releases for `ContextualWisdomLab/contextual-orchestrator`. Naruon therefore has no immutable released consumer API/client/schema to bind to and must fail closed rather than treating a raw URL, tenant provider credential, provider/model name, group, or virtual pool as a substitute.

## Decision

`KgExtractorContext` is now fieldless and has no legacy compatibility constructor. It accepts no provider credential, URL, model, group, pool, or endpoint-diagnostic input. `LlmGroundedExtractor.extract()` cannot invoke the local raw LLM transport: direct-provider mode is policy-disabled, while orchestrator mode reports the missing released consumer contract and never falls back to keyword extraction.

The import application boundary now constructs `KgExtractorContext()` with no embedding-provider data, and the project-graph projection call no longer accepts or forwards `EmailImportEmbeddingProvider`. `backend/core/config.py` no longer exposes `PROJECT_GRAPH_ORCHESTRATOR_BASE_URL`. Email embeddings remain a separate concern and retain their existing provider/batch path; they cannot leak credentials or transport configuration into project-graph semantic extraction.

The local grounded extractor implementation remains independently testable as a pure project-graph transformation seam, but production selector routing cannot reach it until an immutable contextual-orchestrator consumer release supplies a versioned client/schema contract.

## RED → repair evidence

- RED `8ff3e35a2a0fffce460e7bc400d6a12585feb3d1`: executable regression requires a zero-argument, authority-free `KgExtractorContext` and rejects the legacy raw URL / embedding-provider caller seam.
- Runtime repair `f41d9ed47d45c5f645f6da767e9862b35aa07404`: removes the compatibility constructor and endpoint diagnostic from `KgExtractorContext`; orchestrator selection now has only the released-contract fail-closed state.
- Config repair `040e6c0f5107a2fbfc2350999b9d5dca95e3eee0`: removes `PROJECT_GRAPH_ORCHESTRATOR_BASE_URL` from Naruon settings.
- Application repair `645f8acb83330a21adc6500ecc5a7efa6220e110`: stops passing embedding credentials or project-specific raw transport configuration into the extraction seam.
- Test repair `67d83c34c2aad296f6c8276fe9c19484fbf4e025`: aligns import-selector regression coverage with the authority-free context and removes obsolete configured/unconfigured raw-endpoint cases.
- Exact-head hosted CI/security/review evidence remains mandatory. Predecessor checks or reviews do not transfer across these commits.

## Traceability

Owner boundary: `ContextualWisdomLab/contextual-orchestrator` released API/client/schema. Fresh release inventory observed 2026-09-04: empty. Naruon source paths: `backend/services/project_graph/extractor_registry.py`, `backend/services/email_import_service.py`, and `backend/core/config.py`. Regression paths: `backend/tests/test_project_graph_extractor_registry.py`, `backend/tests/test_project_graph_llm_extractor.py`, and `backend/tests/test_project_graph_orchestrator_boundary.py`.
