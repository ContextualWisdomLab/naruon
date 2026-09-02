# MIME attachment filename identity and parser authority

**Status:** open-PR evidence only; not yet shipped on protected `develop`.

## Boundary under repair

Naruon receives attachment filenames from Python's MIME parser and uses them for two different purposes: a human-facing display/storage filename and, only when the declared media type is generic, a filename-extension hint for parser selection. Those purposes must not share a representation-transform pipeline.

The display/storage projection may remove known active markup and literal path segments. The parser-authority projection must not be derived from that sanitized display value, because percent decoding, entity decoding, markup stripping, control deletion, or whitespace normalization can manufacture a recognized suffix that the sender did not present to the parser boundary.

The current PR therefore keeps the two projections separate. Generic-MIME extension fallback uses only the literal parser-authority projection. C0, DEL, and C1 control-bearing filenames fail closed to `attachment` for both display and parser selection; percent/entity text remains literal unless the MIME parser itself has already decoded a standards-defined MIME parameter encoding.

## Standards traceability

RFC 2183 defines the MIME `Content-Disposition` filename as a sender-suggested value, not trusted local authority. Section 2.3 requires a receiving MUA to check and possibly change the suggested filename so it conforms to local conventions and does not present a security problem, and says apparent directory path information should not be respected. Naruon therefore treats the value as a terminal component and rejects representations that are unsafe for display or parser authority.

RFC 2231 extends MIME parameter values with character-set/language information and percent-encoded octets. That decoding belongs to the MIME parameter layer. With Python `policy.default`, `Message.get_filename()` already performs the RFC 2231 decoding before Naruon's attachment parser receives the filename. Naruon must not apply a second URL-style percent decode to that already-decoded identity.

A production-ingress probe also shows why control characters need an explicit fail-closed rule. The RFC 2231 parameter `filename*=utf-8''quarterly%0A.json` is exposed by `Message.get_filename()` as `quarterly\n.json`. Without a control guard, `Path(...).suffix` still returns `.json`, allowing a generic `application/octet-stream` part to select the JSON parser while the display/storage value contains a line control. The regression contract fixes that exact MIME ingress rather than testing an artificial helper-only string.

## TDD and implementation traceability

- Protected base: `develop@042b0c70531b229af3acbd0421a2f23098d848b3`.
- Existing representation-separation causal head: `fea71c7fc2b49d7d47b0c91862786bccddd29d07`.
- Control-character RED: `288136ef8b1a6ffd4c1d910fcd9654d25671f9d1` adds RFC 2231 newline ingress plus C0/C1 unit cases. On the predecessor implementation, control-bearing values remain display filenames and a trailing `.json` retains generic-MIME parser authority.
- Causal fix: `92ec6151d11d9b125880a0405dab9ef59bc9293a` adds `_has_unsafe_filename_control()` and applies it before either display projection or parser-authority projection.
- Product code: `backend/services/attachment_parser.py`.
- Production-ingress regression: `backend/tests/test_attachment_filename_identity.py::test_rfc2231_control_character_filename_fails_closed`.
- Edge regression: `backend/tests/test_attachment_filename_identity.py::test_filename_controls_fail_closed_before_display_or_parser_selection`.

No CardDAV/DAV/HTTP URL canonicalization, declared non-generic MIME type, attachment payload parser, PDF byte validation, or ordinary body-text sanitization is changed by this decision.

## Verification required before merge

The unchanged exact PR head must run the focused filename/parser suite and the normal Python 3.14 suite, then pass all repository-required security, dependency, coverage, image, SBOM/provenance, and review gates. The focused command is:

```bash
cd backend
python -m pytest tests/test_attachment_filename_identity.py tests/test_attachment_parser.py -q
```

Queued, absent, startup-failed, predecessor-head, or author-only evidence is non-passing. The current organization Actions queue/startup failure is tracked through the canonical `.github` owner path rather than by weakening Naruon's required checks.

## References (APA 7th)

Freed, N., & Moore, K. (1997). *MIME parameter value and encoded word extensions: Character sets, languages, and continuations* (RFC 2231). RFC Editor. https://doi.org/10.17487/RFC2231

Troost, R., Dorner, S., & Moore, K. (1997). *Communicating presentation information in Internet messages: The Content-Disposition header field* (RFC 2183). RFC Editor. https://doi.org/10.17487/RFC2183
