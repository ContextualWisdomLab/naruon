# ADR-0005: Pin orchestrator-routed KG extraction to the `orchestrator/free` pool

**Status:** Proposed — Revision 7 (below) reverses this ADR's original point-1/2
mechanism. The title and file identity are kept stable for cross-reference (naruon
`extractor_registry.py`, `ContextualWisdomLab/contextual-orchestrator` ADR-0007, and
`ContextualWisdomLab/.github`'s gap-baseline all cite this path); read Revision 7
before treating anything in Context/Decision points 1–3 as current behavior. This PR
(naruon#1525) has not merged, so this ADR was never more than a same-PR proposal —
"Accepted" here before Revision 7 was itself a premature status marking, corrected
per `ContextualWisdomLab/.github` `docs/product-goal-directive.md`'s repair-not-close
PR-lifecycle policy.
**Date:** 2026-09-02
**Decision owner:** Naruon maintainers
**Scope:** `backend/services/project_graph/extractor_registry.py::LlmGroundedExtractor` when
`routed_via_orchestrator=True` (the `PROJECT_GRAPH_EXTRACTOR=orchestrator` selector).
This ADR does not change the direct-provider `PROJECT_GRAPH_EXTRACTOR=llm` path, and
it does not cover `backend/services/batch_embedding_service.py`'s separate orchestrator
batch-embedding call site (see Consequences).

## Context

Naruon can route project-graph KG extraction through the
[`contextual-orchestrator`](https://github.com/ContextualWisdomLab/contextual-orchestrator)
gateway instead of a direct LLM provider: `LlmGroundedExtractor._resolve_base_url`
already swaps the HTTP target to `context.orchestrator_base_url` when
`routed_via_orchestrator` is set, keeping the request otherwise identical
(same OpenAI-compatible client, same grounded extraction core).

What that swap did **not** do, before this ADR, is change which `model` string the
request carries. `extract()` always sent `context.model`, which
`backend/services/email_import_service.py::_extract_project_semantics_for_import` sets to
`settings.OPENAI_MODEL` — naruon's general-purpose direct-provider model setting —
for both the direct and orchestrator-routed cases alike, because `KgExtractorContext`
is built once per import and handed to `run_extraction()` regardless of which
selector ends up choosing it.

That is a real product gap, not a hypothetical: `ContextualWisdomLab/.github`'s
[ADR-0003](https://github.com/ContextualWisdomLab/.github/blob/main/docs/adr/0003-contextual-orchestrator-vendored-free-zdr.md)
establishes that the orchestrator gateway does not treat every `model` value as a
literal pass-through provider id. It also recognizes a small set of fixed
**virtual pool ids** — `orchestrator/free` and `orchestrator/auto` — that it
resolves itself, at request time, to a concrete discovered provider route chosen
by its own governed policy (zero-cost-first, Zero Data Retention (ZDR)-prioritized
for `free`; a wider evidence-tiered catalog for `auto`, restricted to callers with
an accepted price-attestation exception). Sending a literal provider model id
instead of one of these pool ids does not "opt out" of pool governance safely — it
asks the gateway to proxy that specific model directly, bypassing the free/ZDR
policy entirely, with no code-level signal that the bypass happened. Naruon's own
`docs/adr/` had no decision governing this at all before this ADR: an audit of
`backend/` found zero occurrences of a pool id, a `CONTEXTUAL_ORCHESTRATOR_POOL`-style
setting, or any orchestration-mode parameter anywhere in the runtime code — every
orchestrator-routed call implicitly inherited whatever `settings.OPENAI_MODEL`
happened to be configured as for the unrelated direct-provider path.

The org's own operating directive (`ContextualWisdomLab/.github`
`docs/product-goal-directive.md`, §8) already commits every LLM-routing
consumer in the ecosystem to auto-discovery through `contextual-orchestrator`,
and ADR-0003's 2026-08-30 amendment already moved all three central CI review
consumers (OpenCode, Noema, and — reversing that ADR's original `orchestrator/auto`
choice — Strix) onto the fixed `orchestrator/free` id specifically so that CI
review traffic cannot silently drift onto a paid or non-ZDR route through a
misconfigured setting. Naruon's own product traffic through the same gateway had
no equivalent guarantee. Given naruon's foundational data-sovereignty commitment
(`docs/CWL-MASTER-CONTEXT.md` §2: "stores only metadata + AI-extracted intent +
task state" over customer-owned data), a ZDR-first routing guarantee for
orchestrator-routed KG extraction is at least as important for naruon's own
production traffic as it is for CI review of source code — arguably more so,
since KG extraction runs over real customer email content, not code.

## Decision

1. `LlmGroundedExtractor` gains a `_resolve_model()` method, symmetric to its
   existing `_resolve_base_url()`: when `routed_via_orchestrator` is `True`, it
   returns the fixed constant `ORCHESTRATOR_POOL_MODEL = "orchestrator/free"`
   instead of `context.model`. The direct-provider path (`routed_via_orchestrator
   = False`) is unchanged and keeps using `context.model` exactly as before.
2. `ORCHESTRATOR_POOL_MODEL` is a module-level constant in
   `extractor_registry.py`, not a `Settings` field. This mirrors
   `.github/workflows/strix.yml`'s own hardcoded
   `CONTEXTUAL_ORCHESTRATOR_POOL: free` (ADR-0003's 2026-08-30 amendment):
   the whole point of pinning is that an operator cannot accidentally route
   production KG-extraction traffic onto a non-free, non-ZDR-guaranteed pool
   by misconfiguring (or omitting) an environment variable. If a future,
   evidence-backed need for `orchestrator/auto` (or a priced fallback) emerges
   for naruon's own traffic, it needs its own ADR amendment, the same way
   Strix's `orchestrator/auto` choice needed ADR-0003 §"2026-08-30 amendment"
   to change — not a silent settings-default change.
3. This ADR only fixes the KG-extraction call site. It does not touch the
   direct-provider `PROJECT_GRAPH_EXTRACTOR=llm` selector (customers who point
   naruon straight at their own OpenAI-compatible endpoint keep full control of
   the model they configured), and it does not touch
   `backend/services/batch_embedding_service.py::_run_orchestrator_batch` (see
   Consequences).
4. **Revision (same PR, pre-merge):** `extract()`'s original availability
   check, `KgExtractorContext.has_llm_credentials` (`bool(self.api_key and
   self.model)`), required `context.model` unconditionally — including for
   orchestrator-routed requests, where `_resolve_model()` never reads
   `context.model` at all. That meant a fully valid orchestrator request
   (api key present, orchestrator endpoint configured) would still raise
   `ExtractorUnavailableError` and silently degrade to the deterministic
   keyword extractor whenever `context.model` (naruon's *unrelated*
   direct-provider model setting) happened to be unset — the same class of
   bug §Context describes, just one layer deeper. Devin Review caught this in
   review of this ADR's own PR (ContextualWisdomLab/naruon#1525) before merge.
   Fixed by removing `has_llm_credentials` and having `extract()` check
   `context.api_key` directly, then treat a `None` result from
   `_resolve_model()` (only reachable in direct-provider mode; orchestrator
   mode always returns the fixed `ORCHESTRATOR_POOL_MODEL`) as the
   unavailable case instead. `orchestrator_base_url` unavailability is still
   caught by `_resolve_base_url()`, unchanged.
5. **Revision 2 (same PR, pre-merge):** the point-4 fix initially gated on
   `model is None`, which a blank (empty-string, non-`None`) `context.model`
   passes straight through — sending an invalid empty-string model id to the
   direct provider and only discovering the problem after a failed network
   round-trip, rather than failing closed to the keyword extractor up front.
   Devin Review caught this too, in the same PR. Fixed by checking `not
   model` instead of `model is None`, which rejects both `None` and `""`
   while still accepting the fixed `ORCHESTRATOR_POOL_MODEL` string
   orchestrator mode always supplies.
6. **Revision 3 (same PR, pre-merge):** revision 2's `not model` gate still
   let a whitespace-only `context.model` (`"   "`) through, since a
   non-empty string of only spaces is truthy — sending that as an invalid
   model id to the direct provider and only discovering the problem after a
   failed network round-trip, the same failure mode revision 2 fixed for
   the empty-string case. Devin Review caught this too, one round after the
   blank-string fix. Fixed by checking `not model or not model.strip()`,
   which rejects `None`, `""`, and whitespace-only strings alike while
   still accepting `ORCHESTRATOR_POOL_MODEL` (a non-whitespace literal).
7. **Revision 7 (2026-09-02, owner-directed correction) — reverses points 1–2.**
   The org owner reviewed this PR's exact head (`badf985e`) directly and
   identified that decision points 1–2 above are themselves a boundary
   violation, not a fix: hardcoding `ORCHESTRATOR_POOL_MODEL =
   "orchestrator/free"` inside naruon's own `LlmGroundedExtractor` gives
   naruon product-runtime code the same provider/model/pool selection
   authority `ContextualWisdomLab/.github`
   `docs/product-goal-directive.md` §8 explicitly reserves for
   contextual-orchestrator's released API/client/schema — "LLM Provider
   group 이름을 코드·설정·테스트·라우팅 조건에 하드코딩하지 않는다." The
   `.github` ADR-0003 precedent this ADR's Context/point-2 cited as
   justification governs a different boundary: it pins **GitHub Actions
   model-backed CI workflows** (Strix/OpenCode/Noema), which
   `docs/product-goal-directive.md`'s own item 10 scopes explicitly to
   "GitHub Actions Workflow 이용" — it was never a license for a product
   **runtime** service to make the same hardcoded choice on its own
   consumers' behalf. Naruon's role per the directive's Core-foundation map
   is a **consumer** of contextual-orchestrator, not a co-owner of its
   routing policy; a consumer's job is to pass capability/privacy/ZDR
   requirements to the owner's released contract and fail closed if the
   owner is immature or the capability is unsupported, never to duplicate
   the owner's selection logic locally (§9).

   That immaturity is not hypothetical here: as of 2026-09-03, `GET
   /repos/ContextualWisdomLab/contextual-orchestrator/releases` returns an
   empty list — there is no immutable released consumer contract for
   naruon to conform to yet, for `orchestrator/free` or any other pool
   value. Per the directive's boundary rule ("guard the boundary with
   ports/ACL/feature-flags/test-doubles and never read the owner's
   source/DB/temp branches directly" until a release exists), the correct
   interim state is that orchestrator-routed KG extraction stays
   unavailable, not that it "succeeds" against a value naruon invented.

   **Corrected decision:** `ORCHESTRATOR_POOL_MODEL` is removed entirely —
   no hardcoded pool id exists anywhere in `extractor_registry.py`.
   `KgExtractorContext` gains a new field, `orchestrator_model`, kept
   strictly separate from the pre-existing `model` field (which is, and
   remains, `email_import_service.py`'s tenant direct-provider setting,
   `settings.OPENAI_MODEL` — populated unconditionally regardless of
   selector, so it must never be forwarded to the orchestrator gateway as
   a substitute). `LlmGroundedExtractor._resolve_model()` now reads
   `context.model` in direct-provider mode and `context.orchestrator_model`
   in orchestrator mode, forwarding whichever verbatim — the extractor
   itself picks nothing. No caller populates `orchestrator_model` today,
   so orchestrator-routed extraction correctly and unconditionally fails
   closed to the deterministic keyword fallback, exactly like a missing
   credential does. This is not a regression from points 1–2's
   "`orchestrator/free` always succeeds" behavior; that behavior was the
   defect. When contextual-orchestrator ships its first release defining a
   real consumer contract, the follow-up work is entirely in
   `email_import_service.py` (resolve `orchestrator_model` from that
   contract) — `extractor_registry.py` needs no further change, because it
   was never supposed to own this decision.

## Alternatives rejected

**The three entries immediately below predate Revision 7 and evaluate the
original (now-reversed) "hardcode `orchestrator/free` in naruon" design; kept
as historical record, not current guidance. Revision 7's own alternatives
follow in a separate subsection.**

### Leave the model configurable via a new settings field, defaulted to `orchestrator/free`

Rejected. A configurable-with-a-safe-default field can still be misconfigured
away from the safe default, and nothing in the request path would catch that —
exactly the failure mode ADR-0003's Strix amendment already rejected for CI
review traffic ("fails closed on any other value"). A hardcoded constant is the
only design where the pin cannot silently regress.

### Keep sending `context.model` (status quo)

Rejected — this is the bug this ADR fixes, not a real alternative: it sends
naruon's direct-provider model id to a gateway that does not treat arbitrary
model strings as literal routing directives for orchestrator-mode requests
the way the direct-provider client does, defeating the reason to route through
the orchestrator at all.

### Pin to `orchestrator/auto` instead of `orchestrator/free`

Rejected. ADR-0003 restricts `orchestrator/auto` admission to callers with an
explicit, evidence-tiered price-attestation exception (Strix's security-analysis
use case, decided and documented there). Naruon's KG-extraction path has no such
exception, no price-attestation evidence collection, and no security-analysis
justification for admitting priced routes — `orchestrator/free`'s "zero-cost,
ZDR-first" guarantee is the correct default absent a documented reason to widen it.

### Revision 7 alternatives

#### Keep the `orchestrator/free` hardcode, just relabel it as "temporary"

Rejected. A hardcoded pool id in naruon's own code is a boundary violation
regardless of how it is labeled or how long it is meant to last — the
directive's core-foundation ownership model (`docs/CWL-MASTER-CONTEXT.md`
§9) does not have a "temporary exception" carve-out for a consumer
duplicating an owner's routing authority, and a "temporary" hardcode has no
forcing function to actually get removed once contextual-orchestrator ships.

#### Reuse `context.model` for orchestrator mode instead of adding `orchestrator_model`

Rejected. `context.model` is unconditionally `settings.OPENAI_MODEL` at
naruon's only call site (`email_import_service.py`), regardless of which
selector is active — reusing it would silently forward a tenant's
direct-provider model id to the orchestrator gateway as a pool/model
substitute, the exact bypass this ADR's original §Context already
identified as unsafe (§Context: "asks the gateway to proxy that specific
model directly, bypassing the free/ZDR policy entirely"). A dedicated field
is the only design where the two concerns cannot collide.

#### Remove the `orchestrator` selector entirely until contextual-orchestrator ships a release

Rejected as unnecessarily destructive. The registry's own architecture
(`build_default_registry`) is designed as a stable seam precisely so a
selector can exist and be structurally correct — registered, protocol-
conformant, falling back to keyword extraction like any other unavailable
extractor — before it is operationally complete. Removing the selector
would require re-adding it later with no functional difference from simply
leaving it in its current, correctly-fails-closed state now.

## Consequences

**[Superseded by Revision 7 — see the addendum below for current behavior.]**
The next two bullets describe points 1–2's reversed design and are kept as
historical record only.

- ~~`PROJECT_GRAPH_EXTRACTOR=orchestrator` now actually invokes contextual-orchestrator's
  governed free/ZDR pool selection instead of silently attempting to proxy a
  literal provider model id through it.~~ Tests:
  `test_orchestrator_routing_pins_the_free_pool_model` (implicit in the extended
  `test_orchestrator_routing_targets_the_orchestrator_base_url`) and
  `test_direct_llm_routing_uses_provider_base_url`'s extended model assertion in
  `backend/tests/test_project_graph_extractor_registry.py` cover both branches.
- Decision point 4's availability-gating fix is covered by
  ~~`test_orchestrator_routing_succeeds_without_context_model`~~ (renamed
  `test_orchestrator_routing_fails_closed_without_a_configured_model` under
  Revision 7, with its assertion inverted to match) and
  `test_direct_llm_routing_requires_model_even_with_api_key`
  (direct-provider mode still fails closed without a model, confirming the
  gating narrowed correctly rather than being removed).
- Decision point 5's blank-model fix is covered by
  `test_direct_llm_routing_rejects_blank_model` (an empty-string
  `context.model` still fails closed instead of reaching the provider
  client).
- Decision point 6's whitespace-model fix is covered by
  `test_direct_llm_routing_rejects_whitespace_only_model` (a
  whitespace-only `context.model` still fails closed).

**Revision 7 consequences (current behavior):**

- `PROJECT_GRAPH_EXTRACTOR=orchestrator` unconditionally fails closed to the
  deterministic keyword extractor today — no caller populates
  `context.orchestrator_model`, and this extractor has no authority to
  invent a value. This is intentional, not a bug: it is the correct state
  until `ContextualWisdomLab/contextual-orchestrator` ships a release
  naruon can conform to. Covered by
  `test_orchestrator_routing_fails_closed_without_a_configured_model` and
  the new `test_orchestrator_routing_does_not_leak_the_direct_provider_model`
  (proves a populated `context.model` — the realistic case, since
  `email_import_service.py` always sets it — is not substituted) in
  `backend/tests/test_project_graph_extractor_registry.py`.
- `test_orchestrator_routing_targets_the_orchestrator_base_url` still covers
  the transport-only distinction (orchestrator mode hits
  `context.orchestrator_base_url`, never the raw provider `base_url`) using
  a synthetic `context.orchestrator_model`, so the base-URL-routing logic
  stays verified even though no real caller can supply that field yet.
- Operators must not work around the fail-closed state by manually setting
  `context.model` for orchestrator-mode requests, by adding an
  `orchestrator/free`-defaulted settings field, or by any other means that
  reintroduces points 1–2's hardcode — see "Revision 7 alternatives" above.
- **Open follow-up, deliberately out of this ADR's scope:**
  `backend/services/batch_embedding_service.py::_run_orchestrator_batch` sends a
  separate, tenant-configurable `settings.model` (`BatchEmbeddingSettings.model`,
  a DB-backed per-tenant column) to the orchestrator's batch-submission endpoint
  for embeddings, not chat completions. Whether contextual-orchestrator exposes
  an analogous fixed pool id for the embedding modality — and whether pinning
  it the same way is correct for a tenant-configurable batch-embedding setting —
  is not established by any evidence this ADR has access to (no
  `contextual-orchestrator` source is in this session's repository scope). Do
  not assume the same fix applies there without first confirming the gateway's
  embedding-request contract; track as a separate, evidence-gated follow-up
  before extending this pin to that call site.
- If contextual-orchestrator's `orchestrator/free` catalog is ever empty (no
  admitted zero-cost route available), the gateway itself fails closed
  (`400 invalid_model`, per ADR-0003 §2) rather than naruon silently falling
  back to a paid route — `LlmGroundedExtractor`'s existing fallback-to-keyword-
  extractor behavior on any extraction failure already covers this: the KG
  projection degrades to the deterministic extractor, exactly as it already
  does for a missing credential or an unconfigured orchestrator endpoint.

## References (APA 7th)

ContextualWisdomLab. (2026). *ADR-0003: Vendored contextual-orchestrator review
sidecar with governed gateway pools* [ADR, amended 2026-08-30].
`ContextualWisdomLab/.github` `docs/adr/0003-contextual-orchestrator-vendored-free-zdr.md`.
https://github.com/ContextualWisdomLab/.github/blob/main/docs/adr/0003-contextual-orchestrator-vendored-free-zdr.md

OpenRouter. (n.d.). *Data policy: Zero data retention*. Retrieved 2026-09-02,
from https://openrouter.ai/docs/features/privacy-and-logging
The zero-retention definition ADR-0003 §3 adopts ("a provider will not store
your data for any period of time; zero retention also implies no training")
and that this ADR inherits without redefining.

National Institute of Standards and Technology. (2023). *Artificial intelligence
risk management framework (AI RMF 1.0)* (NIST AI 100-1). U.S. Department of
Commerce. https://doi.org/10.6028/NIST.AI.100-1
Governs the data-minimization and provenance rationale for preferring a
zero-retention route for KG extraction over customer email content, consistent
with `docs/CWL-MASTER-CONTEXT.md`'s data-sovereignty commitment.
