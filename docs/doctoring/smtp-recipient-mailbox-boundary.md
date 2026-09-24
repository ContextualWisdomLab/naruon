# SMTP recipient mailbox validation boundary

## Decision

The local connector is an external-input anti-corruption boundary. Its `send_smtp` adapter must convert the caller's `to` value into one canonical mailbox before constructing `EmailMessageParams`. Non-empty text is not sufficient validation.

The protected API path already models `to` as Pydantic `EmailStr`, while protected `backend/runner/local_mail_adapters.py` accepted any non-empty string. Protected `backend/services/email_client.py` then assigned that text to an `EmailMessage` header. Python's message parser may reinterpret malformed address text instead of preserving the caller's literal mailbox intent. For example, a standalone reproduction on the current Python runtime turns `user@example.com> AUTH=<attacker@example.com` into the parsed `To` value `user@example.com` rather than rejecting the payload. That is a fail-open intent mismatch even though the current Naruon transport calls `SMTP.send_message`.

The repair uses the already-pinned `email-validator==2.3.0` dependency at the connector boundary with `check_deliverability=False`. Syntax and Unicode/domain normalization are therefore deterministic and do not add DNS/network I/O. Invalid mailbox syntax becomes the existing `invalid_payload` envelope before any provider call. Valid domains are normalized before provider use.

## RED → causal repair

RED commit `822543bb37070a63437d60c190b01161503003ce` adds two focused contracts:

- `user@example.com> AUTH=<attacker@example.com` must fail as `invalid_payload` before `send_email` is called;
- `recipient@EXAMPLE.COM` must reach the provider boundary as `recipient@example.com`.

Protected source at the RED parent performs only `isinstance(value, str)` plus `value.strip()`, so the malformed payload reaches `send_email` and the normalization expectation is false.

Causal fix `e07ff4df5f5daa107daec4d331c70e7192163770` adds `_required_smtp_mailbox`, validates with `email_validator.validate_email(..., check_deliverability=False)`, translates `EmailNotValidError` into the existing invalid-payload contract, and passes the normalized mailbox into `EmailMessageParams`. No SMTP host/port, credential, provider, retry, throttling, message-body, dependency, workflow, or database behavior is changed.

The new production helper has a docstring. The focused tests exercise both the accepted and rejected validation paths. Repository-hosted exact-head evidence is still required; local/standalone parser reproduction is not a substitute for Application CI, security gates, independent review, or a live provider test.

## Dependency-security boundary

Protected Naruon currently pins `aiosmtplib==5.1.2`. Upstream aiosmtplib 5.1.3 additionally rejects whitespace/angle-bracket address forms that can inject ESMTP command parameters into direct `mail`, `rcpt`, `vrfy`, `expn`, and `sendmail` calls; the published vulnerability is CVE-2026-90467. Naruon's current `_send_pinned_smtp_message` calls `SMTP.send_message(message)` rather than those direct address APIs, so this PR does **not** claim that CVE-2026-90467 is currently exploitable through the Naruon send path.

Version adoption remains dependency-owner work. Dependabot PR #1749 currently mixes the 5.1.2→5.1.3 aiosmtplib bump with 75 other backend updates, while #1752 owns dependency-grouping policy and already identifies aiosmtplib as an independent security update. This product repair therefore does not copy a dependency delta into the connector lane.

## Rejected alternatives

- **Rely only on `EmailMessage` parsing.** Rejected because malformed caller text can be silently reinterpreted, so the executed recipient can differ from the requested string without an explicit invalid-payload result.
- **Strip suspicious characters.** Rejected because mutation of malformed address syntax creates ambiguous intent; fail-closed validation is preferable.
- **Perform DNS/deliverability validation on every send.** Rejected because mailbox syntax normalization should not add an external DNS dependency to the local connector dispatch path.
- **Bundle aiosmtplib 5.1.3 here.** Rejected because dependency source has its own owner/policy lane and the current product transport does not use the directly affected address APIs.

## Verification

Focused repository target after the causal fix:

```bash
cd backend
python -m pytest -q -W error \
  tests/test_runner_mail_recipient_validation.py \
  tests/test_runner_mail_adapters.py
python -m ruff check \
  runner/local_mail_adapters.py \
  tests/test_runner_mail_recipient_validation.py
```

Acceptance requires the unchanged final head to receive the repository's required hosted checks, zero valid current-head review findings, and qualifying independent post-last-push review. A queued/pending run is not GREEN.

## References

Klensin, J. (2008). *Simple Mail Transfer Protocol* (RFC 5321). Internet Engineering Task Force. https://doi.org/10.17487/RFC5321

MITRE. (2026). *CVE-2026-90467: aiosmtplib before 5.1.3 ESMTP parameter injection via unvalidated addresses*. CVE Program. https://www.cve.org/CVERecord?id=CVE-2026-90467

Vink, C. (2026). *aiosmtplib 5.1.3 release notes*. GitHub. https://github.com/cole/aiosmtplib/releases/tag/v5.1.3
