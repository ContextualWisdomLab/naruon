# LLM email writing guidance and fast-mlsirm judge calibration

**Status:** Proposed architecture evidence; no production accuracy or language-coverage claim is made.  
**Date:** 2026-08-12  
**Evidence refreshed:** 2026-09-01

## Purpose

This record supports Naruon's decision to use contextual LLM judgment for email writing guidance while restricting deterministic code to authorization, schema, revision, selector, safety, and operational integrity. It also defines why `fast-mlsirm` is used to measure and calibrate the LLM-as-a-Judge layer instead of replacing it with keyword or regular-expression rules.

## Current CWL implementation evidence

The current immutable `fast-mlsirm` GitHub release is [`v0.9.1`](https://github.com/ContextualWisdomLab/fast-mlsirm/releases/tag/v0.9.1), published 2026-08-26. The `v0.9.1` tag resolves to source commit `09f762ded35786dd1078222a4577ff09d649816f`. Its tagged package source exports the provider-neutral `ContextualOrchestratorJudge`, `JudgeCriterion`, `JudgeFormatError`, `LLMJudgeResult`, and `validate_irt_response_matrix`; package metadata declares version `0.9.1` and Python `>=3.12`. The GitHub release currently has no attached distributable assets.

That distinction is material. The released source contract is sufficient to retire the obsolete `v0.6.0` source-surface assumption, but it is not yet sufficient for Naruon runtime import. Before Naruon consumes `fast-mlsirm`, the dependency gate must verify an approved immutable distributable package source, exact artifact integrity hash, provenance back to source commit `09f762ded35786dd1078222a4577ff09d649816f`, Python 3.14 compatibility, and Naruon's immutable hash lock. Mutable branches, Git URLs, source copies, local stubs, and workspace paths are not acceptable production dependencies. Package-unavailable behavior must remain testable by dependency injection rather than by assuming the package is absent from the environment.

The verified public surface includes strict criterion-level structured output, explicit dichotomous/polytomous category semantics, deterministic response-matrix validation, and provider-neutral contextual-orchestrator injection. This is useful infrastructure, not proof that an email-writing rubric is valid. Naruon must still define the construct, criteria, category anchors, evaluation cases, language profiles, human reference process, calibration policy, and consequences of false-positive or false-negative guidance.

Inkspan is a separate immutable dependency gate. The current immutable release is [`v0.3.1`](https://github.com/ContextualWisdomLab/inkspan/releases/tag/v0.3.1) from `ContextualWisdomLab/inkspan`; tag `v0.3.1` resolves to source commit `67afc7099cc0e5711a9cc9476bf3be5bb820e229`, and the tagged npm manifest identifies `@contextualwisdomlab/cwl-editor` version `0.3.1`. The GitHub release contains no attached assets, so there is no release-asset SHA-256 to record or invent. Its public exports cover the editor root, collaboration, converter, styles, and fonts but not a `writing-diagnostics` subpath. Naruon therefore must not consume the open writing-diagnostics stack from a branch or Draft PR. Runtime integration waits for a future immutable package artifact that exposes the required writing-diagnostics public subpath and supplies registry/tarball integrity, source provenance, browser/package compatibility, and the revision-bound diagnostic contract required by this design.

## Why keyword matching is rejected

### Lexical presence does not establish pragmatic function

A phrase may be a quotation, a factual incident transcript, a proper name, code, a rhetorical example, or a direct interpersonal act. The same words can therefore support different judgments. Conversely, blame, sarcasm, ambiguity, excessive deference, or technically unsound requests can be expressed without any known trigger phrase.

A keyword detector can be useful for exact policy terms whose lexical occurrence is itself the target. It is not a valid proxy for grammar, clarity, politeness, audience pragmatics, actionability, or technical correctness.

### Recipient and thread context matter

Email interpretation depends on who is speaking to whom, the copied audience, prior commitments, the purpose of the reply, and the surrounding thread. The same sentence can be acceptable in a private peer exchange but read as public rebuke in a broad executive CC thread. Naruon therefore re-reads authorized email/thread context and asks a contextual model; it does not infer the judgment from recipient count alone.

### Deterministic fallback creates hidden false certainty

When a model is unavailable or abstains, a lexical fallback would silently change the feature from contextual review to a different, uncalibrated classifier. The architecture instead degrades to “review unavailable” while preserving editing and sending.

## What research supports—and does not support

### Structured LLM evaluation is useful but fallible

G-Eval showed that rubric-driven form filling with an LLM can correlate better with human judgments than several traditional automatic metrics in the evaluated summarization setting. MT-Bench and Chatbot Arena demonstrated scalable LLM-based evaluation and documented limitations such as position, verbosity, and self-enhancement bias.

These results support structured criteria, independent judging, and explicit evaluation. They do not prove that an LLM is a universally reliable grammar or workplace-pragmatics authority.

### Evaluator bias requires calibration and monitoring

Research has documented unfair preferences, position effects, artifact sensitivity, self-preference, persuasion effects, and disagreement across judge models and evaluation settings. A valid JSON response is therefore necessary for automation but not sufficient evidence of validity.

Naruon addresses this by:

- separating candidate generation and judgment roles;
- using criterion-level ordered categories;
- admitting abstention and adjudication;
- measuring calibration and error by language/context group;
- versioning model, rubric, prompt, and policy;
- preserving user authority over every applied replacement.

### Multilingual performance cannot be assumed

Multilingual LLM-judge research reports inconsistent performance across languages and lower-resource settings. Naruon can expose a language-neutral editor and API contract, but each language profile requires its own validation evidence. A model's ability to accept Korean text is not equivalent to validated Korean pragmatic guidance.

### Psychometrics adds measurement discipline

An LLM judge is treated as a rater/measurement device. Criterion prompts act like items, ordered categories produce responses, and model/provider/prompt configurations can act as raters or facets. fast-mlsirm can help evaluate item difficulty/discrimination, category use, latent structure, rater severity/interaction where implemented, DIF, reliability, category-count choices, and drift.

This does not make LLM output objective truth. It makes assumptions, uncertainty, group differences, and policy changes measurable and auditable.

## Proposed construct map

The initial system distinguishes at least four related constructs:

1. **Mechanical correctness** — spelling, spacing, punctuation, morphology, and syntax.
2. **Comprehensibility and structure** — clarity, concision, reference resolution, logical ordering, and redundancy.
3. **Pragmatic fitness** — audience, relationship, public/private context, face threat, firmness, and collaborative interpretation.
4. **Operational fidelity** — preservation of facts, actors, quantities, deadlines, request strength, technical claims, and actionable next steps.

A single scalar score is inadequate because a grammatically polished replacement can still weaken accountability or distort a technical request. Criterion-level responses and mandatory preservation floors are therefore part of the admission policy.

## Proposed criterion-response design

Each candidate diagnostic is judged on observable criteria such as:

```text
issue_support
span_fidelity
replacement_correctness
intent_preservation
fact_preservation
request_strength_preservation
audience_pragmatics
technical_precision
actionability
explanation_quality
```

The first study should compare category counts such as 2, 3, 4, 5, and 7 rather than assuming that finer scales always improve measurement. Category anchors must be explicit, ordered, and criterion-specific where necessary.

A runtime decision is derived from the criterion pattern and a versioned calibration policy. It is not derived from the occurrence of “rude” words or a free-form model declaration.

## Evaluation design

### Reference judgments

Use trained human reviewers with a documented rubric and adjudication procedure. Human agreement and disagreement are reported; adjudicated labels are reference evidence, not infallible ground truth.

### Contrast sets

The benchmark contains matched cases that vary one factor at a time:

- identical wording used as quotation versus direct speech act;
- paraphrases of the same issue with no shared trigger words;
- proper names, code, URLs, file paths, and product terms resembling misspellings;
- identical drafts with different recipient roles and thread histories;
- firm legitimate requests that must not be weakened;
- polite but technically invalid requests;
- terse but acceptable operational messages;
- Korean, English, mixed-language, code-switched, and CJK/Unicode cases.

These cases directly test the claim that semantic behavior is not keyword matching.

### Metrics

Report, at minimum:

- issue/category precision, recall, macro-F1;
- smallest-sufficient-span accuracy and span intersection-over-union;
- replacement correctness;
- fact, intent, actor, deadline, and request-strength preservation;
- unsupported-claim and hallucinated-fact rate;
- user acceptance/ignore/rewrite rates with selection caveats;
- human inter-rater agreement;
- Brier score, expected calibration error, and reliability curves;
- category occupancy and sparse-category behavior;
- test-retest and cross-model agreement;
- DIF or group-specific error by language, role/context, recipient configuration, and thread depth;
- temporal/model/prompt/rubric drift;
- latency, token, cost, and orchestration-depth distributions.

No overall “email danger” or “tone risk” score substitutes for the criterion results.

### Pre-registered publication protocol

Before calibration or threshold selection, the evaluation runner writes a
canonical `email_writing_policy_protocol_v1` document and records its SHA-256.
The split is fixed by contrast family, not by individual rows: 60% calibration,
20% development, and a 20% human-labeled locked holdout. Locked-holdout labels
remain sealed and inaccessible to calibration, development, threshold selection,
and policy fitting; they are opened only for the preregistered final
publish/no-publish evaluation after all thresholds and decision rules are frozen.
The holdout case-manifest SHA-256 is stored beside the protocol hash before that
label access. The initial publication gates are fixed in the protocol: holdout
macro-F1 at least 0.80, every mandatory preservation criterion at least 0.90,
unsupported-claim rate at most 0.02, expected calibration error at most 0.05,
and no prespecified language/role/context slice with macro-F1 below 0.70 when
that slice has the preregistered minimum sample size.

The preregistered `minimum_slice_sample_size` is 30 labeled cases per slice. A
slice below that count is reported as underpowered rather than selectively
excluded after seeing its result.

The same protocol preregisters three additional release-risk gates before any
locked-holdout labels are accessed:

- **DIF/fairness:** `maximum_large_dif_flags = 0`. A “large” flag must come from
  the exact released fast-mlsirm DIF estimator and its method-specific,
  preregistered effect-size classification. The protocol also caps the absolute
  macro-F1 gap between every supported prespecified slice and the pooled
  holdout at `0.10`, and the absolute mandatory-preservation-rate gap at `0.05`.
  If the released estimator cannot produce a compatible effect-size
  classification for a requested profile, that profile is withheld rather than
  declared DIF-clean.
- **Temporal drift:** relative to the last published baseline on the same frozen
  recurrent benchmark, macro-F1 may fall by at most `0.05` and expected
  calibration error may increase by at most `0.02`. Crossing either bound
  withholds the affected profile pending a new preregistered evaluation.
- **Critical consequences:** for cases whose adjudicated reference marks a
  fact/actor/deadline/request-strength distortion as critical,
  `maximum_observed_critical_consequence_errors = 0` and the one-sided 95%
  exact-binomial upper confidence bound for the critical-consequence error rate
  must be at most `0.05`. An underpowered critical-consequence set therefore
  withholds publication rather than converting zero observed errors into a
  safety claim.

These numeric cutoffs are conservative Naruon product-admission tolerances, not
universal psychometric, fairness, or AI-safety constants. The AERA/APA/NCME
Standards support intended-use, fairness, reliability, and consequence evidence;
DIF literature supports combining statistical evidence with effect magnitude;
and NIST AI RMF guidance supports comparing production behavior with
pre-deployment metrics and monitoring drift. None of those sources mandates
these particular Naruon cutoffs. Any threshold change requires a new protocol
version before the new locked holdout is opened.

The policy artifact must contain `protocol_id`, `protocol_hash`,
`calibration_split_hash`, `development_split_hash`, `locked_holdout_hash`,
literal `minimum_slice_sample_size: 30`, every literal publication threshold and
decision rule above, a lifecycle `status`, and `publish_decision` (`publish` or
`withhold`). An `evaluation_only` artifact is represented as
`status: evaluation_only` plus `publish_decision: withhold`; the two fields are
orthogonal and the combination is enforced by schema. Every artifact consumer
must have access to the immutable protocol identified by `protocol_hash` and
must reject an artifact whose duplicated literal values disagree with that
protocol. Changing any split, threshold, protocol, or holdout requires a new
protocol version and a new calibration run. Thresholds must be frozen before
the locked-holdout labels are accessed. A run that tunes thresholds against the
locked holdout is invalid for publication and requires a new locked holdout; it
is not a publication decision.

## Multi-agent and compute allocation

The workflow can allocate more test-time computation without lexical routing:

- explicit incremental review uses a bounded candidate reviewer and independent judge;
- explicit deep review decomposes mechanics, discourse/actionability, pragmatics, and technical precision;
- calibrated disagreement, preservation conflict, missing context, or uncertainty can trigger adjudication;
- role-specific reasoning effort and workflow depth are recorded;
- ablations compare single-model routing, independent judge, multi-agent review, and adjudication.

Speed is not the primary scientific criterion, but every workflow remains resource-bounded and observable.

## Revision and annotation validity

Inkspan's revision-scoped W3C `TextPositionSelector` contract supplies Unicode-code-point offsets and a strong document revision. The W3C model itself warns that position selectors are brittle when a resource changes. Naruon and Inkspan therefore reject stale diagnostics rather than searching for keywords or moving the suggestion to the nearest similar sentence.

## Privacy and PII

Pragmatic review may need names, organizational roles, dates, quantities, recipient relationships, and thread commitments. Blind masking can destroy the construct being measured. The system instead uses compensating controls:

- approved provider/model/region policy;
- encrypted transport and credential storage;
- contractual no-training/no-secondary-use restrictions;
- no raw content in ordinary logs or telemetry;
- short-lived or zero-retention review sessions;
- opaque identifiers and policy/version provenance;
- synthetic or carefully de-identified persistent benchmark cases;
- explicit access, export, retention, and deletion controls.

This design does not assert that every provider satisfies those requirements. Tenant configuration and procurement evidence determine which providers are eligible.

## Standards and governance alignment

- **NIST AI 600-1** supports lifecycle risk identification, evaluation, monitoring, and governance for generative AI systems.
- **NIST AI 100-1** supports use-case-specific measurement and ongoing comparison of deployed behavior with pre-deployment evidence rather than universal thresholds.
- **ISO/IEC 23894:2023** provides AI risk-management guidance.
- **ISO/IEC 42001:2023** establishes an AI management-system framework for responsible development and use.
- **W3C Web Annotation Data Model** defines `TextPositionSelector` semantics and resource-change limitations.
- **AERA/APA/NCME Standards** inform validity, reliability, fairness, intended-use, and consequence evidence. Naruon does not claim to be a regulated psychological test merely because psychometric methods are used.

## APA 7th references

American Educational Research Association, American Psychological Association, & National Council on Measurement in Education. (2014). *Standards for educational and psychological testing*. American Educational Research Association.

Autio, C., Schwartz, R., Dunietz, J., Jain, S., Stanley, M., Tabassi, E., Hall, P., & Roberts, K. (2024). *Artificial intelligence risk management framework: Generative artificial intelligence profile* (NIST AI 600-1). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.AI.600-1

Chen, H., & Goldfarb-Tarrant, S. (2025). Safer or luckier? LLMs as safety evaluators are not robust to artifacts. In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 19750–19766). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.acl-long.970

Gómez-Benito, J., Hidalgo, M. D., & Zumbo, B. D. (2013). Effectiveness of combining statistical tests and effect sizes when using logistic discriminant function regression to detect differential item functioning for polytomous items. *Educational and Psychological Measurement, 73*(5), 875–897. https://doi.org/10.1177/0013164413492419

Fu, X., & Liu, W. (2025). How reliable is multilingual LLM-as-a-Judge? In *Findings of the Association for Computational Linguistics: EMNLP 2025*. Association for Computational Linguistics. https://aclanthology.org/2025.findings-emnlp.587/

International Organization for Standardization. (2023a). *Information technology—Artificial intelligence—Guidance on risk management* (ISO/IEC Standard No. 23894:2023). https://www.iso.org/standard/77304.html

International Organization for Standardization. (2023b). *Information technology—Artificial intelligence—Management system* (ISO/IEC Standard No. 42001:2023). https://www.iso.org/standard/42001.html

Liu, S., Xu, Z., Liu, Z., Yan, Y., Yu, M., Gu, Y., Chen, C., Xie, H., & Yu, G. (2026). Mitigating judgment preference bias in large language models through group-based polling. In *Findings of the Association for Computational Linguistics: ACL 2026* (pp. 1448–1464). Association for Computational Linguistics. https://doi.org/10.18653/v1/2026.findings-acl.71

Liu, Y., Iter, D., Xu, Y., Wang, S., Xu, R., & Zhu, C. (2023). G-Eval: NLG evaluation using GPT-4 with better human alignment. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 2511–2522). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.emnlp-main.153

