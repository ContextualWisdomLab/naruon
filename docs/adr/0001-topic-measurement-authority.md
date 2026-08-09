# ADR-0001: Structural topic measurement is a TEPP model-artifact boundary

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Naruon historically exposed `email_categorizer` and `meeting_agenda_generator` from small hard-coded Korean/English term tables. Those outputs were deterministic, but they were lexical rules presented through product names that implied semantic topic inference. That is not a Structural Topic Model and provides no fitted corpus-level topic identity, mixed-membership posterior, uncertainty, prevalence/content covariate effect, multilingual measurement evidence, or model-artifact provenance.

The CWL scientific boundary is already defined in TEPP: LLM-assisted multilingual semantic evidence may support measurement, while fitted statistical topic inference remains a versioned Rust-first model with explicit preprocessing/vocabulary, temporal availability and multilevel/multiple-membership structure where applicable. Naruon is a consuming workspace/product surface, not a second independent topic-estimation authority.

## Decision

1. Naruon's retained `keyword_extractor` remains explicitly lexical metadata only. It must never be described as a topic model or semantic classifier.
2. Naruon will not replace removed pseudo-topic tools with a larger keyword table, embedding cluster, zero-shot labeler, or LLM prompt while naming the result Structural Topic Modeling.
3. Production topic inference, when available, must consume a **versioned fitted TEPP model artifact** through a stable typed integration boundary. Naruon must not refit an STM per request.
4. A valid inference request/result must bind at least: model artifact/version and digest; immutable source/document identity; frozen preprocessing and vocabulary; OOV/retained-token diagnostics; language profile/support status; relevant prevalence/content and multilevel/cross-classified/multiple-membership covariates; event/document/availability/knowledge-cutoff time semantics when the model uses them; mixed-membership topic proportions; posterior uncertainty/diagnostics; and explicit abstention/failure status.
5. Human-readable topic labels and generated agenda/action summaries are presentation/generation artifacts. They are never the numeric topic identity and cannot change the fitted posterior.
6. If the required TEPP model/API/artifact is unavailable, incompatible, under-supported for the document language, or cannot produce an evidence-valid posterior, Naruon fails closed. It does not fabricate `General`, empty agenda semantics, or an embedding/LLM substitute under the same contract.
7. TEPP remains independently operable and Naruon remains independently useful without topic inference. Integration is optional and versioned; Naruon must not read TEPP's private database directly.

## Alternatives rejected

### Keep deterministic keyword categories

Rejected because deterministic lexical matching is not mixed-membership topic measurement and would preserve the original product-truth defect.

### Use embeddings or clustering as a drop-in STM replacement

Rejected as a semantic product substitution. Such methods may be useful in separate features, but equal semantic usefulness does not make them an STM posterior or preserve the same prevalence/content/uncertainty contract.

### Ask an LLM for topic labels at request time

Rejected as the statistical authority. LLMs may interpret or label fitted evidence behind a separate bounded contract, but request-time labels do not replace a fitted corpus-level model and its uncertainty.

### Fit a fresh topic model for every Naruon request

Rejected because new-document inference must be comparable against a stable fitted model. Per-request refits destroy topic identity, reproducibility, governance, and longitudinal comparability.

## Consequences

- PR #1297 removes the misleading pseudo-topic tools rather than shipping an unvalidated replacement.
- The next topic-related product work belongs first in TEPP: production fitted-model artifact and inference API, realistic model validation, then a Naruon adapter.
- Naruon tests must keep lexical utilities labelled lexical and must fail if removed pseudo-topic registry entries reappear without an accepted replacement contract.
- Any future adapter must carry model/provenance/uncertainty/diagnostic fields rather than only a label string.
- Product documentation must distinguish `implemented on protected develop`, `active PR`, and `accepted target`; this ADR does not claim TEPP topic inference exists today.

## Verification / acceptance

Before a future topic-measurement adapter is promoted to protected `develop`, require:

- TEPP production artifact/inference API available at a versioned contract;
- fitted-model and preprocessing/vocabulary identity validation;
- positive, negative, OOV/insufficient-text, unsupported-language and model-unavailable tests;
- posterior normalization and uncertainty/diagnostic tests;
- multilevel/multiple-membership and temporal-covariate contract tests when those inputs are part of the fitted model;
- tenant/source authorization at the Naruon boundary;
- exact-head CI/security/coverage and independent review;
- no claim that topic labels or LLM interpretations are the numeric topic identity.

## Supersession rule

Changing the statistical authority away from TEPP, changing new-document topic identity semantics, or authorizing Naruon to fit its own production topic models requires a superseding ADR plus synchronized product/technical/architecture/test/operability documentation and scientific validation evidence.