# LLM email writing guidance and fast-mlsirm judge calibration

**Status:** Proposed architecture evidence; no production accuracy or language-coverage claim is made.  
**Date:** 2026-08-12

## Purpose

This record supports Naruon's decision to use contextual LLM judgment for email writing guidance while restricting deterministic code to authorization, schema, revision, selector, safety, and operational integrity. It also defines why `fast-mlsirm` is used to measure and calibrate the LLM-as-a-Judge layer instead of replacing it with keyword or regular-expression rules.

## Current CWL implementation evidence

`ContextualWisdomLab/fast-mlsirm` pull request #733 introduced a provider-neutral `ContextualOrchestratorJudge`, strict criterion-level JSON, explicit polytomous categories, runtime-derived acceptance, `LLMJudgeResult.to_irt_row()`, multi-item response-matrix validation, and a deliberate no-keyword/no-positional-repair boundary. All judge model calls are injected through contextual-orchestrator rather than bound to one provider.

This is useful infrastructure, not proof that an email-writing rubric is valid. Naruon must still define the construct, criteria, category anchors, evaluation cases, language profiles, human reference process, calibration policy, and consequences of false positive or false negative guidance.

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
- **ISO/IEC 23894:2023** provides AI risk-management guidance.
- **ISO/IEC 42001:2023** establishes an AI management-system framework for responsible development and use.
- **W3C Web Annotation Data Model** defines `TextPositionSelector` semantics and resource-change limitations.
- **AERA/APA/NCME Standards** inform validity, reliability, fairness, intended-use, and consequence evidence. Naruon does not claim to be a regulated psychological test merely because psychometric methods are used.

## APA 7th references

American Educational Research Association, American Psychological Association, & National Council on Measurement in Education. (2014). *Standards for educational and psychological testing*. American Educational Research Association.

Autio, C., Schwartz, R., Dunietz, J., Jain, S., Stanley, M., Tabassi, E., Hall, P., & Roberts, K. (2024). *Artificial intelligence risk management framework: Generative artificial intelligence profile* (NIST AI 600-1). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.AI.600-1

Chen, H., & Goldfarb-Tarrant, S. (2025). Safer or luckier? LLMs as safety evaluators are not robust to artifacts. In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 19750–19766). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.acl-long.970

Fu, X., & Liu, W. (2025). How reliable is multilingual LLM-as-a-Judge? In *Findings of the Association for Computational Linguistics: EMNLP 2025*. Association for Computational Linguistics. https://aclanthology.org/2025.findings-emnlp.587/

International Organization for Standardization. (2023a). *Information technology—Artificial intelligence—Guidance on risk management* (ISO/IEC Standard No. 23894:2023). https://www.iso.org/standard/77304.html

International Organization for Standardization. (2023b). *Information technology—Artificial intelligence—Management system* (ISO/IEC Standard No. 42001:2023). https://www.iso.org/standard/42001.html

Liu, S., Xu, Z., Liu, Z., Yan, Y., Yu, M., Gu, Y., Chen, C., Xie, H., & Yu, G. (2026). Mitigating judgment preference bias in large language models through group-based polling. In *Findings of the Association for Computational Linguistics: ACL 2026* (pp. 1448–1464). Association for Computational Linguistics. https://doi.org/10.18653/v1/2026.findings-acl.71

Liu, Y., Iter, D., Xu, Y., Wang, S., Xu, R., & Zhu, C. (2023). G-Eval: NLG evaluation using GPT-4 with better human alignment. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 2511–2522). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.emnlp-main.153

Shen, C., Cheng, L., Nguyen, X.-P., You, Y., & Bing, L. (2023). Large language models are not yet human-level evaluators for abstractive summarization. In *Findings of the Association for Computational Linguistics: EMNLP 2023* (pp. 4215–4233). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.278

Usami, H., Hara, K., Tsuboi, A., & Matsuda, N. (2026). *LLM judges have dark current: A psychometric datasheet for LLM-as-a-Judge evaluation* [Preprint]. arXiv. https://arxiv.org/abs/2606.15610

Wang, P., Li, L., Chen, L., Cai, Z., Zhu, D., Lin, B., Cao, Y., Kong, L., Liu, Q., Liu, T., & Sui, Z. (2024). Large language models are not fair evaluators. In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 9440–9450). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.511

World Wide Web Consortium. (2017). *Web annotation data model*. https://www.w3.org/TR/annotation-model/

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* [Preprint]. arXiv. https://arxiv.org/abs/2306.05685

## Claim boundary

The cited evidence supports structured, bias-aware, calibrated LLM evaluation and revision-bound editor integrity. It does not prove that the planned Naruon rubric, model, provider, language profile, or fast-mlsirm configuration is sufficiently valid. Those claims require the benchmark, ablation, DIF, drift, security, privacy, and user-consequence evidence defined in the design.