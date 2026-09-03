# Project-graph contextual-orchestrator consumer boundary

## Finding

Naruon's project-graph extractor registry retained three authority-bearing values in `KgExtractorContext`: a provider `api_key`, a raw contextual-orchestrator base URL, and an `orchestrator_model`. The orchestrator selector could therefore reach the local OpenAI-compatible `extract_project_semantics_llm(...)` transport when those values were populated. This was a dormant second routing authority even though the selector currently failed earlier because no model was supplied.

The canonical owner check on 2026-09-04 found no GitHub Releases for `ContextualWisdomLab/contextual-orchestrator`. Naruon therefore has no immutable released consumer API/client/schema to bind to and must fail closed rather than treating a raw URL, tenant provider credential, provider/model name, group, or virtual pool as a substitute.

## Decision

`KgExtractorContext` no longer has provider, credential, URL, model, group, or pool fields. During this open-PR migration its constructor still accepts the predecessor keyword arguments so older callers cannot break the explicit non-LLM `keyword` mode; the supplied values are discarded immediately and are not retained. Only a boolean diagnostic noting whether the predecessor caller had configured an endpoint is kept, and it has no routing authority.

`LlmGroundedExtractor.extract()` no longer invokes the local raw LLM transport. Direct-provider mode remains policy-disabled. Orchestrator mode reports either an unconfigured endpoint or an unavailable released consumer contract and never falls back to the keyword extractor. The local grounded extractor implementation remains testable as a standalone pure project-graph transformation seam but is not reachable from production selector routing.

The compatibility constructor is temporary. A later source cleanup in this same lane should remove the dead `PROJECT_GRAPH_ORCHESTRATOR_BASE_URL` setting and stop `email_import_service` from passing embedding-provider credentials into `KgExtractorContext`; those values are already non-authoritative at runtime after this repair. They must not become live again before an immutable contextual-orchestrator consumer release exists.

## RED → repair evidence

- RED: `c560296c5c932e81c924612d0dc82ebb41799148` added executable assertions that the project-graph context must not expose provider-routing fields and that orchestrator selection must have no local raw LLM call path.
- Repair: direct non-force successor replaces the authority-bearing context with a fieldless compatibility boundary and makes both LLM-backed selector paths fail closed before any raw transport call.
- Exact-head hosted CI/security/review evidence remains mandatory. Predecessor checks or reviews do not transfer across these commits.

## Traceability

Owner boundary: `ContextualWisdomLab/contextual-orchestrator` released API/client/schema. Current release inventory observed 2026-09-04: empty. Naruon source path: `backend/services/project_graph/extractor_registry.py`. Regression paths: `backend/tests/test_project_graph_extractor_registry.py` and `backend/tests/test_project_graph_orchestrator_boundary.py`.
