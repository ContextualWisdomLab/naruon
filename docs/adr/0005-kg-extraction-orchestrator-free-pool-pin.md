# ADR-0005: Pin orchestrator-routed KG extraction to the `orchestrator/free` pool

> The filename and title are retained for stable cross-references. The original
> pinning decision was reversed before merge. The current decision is **not** to
> pin or select any contextual-orchestrator provider/model/group/pool in Naruon.

**Status:** Proposed  
**Date:** 2026-09-02  
**Last revised:** 2026-09-04 (Revision 10)  
**Decision owner:** Naruon maintainers  
**Scope:** `backend/services/project_graph/extractor_registry.py`, the email-import
project-graph caller, and project-graph-specific runtime configuration. The separate
batch-embedding path is outside this ADR.

## Problem

Naruon's project-graph extraction seam originally allowed two LLM-backed routes:
a direct-provider selector and a contextual-orchestrator selector. The latter reused
Naruon's local OpenAI-compatible transport, tenant provider credential, raw gateway
URL, and model input. Early versions of this ADR attempted to make that route safer
by hardcoding `orchestrator/free`.

That was the wrong ownership boundary. Contextual-orchestrator owns provider/model/
group/pool discovery and routing. Naruon owns project-graph domain semantics,
grounding, persistence, selector intent, and truthful capability availability. A
consumer-side pool hardcode, raw gateway URL, tenant provider key, or literal model
is not a substitute for a released contextual-orchestrator API/client/schema.

A fresh owner check on 2026-09-04 returned an empty GitHub Release inventory for
`ContextualWisdomLab/contextual-orchestrator`. There is therefore still no immutable
consumer contract that this product-runtime path can pin and consume.

A second defect compounded the ownership problem: LLM-backed selectors could fall
through to deterministic keyword extraction. That changed the requested algorithm
while presenting the result as a successful semantic projection. The keyword
extractor is a valid explicit non-LLM mode, but it cannot masquerade as an LLM result.

## Constraints

- Naruon remains the canonical owner of project-graph domain truth and grounding.
- Contextual-orchestrator remains the canonical owner of LLM provider/model/group/
  pool routing.
- Product runtime may consume only a released, immutable owner contract; mutable
  branches, raw URLs, or copied source are not contracts.
- `PROJECT_GRAPH_EXTRACTOR=keyword` is an explicit deterministic product mode.
- `llm` and `orchestrator` selectors must fail closed when the requested LLM
  capability cannot execute; they must not substitute keyword output.
- Email import is allowed to succeed when best-effort graph projection is absent.
- Existing standalone grounded-extractor tests may remain as pure transformation
  tests; production selector routing must not reach that raw transport.

## Current decision

### 1. Keep explicit selector identities

`PROJECT_GRAPH_EXTRACTOR` recognizes:

- `keyword`: deterministic non-LLM extraction;
- `llm`: retained for configuration compatibility but policy-disabled;
- `orchestrator`: retained as the future contextual-orchestrator capability seam,
  currently unavailable pending a released owner contract.

Unknown selectors raise `ExtractorUnavailableError`; they never default to keyword.

### 2. Make LLM fallback semantics structural

`KgExtractor.requires_llm_capability` is mandatory. LLM-backed extractors set it to
`True`, so their resolution chain contains only the requested extractor. A failed or
unavailable LLM request therefore propagates its real failure instead of falling
through to keyword extraction. Non-conforming plugins fail loudly rather than
inheriting a permissive default.

### 3. Remove Naruon-owned LLM routing authority from this seam

`KgExtractorContext` is fieldless. It has no provider credential, raw
contextual-orchestrator URL, provider/model id, group, pool, or legacy endpoint
signal. Its constructor accepts no predecessor compatibility arguments.

`LlmGroundedExtractor.extract()` does not invoke the local
`extract_project_semantics_llm(...)` transport. Direct-provider mode raises a
policy-disabled error. Orchestrator mode raises a released-contract-unavailable
error until a real owner release can be consumed.

`backend/services/email_import_service.py` constructs `KgExtractorContext()` with no
embedding-provider data. The project-graph projection call no longer accepts or
forwards `EmailImportEmbeddingProvider` solely for semantic-extractor routing.
Email embedding generation remains a separate path and is not changed by this ADR.

`backend/core/config.py` no longer defines
`PROJECT_GRAPH_ORCHESTRATOR_BASE_URL`. A project-specific raw gateway setting would
recreate the transport authority this ADR removes.

### 4. Future enablement requires an immutable owner contract

When contextual-orchestrator publishes a suitable immutable release, a separate
consumer change must:

1. pin the released API/client/schema version;
2. adapt request/response data through a Naruon ACL while preserving project-graph
   grounding and provenance;
3. pass capability/privacy/price/latency requirements rather than choosing a
   provider/model/group/pool locally;
4. generate exact-head API-schema, behavioral, security, SBOM/provenance, and E2E
   evidence;
5. keep absence/incompatibility fail-closed.

No mutable owner head, hardcoded `orchestrator/free`, raw provider model, or manual
URL setting is an acceptable interim implementation.

## Revision history

The revisions below occurred within the still-open PR and are preserved as decision
history, not as current runtime instructions.

- **Original through Revision 3:** attempted to route the orchestrator selector
  through Naruon's raw OpenAI-compatible transport and hardcode
  `orchestrator/free`; review iterations fixed missing/blank/whitespace model gates.
- **Revision 7 (2026-09-02):** identified the consumer-side pool hardcode as an
  ownership violation and removed `ORCHESTRATOR_POOL_MODEL`; introduced a distinct
  orchestrator-model concept while awaiting an owner release.
