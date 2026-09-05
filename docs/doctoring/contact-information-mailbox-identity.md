# Contact-information mailbox identity

## Problem

`contact_information_extractor` originally deduplicated every extracted value with `casefold()`. That is acceptable for the bounded phone representations used here, but it can collapse two distinct email mailboxes whose local-parts differ only by case. RFC 5321 requires SMTP implementations to preserve mailbox local-part case, while mailbox domains follow case-insensitive DNS comparison. RFC 6531 extends mailbox syntax for SMTPUTF8 without replacing the RFC 5321 local-part parsing rule. RFC 9549 uses the same comparison boundary for email identifiers: exact local-part and case-insensitive host-part comparison.

The defect is buyer-visible data loss rather than formatting trivia. A contact-review tool must not silently discard one extracted mailbox because another address differs only in local-part case.

## Decision

Naruon keeps the extracted representation byte-for-byte and deduplicates email addresses with a two-part identity:

- local-part: exact comparison;
- domain part: case-insensitive comparison with `casefold()`.

Therefore `Ada.Example@example.com` and `Ada.Example@EXAMPLE.com` are one extracted mailbox representation, while `Ada.Example@example.com` and `ada.example@example.com` remain distinct. The same exact-local rule is retained for SMTPUTF8-style Unicode local-parts. This service does not attempt provider-specific mailbox canonicalization, Unicode normalization, alias resolution, or deliverability validation.

The extraction boundary remains purpose-limited: it operates only on caller-supplied text, does not log, persist, index, or transmit the input or extracted PII, and leaves authorization, retention, and downstream disclosure to the caller.

## Alternatives rejected

Case-folding the complete mailbox was rejected because it can merge identifiers that SMTP requires implementations to preserve distinctly. Treating the entire address as exact was also rejected because domain labels are case-insensitive and would emit duplicate representations such as `Ada.Example@example.com` and `Ada.Example@EXAMPLE.com`.

Provider-specific canonicalization such as lowercasing local-parts, dot removal, plus-tag stripping, or account-directory lookup was rejected because those rules are not portable mailbox identity rules and would make this pure extractor depend on external provider semantics.

## Executable traceability

- RED: `1bf449a078580cc6545f862c07a8d68bf968b005` changes the focused regression so domain-only case changes deduplicate but local-part case changes remain distinct.
- Causal fix: `fd629039b1d4a4b36d8ab5cdb1bdbc8e4e787c1b` introduces exact-local/case-insensitive-domain mailbox identity without changing the bounded extraction patterns or the no-side-effect PII boundary.
- Regression owner: `backend/tests/test_text_analysis_services.py`.
- Production owner: `backend/services/contact_information_extractor.py`.

These commits establish RED-before-fix source provenance. A protected GREEN claim still requires current-head test/check evidence; predecessor or unrelated PR results do not transfer.

## References

Housley, R. (2024). *Internationalization updates to RFC 5280* (RFC 9549). RFC Editor. https://doi.org/10.17487/RFC9549

Klensin, J. (2008). *Simple Mail Transfer Protocol* (RFC 5321). RFC Editor. https://doi.org/10.17487/RFC5321

Yao, J., & Mao, W. (2012). *SMTP extension for internationalized email* (RFC 6531). RFC Editor. https://doi.org/10.17487/RFC6531
