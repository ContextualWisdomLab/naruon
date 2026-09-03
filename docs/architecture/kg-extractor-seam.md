# Semantic project-graph extractor seam

Status: implemented seam; LLM-backed execution is intentionally unavailable until a released contextual-orchestrator consumer contract can be consumed.

The runnable contract lives in [`backend/services/project_graph/extractor_registry.py`](../../backend/services/project_graph/extractor_registry.py). This note describes the product boundary and must stay aligned with that module and ADR-0005.

## Problem

The semantic project graph (`project_graph_objects` / `project_graph_edges`, cited back to `content_segments`) is populated by named, versioned extractors. A stable registry is useful only if selection and fallback semantics remain truthful. In particular, a request for LLM-backed extraction must not silently return keyword-derived output, and Naruon must not become a second provider/model router beside contextual-orchestrator.

The earlier implementation violated both constraints: LLM-backed selectors could fall through to the deterministic keyword extractor, while Naruon carried direct-provider model/base-URL authority and later attempted to choose an orchestrator pool/model itself. PR #1525 removes those authorities rather than hiding them behind configuration.

## Contract

`KgExtractor` is a typed, named and versioned `Protocol` with an explicit capability-fallback declaration:

```python
class KgExtractor(Protocol):
    name: str
    version: str
    requires_llm_capability: bool

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult: ...
```

`name` and `version` are persisted as extractor provenance. `requires_llm_capability` is mandatory: a plugin that omits it fails loudly during chain resolution instead of inheriting an accidental fallback policy.

`KgExtractorContext` is intentionally fieldless while there is no immutable contextual-orchestrator consumer contract. It carries no provider credential, raw contextual-orchestrator URL, provider/model id, group, pool, or compatibility diagnostic. Future LLM-backed enablement must add only inputs defined by a released owner contract rather than reviving Naruon-owned transport or routing fields.

## Selector and fallback semantics

The selector contract is explicit:

| `PROJECT_GRAPH_EXTRACTOR` | Resolution | Failure behavior |
| --- | --- | --- |
| `keyword` | deterministic keyword extractor only | propagates its own failure |
| `llm` | direct-provider LLM extractor only | always unavailable by policy; no keyword substitution |
| `orchestrator` | contextual-orchestrator capability placeholder only | unavailable until a released owner contract exists; no keyword substitution |
| unknown value | no extractor | `ExtractorUnavailableError`; no implicit keyword mode |

The deterministic keyword extractor is therefore an intentional non-LLM product mode, not a rescue path for an unavailable LLM capability. For future non-LLM plugins that explicitly set `requires_llm_capability = False`, the registry may append the deterministic extractor as a fallback. LLM-backed extractors set it to `True`, so their chain contains only the requested extractor and `run_extraction` propagates errors.

This distinction is load-bearing. It prevents a tenant/operator from selecting `llm` or `orchestrator` and receiving persisted keyword-derived graph objects that appear to be evidence of successful LLM extraction.

## LLM authority boundary

### Direct-provider selector

`PROJECT_GRAPH_EXTRACTOR=llm` remains registered for configuration compatibility but is disabled by policy. `LlmGroundedExtractor.extract()` raises `ExtractorUnavailableError` before reading credentials, endpoint, or model data when `routed_via_orchestrator` is false.

Naruon does not own production LLM provider/model routing. Re-enabling this path would recreate a second routing authority and requires a new accepted architecture decision; credentials or a reachable provider endpoint are not sufficient justification.

### contextual-orchestrator selector

`PROJECT_GRAPH_EXTRACTOR=orchestrator` is a fail-closed capability placeholder. It does not target a locally configured raw endpoint, pass an embedding-provider credential, select a provider/model/group/pool, or invoke Naruon's standalone `extract_project_semantics_llm(...)` transport.

As recorded by ADR-0005 and PR #1525, no released contextual-orchestrator consumer contract is currently available for this path. Naruon therefore has no legitimate transport/client/schema to execute against and reports the capability as unavailable. A raw URL, tenant provider key, literal provider model, or virtual pool id is not a substitute for a versioned owner contract.