- **Revision 8 (2026-09-02):** stopped LLM-backed selectors from silently degrading
  to keyword output and policy-disabled direct-provider project-graph routing.
- **Revision 9 (2026-09-02):** made unknown selectors fail closed and made
  `requires_llm_capability` an enforced extractor protocol requirement rather than
  an optional registry convention.
- **Revision 10 (2026-09-04):** completed the boundary repair. A RED regression at
  `8ff3e35a2a0fffce460e7bc400d6a12585feb3d1` required a zero-argument,
  authority-free context and removal of the legacy raw-configuration caller seam.
  The subsequent non-force lineage removed the compatibility constructor
  (`f41d9ed47d45c5f645f6da767e9862b35aa07404`), removed the raw project-graph
  orchestrator URL setting (`040e6c0f5107a2fbfc2350999b9d5dca95e3eee0`), severed
  embedding credentials from semantic extraction routing
  (`645f8acb83330a21adc6500ecc5a7efa6220e110`), and aligned import-selector tests
  (`67d83c34c2aad296f6c8276fe9c19484fbf4e025`).

## Alternatives rejected

### Hardcode `orchestrator/free` in Naruon

Rejected. The virtual pool is routing policy owned by contextual-orchestrator. The
fact that centrally governed GitHub Actions workflows may use an explicitly
specified free route does not grant product-runtime consumers authority to duplicate
that policy.

### Make a Naruon setting default to `orchestrator/free`

Rejected. A configurable default still duplicates owner policy and can drift. It
also turns an unreleased dependency into a local configuration convention.

### Reuse `OPENAI_MODEL` or an embedding-provider model

Rejected. Those values belong to different Naruon/provider boundaries. Forwarding
them into contextual-orchestrator as a route selector would silently reintroduce
provider/model authority and couple unrelated capabilities.

### Keep a raw contextual-orchestrator URL only for transport

Rejected for the current unreleased state. Without a versioned owner client/schema,
a raw URL necessarily couples Naruon to an unversioned OpenAI-compatible transport
shape and invites credentials/model fields back into the context. Future transport
configuration must come from the released consumer contract's supported mechanism.

### Keep the legacy constructor but discard its values

Rejected in Revision 10. Although discarding values prevented immediate routing,
the callable surface still advertised credentials/URL/model as legitimate inputs and
left callers/configuration in place. Dead compatibility surface is a future
regression path, not a stable boundary.

### Remove the `orchestrator` selector entirely

Rejected as unnecessarily destructive. The selector is a stable capability identity
and can truthfully report unavailable while the owner contract is absent. Keeping the
identity avoids conflating "unknown selector" with "known but unavailable
capability."

### Degrade failed LLM extraction to keyword and only log a warning

Rejected. Logging does not repair the persisted semantic misrepresentation. A
request that selected LLM extraction must either produce LLM-backed grounded output
or report that capability unavailable.

## Consequences

- `PROJECT_GRAPH_EXTRACTOR=keyword` continues to work as the explicit deterministic
  mode.
- `PROJECT_GRAPH_EXTRACTOR=llm` always fails closed before direct-provider routing.
- `PROJECT_GRAPH_EXTRACTOR=orchestrator` fails closed while the immutable owner
  consumer contract is absent. It has no local URL/model/key workaround.
- Email import itself still succeeds because `_persist_project_graph_projection`
  treats semantic projection as best-effort and rolls back only projection work on
  failure.
- The project graph may therefore have no new projection for an email when an
  unavailable LLM selector is configured. That absence is more truthful than
  persisting keyword-derived objects under an LLM request.
- The standalone grounded-extraction core remains unit-testable, but is not a
  production transport path.
- `backend/services/batch_embedding_service.py` is deliberately not changed here.
  It is a separate embedding/batch bounded concern and requires its own owner-contract
  evidence rather than assuming the project-graph decision applies verbatim.

## Verification and traceability

Required regression evidence includes:

- `backend/tests/test_project_graph_extractor_registry.py` — selector, fallback, and
  plugin capability policy;
- `backend/tests/test_project_graph_orchestrator_boundary.py` — zero-field context,
  absent legacy config/caller seam, and no dormant raw LLM transport;
- `backend/tests/test_project_graph_llm_extractor.py` — explicit keyword behavior,
  direct-provider disable, and orchestrator fail-closed import behavior;
- `backend/tests/test_project_graph_extractor_authority_docs.py` — root and detailed
  architecture docs remain aligned with the authority boundary;
- `docs/architecture/kg-extractor-seam.md` and
  `docs/doctoring/project-graph-orchestrator-consumer-boundary.md` — code-current
  architecture and RED→repair lineage.

Exact-head hosted CI/security/review evidence is required after every push. Review or
check evidence from a predecessor head does not transfer.

## References (APA 7th)

ContextualWisdomLab. (2026). *ADR-0003: Vendored contextual-orchestrator review
sidecar with governed gateway pools* [Architecture decision record, amended
2026-08-30]. `ContextualWisdomLab/.github`.
https://github.com/ContextualWisdomLab/.github/blob/main/docs/adr/0003-contextual-orchestrator-vendored-free-zdr.md

National Institute of Standards and Technology. (2023). *Artificial intelligence
risk management framework (AI RMF 1.0)* (NIST AI 100-1). U.S. Department of
Commerce. https://doi.org/10.6028/NIST.AI.100-1

OpenRouter. (n.d.). *Data policy: Zero data retention*. Retrieved September 2,
2026, from https://openrouter.ai/docs/features/privacy-and-logging
