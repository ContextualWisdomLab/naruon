# Structural Topic Boundary Design

## Context

`backend/api/tools.py` exposes `email_categorizer` and
`meeting_agenda_generator` as analysis tools, but both derive their outputs from
small hard-coded Korean/English term lists. The behavior entered in commit
`c070c8d19f01ccfe46a5ee7e8a577b08e587bb14` as demonstration logic and was
later made deterministic and better tested without correcting the underlying
measurement error. The tests consequently canonized lexical hits as topic
evidence.

Structural topic modeling (STM) is not fixed-label keyword classification. It
estimates mixed-membership topic proportions over a corpus and can model how
document metadata affects topic prevalence or content. Inference for a new
document requires a previously fitted model and its frozen vocabulary; the
result is a topic mixture with uncertainty, not a calibrated probability for a
business label.

## Decision

1. Remove `email_categorizer` and `meeting_agenda_generator` from Naruon's tool
   registry. They have no callers outside their own tests, so removal eliminates
   misleading product behavior without breaking an integrated workflow.
2. Remove `_CATEGORY_TERMS`, `_AGENDA_TOPICS`, and the substring matcher that
   exists only to support those pseudo-models.
3. Retain `keyword_extractor` as an explicitly lexical utility, but describe it
   honestly as deterministic term-frequency extraction. Its output must never
   be treated as topic posterior evidence.
4. Do not add an embedding, LLM, or larger dictionary fallback and do not call
   any such fallback STM.
5. Reserve corpus-level topic estimation for the Rust-first TEPP
   `topic_measurement` boundary. Naruon may consume that boundary only after it
   exposes a versioned, source-backed model artifact and new-document inference
   contract. Absence of a fitted model must fail closed rather than return
   `General` or a template agenda.

## Future TEPP integration contract

The later integration must carry, at minimum:

- immutable document and model-artifact identifiers plus content/vocabulary
  digests;
- document, event, assertion, availability, and knowledge-cutoff times;
- language and multilevel/cross-classified membership covariates;
- the frozen preprocessing and prevalence/content design specifications;
- topic proportions that sum to one, posterior uncertainty, inference method,
  model version, and diagnostic status;
- evidence-backed topic labels kept separate from the numeric topic identity;
- explicit out-of-vocabulary and model-unavailable errors.

Agenda generation, if reintroduced, must consume source evidence and the
versioned posterior through a separate decision/generation boundary. It must not
map raw words directly to agenda templates.

## Alternatives rejected

- **Expand the dictionaries:** deterministic but still lexical, brittle across
  language and domain, and unable to represent mixed membership or uncertainty.
- **Use embeddings or an LLM as a drop-in replacement:** potentially useful for
  semantic labeling, but neither is STM and neither supplies the required
  corpus-level estimand or covariate effects.
- **Fit a model inside each API request:** statistically invalid for a single
  document, operationally expensive, and incompatible with reproducible model
  artifacts.

## Verification

- A regression test must fail on the current branch because the two misleading
  tool codes are still registered.
- After the change, the registry must omit both codes while retaining the
  explicitly lexical term-frequency utility.
- Focused tools tests, the complete backend test suite with warnings promoted to
  errors, and Ruff must pass.

## References

Roberts, M. E., Stewart, B. M., & Tingley, D. (2019). stm: An R package for
structural topic models. *Journal of Statistical Software, 91*(2), 1–40.
https://doi.org/10.18637/jss.v091.i02

Roberts, M. E., Stewart, B. M., Tingley, D., Lucas, C., Leder-Luis, J.,
Gadarian, S. K., Albertson, B., & Rand, D. G. (2014). Structural topic models
for open-ended survey responses. *American Journal of Political Science,
58*(4), 1064–1082. https://doi.org/10.1111/ajps.12103
