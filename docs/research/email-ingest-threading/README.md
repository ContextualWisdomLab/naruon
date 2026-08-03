# Email Ingest & Threading — Standards Basis and Design Rationale

This pack grounds the email-ingest correctness work on
`ContextualWisdomLab/naruon#1192`
(`backend/services/threading_service.py`, `backend/services/email_parser.py`):
Message-ID interior-whitespace normalization, unknown-zone (`-0000`) date
normalization, In-Reply-To `1*msg-id` (multi-parent + CFWS) parsing, and
RFC 2047 encoded-word decoding of non-ASCII display names.

## Standards basis (RFC 5322 message format + RFC 2047 header encoding)

Each fix is anchored to a specific clause of the relevant standard:

- **Header unfolding** — RFC 5322 §2.2.3. When a folded header is rejoined,
  interior whitespace/tabs can survive. `normalize_message_id` collapses that
  interior whitespace so the folded and unfolded forms of one Message-ID map to
  a single de-dup/threading key.
- **Message-ID** — RFC 5322 §3.6.4 (`msg-id = "<" id-left "@" id-right ">"`).
  A well-formed Message-ID carries no interior whitespace, so collapsing it is a
  no-op for conforming input and only repairs unfolded input.
- **In-Reply-To / References** — RFC 5322 §3.6.4 defines both as `1*msg-id`
  (one or more angle-bracketed ids, each optionally wrapped in CFWS, §3.2.2).
  `assign_thread_id` therefore parses In-Reply-To with the same multi-id
  extractor used for References, so a reply naming several parents — or a single
  id trailed by a comment — threads onto an existing ancestor instead of
  splitting off on a garbage key.
- **Date / unknown zone** — RFC 5322 §3.3 defines a `-0000` zone as "time zone
  unknown". `email.utils.parsedate_to_datetime` returns a naive datetime for
  that case; `_extract_date` treats the unknown zone as UTC so every ingested
  date is timezone-aware and safe to sort and to store in a `timestamptz`
  column.
- **Non-ASCII display names** — RFC 2047 (MIME Part Three) defines the
  `=?charset?enc?text?=` encoded-word so non-ASCII text can appear in structured
  headers. `From` / `To` / `Reply-To` display names arrive header-decoded under
  `email.policy.default`, so `_sanitize_address_display_text` must store the
  decoded name and must **not** re-encode it. `email.utils.formataddr` re-encodes
  any non-ASCII display name back into an encoded-word, which stored a garbled
  `=?utf-8?...?=` value for every non-ASCII (e.g. Korean) sender/recipient;
  `_format_display_address` keeps the decoded name literal while preserving
  formataddr's RFC 5322 quoting/escaping for display-name specials.

## Design rationale — header-based, precision-first threading

Naruon reconstructs conversations from the RFC 5322 reference graph
(References / In-Reply-To), deterministically, and deliberately does **not**
fall back to subject- or content-based grouping. This is a precision/recall
trade-off, not an oversight, and the rejected alternative is grounded in the
conversation-threading literature:

- Content- and coherence-model approaches to thread reconstruction are
  probabilistic and improve *recall* on broken reference chains, but carry an
  inherent false-merge (precision) cost: Mohiuddin, Joty, and Nguyen (2018)
  reconstruct thread trees by scoring candidate structures with a neural
  coherence model, and even their best model reaches only ~30% thread-level
  reconstruction accuracy — useful for recall on missing links, but far from the
  certainty a mailbox view requires.
- Email threads are also large and topically heterogeneous in practice (Kooti,
  Aiello, Grbovic, Lerman, & Mantrach, 2015, characterize replying behavior
  over 16 billion messages; Zhang, Celikyilmaz, Gao, & Bansal, 2021, curate
  2,549 real email threads for EmailSum), so a wrong content-based merge is both
  likely and costly at scale.
- Naruon therefore optimizes for *precision* — never merging unrelated messages —
  because a wrong merge silently corrupts a user's mailbox view. The invariant is
  pinned by `test_forwarded_subject_alone_does_not_merge_unrelated_thread`.
- The #1192 In-Reply-To fix improves *recall on the header-complete path* (it
  no longer drops multi-parent / CFWS replies) with **zero** precision cost,
  because it stays entirely within the deterministic header graph.

The cited papers are bookmarked in the shared alphaXiv library folder
"CWL · Naruon email/threading standards grounding".

## References (APA 7)

- Resnick, P. (Ed.). (2008). *Internet message format* (RFC 5322). RFC Editor.
  https://www.rfc-editor.org/rfc/rfc5322.txt
- Moore, K. (1996). *MIME (Multipurpose Internet Mail Extensions) part three:
  Message header extensions for non-ASCII text* (RFC 2047). RFC Editor.
  https://www.rfc-editor.org/rfc/rfc2047.txt
- Kooti, F., Aiello, L. M., Grbovic, M., Lerman, K., & Mantrach, A. (2015).
  *Evolution of conversations in the age of email overload* [Preprint]. arXiv.
  https://arxiv.org/abs/1504.00704
- Mohiuddin, T., Joty, S., & Nguyen, D. T. (2018). *Coherence modeling of
  asynchronous conversations: A neural entity grid approach* [Preprint]. arXiv.
  https://arxiv.org/abs/1805.02275
- Zhang, S., Celikyilmaz, A., Gao, J., & Bansal, M. (2021). *EmailSum:
  Abstractive email thread summarization* [Preprint]. arXiv.
  https://arxiv.org/abs/2107.14691

## Preservation notes

- Original standard text and paper PDFs are referenced by their canonical
  RFC Editor / arXiv URLs above and are bookmarked in the alphaXiv library
  folder named in the design-rationale section. They are not committed here
  because this sandbox's outbound proxy blocks `rfc-editor.org` and `arxiv.org`;
  when a network-enabled run can fetch them, drop the RFC text into
  `standards/` and the PDFs into `pdfs/` following the sibling packs' layout.
- Git LFS is intentionally not used, consistent with the other
  `docs/research/*` packs.

## Governance notes

- Work item: `ContextualWisdomLab/naruon#1192` (RFC 5322 / RFC 2047 email-ingest
  correctness + coverage).
- Verification: threading/parser suites pass with `--noconftest`;
  `threading_service.py` at 100% and `email_parser.py` at 98% branch coverage
  (the RFC 2047 `_format_display_address` helper is fully covered).
