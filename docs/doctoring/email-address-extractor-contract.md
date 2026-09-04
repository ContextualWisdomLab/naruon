# Email address extractor contract

## Problem

The first extractor used a second permissive regular expression. It accepted
empty domain labels such as `a@b..com` and then tried to repair sentence
punctuation after matching. That disagreed with the email masker and allowed
the two tools to classify the same address differently.

## Boundary

The extractor and masker now share `_EMAIL_PATTERN` in `backend/api/tools.py`.
It accepts a bounded ASCII dot-atom local part and DNS-style domain labels,
preserves the first spelling encountered, and deduplicates case-insensitively.
Quoted local parts, comments, internationalized addresses, domain literals,
and full mailbox parsing remain outside this utility tool's claim.

This is an extraction aid, not an RFC-complete mailbox validator. Sending and
identity boundaries must still use their protocol-specific validation.

## Verification

`backend/tests/test_tools_api.py` covers mixed-case duplicate addresses,
subdomains, sentence punctuation, ellipses, malformed empty domain labels,
the signed API envelope, empty input, and the shared input-size limit.

## Reference

Resnick, P. (2008). *Internet message format* (RFC 5322). Internet Engineering
Task Force. https://doi.org/10.17487/RFC5322

RFC 5322 sections 3.2.3 and 3.4.1 define dot-atoms and address syntax. The
bounded matcher deliberately implements only the common ASCII dot-atom and
DNS-label subset described above, avoiding claims of complete RFC parsing.