Shen, C., Cheng, L., Nguyen, X.-P., You, Y., & Bing, L. (2023). Large language models are not yet human-level evaluators for abstractive summarization. In *Findings of the Association for Computational Linguistics: EMNLP 2023* (pp. 4215–4233). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.278

Tabassi, E. (2023). *Artificial intelligence risk management framework (AI RMF 1.0)* (NIST AI 100-1). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.AI.100-1

Usami, H., Hara, K., Tsuboi, A., & Matsuda, N. (2026). *LLM judges have dark current: A psychometric datasheet for LLM-as-a-Judge evaluation* [Preprint]. arXiv. https://arxiv.org/abs/2606.15610

Wang, P., Li, L., Chen, L., Cai, Z., Zhu, D., Lin, B., Cao, Y., Kong, L., Liu, Q., Liu, T., & Sui, Z. (2024). Large language models are not fair evaluators. In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 9440–9450). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.511

World Wide Web Consortium. (2017). *Web annotation data model*. https://www.w3.org/TR/annotation-model/

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* [Preprint]. arXiv. https://arxiv.org/abs/2306.05685

## Claim boundary

The cited evidence supports structured, bias-aware, calibrated LLM evaluation and revision-bound editor integrity. It does not prove that the planned Naruon rubric, model, provider, language profile, or fast-mlsirm configuration is sufficiently valid. The numeric admission thresholds above are product policy, not literature-derived universal constants. Product validity claims require the benchmark, ablation, DIF, drift, security, privacy, and user-consequence evidence defined in the design.
