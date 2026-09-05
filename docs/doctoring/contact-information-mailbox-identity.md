# Contact-information mailbox identity

## Problem

`contact_information_extractor` originally deduplicated every extracted value with `casefold()`. That can collapse distinct email mailboxes whose local-parts differ only by case. RFC 5321 requires SMTP implementations to preserve mailbox local-part case, while ASCII DNS labels use case-insensitive comparison. RFC 6531 extends mailbox syntax for SMTPUTF8 without replacing the RFC 5321 local-part rule.

The first repair therefore changed mailbox identity to exact local-part plus a case-insensitive domain. A follow-up review found that the domain rule was still too broad for internationalized domain labels: Python `casefold()` maps some Unicode strings irreversibly, including German sharp S (`ß`) to `ss`. IDNA2008 does not define U-label equivalence by arbitrary Unicode case folding. RFC 5891 requires A-labels to compare as case-insensitive ASCII and U-labels to compare as-is, without case folding or other intermediate steps; RFC 5894 explicitly calls out the irreversible `ß` → `ss` mapping as a reason IDNA2008 moved away from the IDNA2003 folding model.

That matters for extraction because `Ada@faß.de` and `Ada@fass.de` must not be silently collapsed merely because a generic Unicode fold produces the same string. The defect is data loss, not a presentation difference.

## Decision

Naruon keeps the extracted mailbox representation unchanged and uses a loss-avoiding identity rule:

- local-part: exact comparison;
- ASCII domain labels, including A-label/LDH representations: case-insensitive comparison;
- non-ASCII U-labels: exact comparison, with no Unicode case folding.

The comparison is label-by-label so `Ada@EXAMPLE.한국` and `Ada@example.한국` deduplicate on the ASCII label while the identical `한국` U-label is preserved exactly. `Ada@faß.de` and `Ada@fass.de` remain distinct.

This pure extractor deliberately does not perform IDNA A-label/U-label conversion, NFC normalization, provider-specific alias canonicalization, MX/deliverability lookup, or account-directory resolution. That means semantically equivalent A-label and U-label spellings may remain as separate extracted representations. For a non-normalizing extraction boundary, retaining a duplicate is preferable to deleting a potentially distinct mailbox. Any future canonicalization must use an explicit validated IDNA profile and its own migration evidence rather than generic Unicode folding.

The extraction boundary remains purpose-limited: it operates only on caller-supplied text, does not log, persist, index, or transmit the input or extracted PII, and leaves authorization, retention, and downstream disclosure to the caller.

## Alternatives rejected

Case-folding the complete mailbox was rejected because it can merge local-parts that SMTP requires implementations to preserve. Case-folding the complete Unicode domain was also rejected because IDNA2008 U-label comparison is exact and generic folding is not reversible.

Treating every domain label as exact was rejected because ASCII DNS labels are case-insensitive and would emit avoidable duplicates such as `Ada@example.com` and `Ada@EXAMPLE.com`. Automatically converting between A-label and U-label forms was deferred because this service currently performs bounded pattern extraction, not IDNA validation or normalization; adding conversion here would silently broaden the contract.

Provider-specific rules such as local-part lowercasing, dot removal, plus-tag stripping, or account-directory lookup were rejected because they are not portable mailbox identity rules and would introduce external provider semantics into a pure service.

## Executable traceability

- Local-part RED: `1bf449a078580cc6545f862c07a8d68bf968b005` requires domain-only ASCII case changes to deduplicate while preserving local-part case.
- Local-part fix: `fd629039b1d4a4b36d8ab5cdb1bdbc8e4e787c1b` introduces exact local-part comparison.
- IDNA U-label RED: `2d6da9a86c4d4a9a231cfd96884482e5d5bd9b1d` requires `faß.de` and `fass.de` to remain distinct while preserving case-insensitive comparison of an ASCII label in a mixed internationalized domain.
- IDNA U-label fix: `f7b9974ba0e267d45dae82e3626f6a33a7e16d21` compares ASCII domain labels case-insensitively and non-ASCII labels exactly.
- Regression owner: `backend/tests/test_text_analysis_services.py`.
- Production owner: `backend/services/contact_information_extractor.py`.

These commits establish RED-before-fix source provenance. Current-head pytest, repository checks, independent review, protected merge, and release remain separate evidence gates.

## References

Housley, R. (2024). *Internationalization updates to RFC 5280* (RFC 9549). RFC Editor. https://doi.org/10.17487/RFC9549

Klensin, J. (2008). *Simple Mail Transfer Protocol* (RFC 5321). RFC Editor. https://doi.org/10.17487/RFC5321

Klensin, J. C. (2010a). *Internationalized domain names for applications (IDNA): Definitions and document framework* (RFC 5890). RFC Editor. https://doi.org/10.17487/RFC5890

Klensin, J. C. (2010b). *Internationalized domain names in applications (IDNA): Protocol* (RFC 5891). RFC Editor. https://doi.org/10.17487/RFC5891

Klensin, J. C. (2010c). *Internationalized domain names for applications (IDNA): Background, explanation, and rationale* (RFC 5894). RFC Editor. https://doi.org/10.17487/RFC5894

Yao, J., & Mao, W. (2012). *SMTP extension for internationalized email* (RFC 6531). RFC Editor. https://doi.org/10.17487/RFC6531