When contextual-orchestrator publishes an immutable consumer release, enabling this path requires a separate consumer change that pins that release, maps its versioned request/response schema through an ACL, regenerates exact-head contract/E2E/security evidence, and adds only contract-defined capability inputs. A mutable branch/head is not a dependency contract.

## Import behavior

Failing project-graph extraction does not fail email import. `_persist_project_graph_projection` already treats projection as best-effort at the higher application layer and catches extraction failures. The truthful behavior is therefore:

1. persist/import the email according to the normal mail contract;
2. attempt only the extractor explicitly selected;
3. if an LLM-backed capability is unavailable or fails, omit that graph projection and retain failure evidence/logging;
4. never replace it with keyword-derived output under the LLM selector.

Explicit `keyword` mode remains available for tenants/operators that intentionally choose deterministic lexical extraction.

## Grounding invariant

Extractor selection does not weaken grounding. Every emitted object must cite input `content_segment_uid` values; LLM extraction validates cited segments and relation grounding; persistence re-validates segment scope before storing the graph. Extractor name/version provenance remains attached to persisted objects and edges.

The seam changes *which implementation may run*, not the citation or tenant-scope contract.

## Configuration

- `PROJECT_GRAPH_EXTRACTION_ENABLED` — gates project-graph projection.
- `PROJECT_GRAPH_EXTRACTOR` — explicit selector: `keyword`, `llm`, or `orchestrator`; unknown values fail closed.

There is deliberately no project-graph-specific contextual-orchestrator URL, provider credential, model, group, or pool setting. Those are owner-contract concerns, not Naruon runtime configuration.

## Verification contract

The regression suite must prove at least these behaviors:

- explicit `keyword` selection resolves only the deterministic extractor;
- `llm` direct-provider mode is unconditionally unavailable;
- `orchestrator` mode fails closed while the released owner contract is absent;
- the context and import caller expose no raw URL/provider-key/model compatibility seam;
- failures from either LLM-backed selector propagate rather than falling through to keyword extraction;
- unknown selector values fail closed;
- plugins must explicitly implement `requires_llm_capability`;
- grounding/provenance invariants remain unchanged;
- the higher-level email import survives projection failure without fabricating a substitute graph.

Relevant tests are in `backend/tests/test_project_graph_extractor_registry.py`, `backend/tests/test_project_graph_llm_extractor.py`, `backend/tests/test_project_graph_orchestrator_boundary.py`, `backend/tests/test_project_graph_extractors.py`, `backend/tests/test_project_graph_import_wiring.py`, and `backend/tests/test_project_graph_projection.py`.

## Traceability and grounding

- `docs/adr/0005-kg-extraction-orchestrator-free-pool-pin.md` — decision history for provider/model authority, fail-closed LLM selectors, and contextual-orchestrator release dependency.
- `docs/doctoring/project-graph-orchestrator-consumer-boundary.md` — exact repair lineage and live owner-release observation.
- `docs/planning/naruon-platform-plan.md` — `kg.extractor` extension point and the dense project-graph roadmap. Historical language about deterministic fallback does not override the current truthfulness invariant for an explicitly requested LLM capability.
- Pan, S., Luo, L., Wang, Y., Chen, C., Wang, J., & Wu, X. (2024). Unifying large language models and knowledge graphs: A roadmap. *IEEE Transactions on Knowledge and Data Engineering*. https://doi.org/10.1109/TKDE.2024.3352100 — grounding for LLM/KG construction; it does not assign provider-routing authority to Naruon.
- Necula, S.-C., Păvăloaia, V.-D., Strîmbei, C., & Dospinescu, O. (2024). Enhancement of natural language processing approaches for requirements engineering: A systematic literature review. *Electronics, 13*(11), 2055. The redistribution-permitted in-repo reference, when present under `docs/papers/`, is supporting research rather than an executable contract.

Code, ADR, this architecture note, PR metadata, and tests must agree before #1525 can be considered merge-ready. Predecessor-head review/check evidence does not transfer after a documentation commit.
