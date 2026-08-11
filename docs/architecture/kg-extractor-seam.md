# Semantic project-graph extractor seam

Status: implemented (naruon#975, Phase 0 keystone bullet — "make the dense KG
real *behind a stable extractor seam*"). This note records the design and its
grounding; the runnable contract lives in
[`backend/services/project_graph/extractor_registry.py`](../../backend/services/project_graph/extractor_registry.py).

## Problem

The semantic project graph (`project_graph_objects` / `_edges`, cited back to
`content_segments`) is populated by *extractors*. Two existed — a deterministic
keyword baseline and a grounded LLM extractor — but the import pipeline chose
between them with a hardcoded branch:

```python
if settings.PROJECT_GRAPH_EXTRACTOR == "llm" and provider and provider.api_key:
    try: return await extract_project_semantics_llm(...)
    except Exception: ...        # fall back
return extract_project_semantics(...)
```

The platform plan (`docs/planning/naruon-platform-plan.md`, §7.2) names a
`kg.extractor` extension point — "register a named + versioned entity/relation
extractor" — as one of only two seams the plugin kernel will generalize, and
§8.2 flags "make the dense KG real behind a stable extractor seam" as the Phase 0
keystone. A hardcoded `if/else` is not that seam: a third extractor (or a
plugin) cannot be selected without editing core ingest, and the
"rule-based extraction is fallback/reference only" discipline is an ad-hoc branch
rather than a structural guarantee. naruon#975 asks specifically to *"establish
the pluggable extractor/plugin seam and route the real LLM-based
language-agnostic extraction through contextual-orchestrator; current rule-based
extraction is fallback/reference only."*

## Design

### The contract

`KgExtractor` is a typed, named + versioned `Protocol`:

```python
class KgExtractor(Protocol):
    name: str
    version: str
    async def extract(
        self, segments: list[ProjectSourceSegment], *, context: KgExtractorContext
    ) -> ProjectSemanticExtractionResult: ...
```

`name`/`version` are recorded as per-row provenance on the objects and edges an
extractor emits (`project_graph_objects.extractor_name` / `.extractor_version`),
so every node in the graph is attributable to the extractor and version that
produced it. `extract` is always awaited so pure/deterministic and LLM-backed
extractors compose uniformly. `KgExtractorContext` is a small, provider-agnostic
carrier (`api_key`, `base_url`, `model`, `orchestrator_base_url`) — extractors
receive exactly the resources they need, with no ambient session/settings
authority (mirroring the plan's plugin-context principle, §7.2).

### The registry and the fallback discipline

`KgExtractorRegistry` maps the stable `PROJECT_GRAPH_EXTRACTOR` selector value to
an extractor. `resolve_extractor_chain(selector)` returns an ordered chain whose
**terminal element is always the deterministic reference extractor**:

| selector | chain |
| --- | --- |
| `keyword` | `[deterministic]` |
| `llm` | `[llm-grounded, deterministic]` |
| `orchestrator` | `[llm-grounded (routed), deterministic]` |
| unknown / plugin-without-fallback | `[…, deterministic]` |

`run_extraction` walks the chain and returns the first success. An extractor that
hits a *recoverable precondition* (missing LLM credentials, an unconfigured
orchestrator endpoint) raises `ExtractorUnavailableError`; a genuine failure
raises anything else. Both cause the runner to advance to the next extractor.
Because the deterministic keyword extractor is pure and always produces a result,
"rule-based extraction is fallback/reference only" is guaranteed *by
construction* — not by remembering to write a fallback branch. The default
selector is grounded `orchestrator`; `keyword` must be selected explicitly for
diagnostic/reference use. The projection is best-effort and never lost.

Adding an extractor — including a future plugin on the `kg.extractor` extension
point — is now `registry.register("selector", MyExtractor())` plus a config
value; core ingest is untouched.

### Grounding invariant (unchanged, and load-bearing)

Extractors do not get to weaken grounding. Every emitted object must cite
`content_segment_uid`s that exist in the input segments
(`ProjectSemanticObject.__post_init__`), the LLM extractor drops any object with
unknown/absent citations and grounds each object-to-object relation in the union
of its endpoints' cited segments (`llm_extractor._validated_objects` /
`_relation_edges`), and the repository re-validates that every cited segment is
in the caller's scope (`repository._validate_segment_scope`). The seam changes
*selection*, not the citation contract.

### Routing LLM extraction through contextual-orchestrator

contextual-orchestrator is the org's LLM cost/routing hub. naruon already treats
every LLM provider as OpenAI-compatible (it builds an `AsyncOpenAI` client against
any provider `base_url` through the SSRF-guarded
`build_llm_provider_http_client`). Routing extraction "through the orchestrator"
is therefore a *transport* choice, not a new bespoke API: the `orchestrator`
selector runs the **identical** grounded LLM extractor but points its client at
`PROJECT_GRAPH_ORCHESTRATOR_BASE_URL` (the orchestrator's OpenAI-compatible
endpoint) instead of the raw provider. Constraints:

- The orchestrator base URL must be HTTPS and exact-host allowlisted by
  `ALLOWED_LLM_BASE_URL_HOSTS`; the egress guard pins the resolved global address
  (DNS-rebinding safe). An unset or rejected endpoint raises
  `ExtractorUnavailableError` → deterministic fallback (fail closed).
- The provider API key stays the tenant's Fernet-encrypted credential; only the
  routing target changes.

This deliberately reuses the OpenAI chat/structured-output contract the merged
`llm` extractor already speaks, so the orchestrator path is no more speculative
than the direct path. It contrasts with the *batch embedding* path
(`batch_embedding_service.py`), which needed a bespoke `/v1/batch/embeddings`
contract because batching is not part of the OpenAI API; synchronous extraction
is. Follow-up (out of scope here): a dedicated per-tenant orchestrator
extraction endpoint + token in Fernet `tenant_configs` (mirroring the batch
fields) if the orchestrator authenticates extraction separately from the tenant
provider key, reconciled cross-repo the way batch routing was with
contextual-orchestrator (see naruon#973).

## Configuration

- `PROJECT_GRAPH_EXTRACTION_ENABLED` (default `false`) — gates whether ingest
  snapshots segments for projection at all.
- `PROJECT_GRAPH_EXTRACTOR` (default `orchestrator`) — `keyword` | `llm` |
  `orchestrator`.
- `PROJECT_GRAPH_ORCHESTRATOR_BASE_URL` (default unset) — OpenAI-compatible
  orchestrator endpoint for `orchestrator` routing; HTTPS + allowlisted.

## Grounding

- **Platform plan** `docs/planning/naruon-platform-plan.md` — §7.2 (the
  `kg.extractor` extension point; extractors emit *candidates* with confidence
  and cited segments, the kernel commits provenance), §7.3 ("LLM-based
  entity/relation extraction … replaces today's deterministic rule extractor;
  deterministic rules remain as a cheap first pass / offline-deterministic test
  fallback"), §8.2 (the Phase 0 keystone).
- **LLM + knowledge-graph construction.** S. Pan, L. Luo, Y. Wang, C. Chen,
  J. Wang, X. Wu, *"Unifying Large Language Models and Knowledge Graphs: A
  Roadmap"* (arXiv:2306.08302; IEEE TKDE 2024) — the canonical survey of
  LLM-driven KG construction (entity/relation extraction) with the human-in-the-
  loop, provenance-carrying discipline this seam implements. (Source PDF
  `https://arxiv.org/pdf/2306.08302`; not mirrored into `docs/papers/` here
  because this environment's network policy denies arxiv egress — the citation
  stands as the external reference.)
- **Requirements extraction from natural language** — the in-repo
  `docs/papers/nlp-in-software-requirements-engineering-slr.pdf` (Necula et al.,
  *Electronics* 2024) grounds extracting requirements/issues/features from email
  threads, which is what the project-graph objects are.
- **Orchestrator-as-routing-hub** — the in-repo `docs/papers/` routing set
  (FrugalGPT, RouteLLM, Hybrid LLM) grounds sending LLM work through a
  cost/routing hub rather than hard-wiring a provider per caller, the pattern the
  `orchestrator` selector extends from embeddings to extraction.

## Tests

- `backend/tests/test_project_graph_extractor_registry.py` — the contract
  (Protocol conformance, name/version provenance), chain resolution
  (deterministic always terminal; unknown selectors and plugin registrations
  still fall back), `run_extraction` degradation (primary success, failure
  fall-through, missing-credential fall-through), and orchestrator routing
  (targets the orchestrator base URL; fails closed when unconfigured).
- `backend/tests/test_project_graph_llm_extractor.py` — the import selector now
  resolves through the registry (`keyword` / `llm` / `orchestrator` / fallback).
- The grounding invariant and persistence remain covered by the existing
  `test_project_graph_llm_extractor.py`, `test_project_graph_extractors.py`,
  `test_project_graph_import_wiring.py`, and `test_project_graph_projection.py`.
