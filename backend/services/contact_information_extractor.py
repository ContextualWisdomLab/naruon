"""Pure, bounded contact-information extraction for explicitly supplied text."""

import re
from collections.abc import Iterable
from dataclasses import dataclass

MAX_CONTACT_INPUT_CHARS = 100_000
_EMAIL_ATOM = r"A-Za-z0-9!#$%&'*+/=?^_`{|}~"
_ASCII_EMAIL_PATTERN = re.compile(
    rf"(?<![{_EMAIL_ATOM}.-])"
    rf"[{_EMAIL_ATOM}-]+(?:\.[{_EMAIL_ATOM}-]+)*@"
    rf"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{{0,61}}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}(?![A-Za-z0-9-])"
)
_UNICODE_EMAIL_PATTERN = re.compile(
    rf"(?<![\w{_EMAIL_ATOM}.-])"
    rf"[\w{_EMAIL_ATOM}-]+(?:\.[\w{_EMAIL_ATOM}-]+)*@"
    r"(?:[^\W_](?:(?:[^\W_]|-){0,61}[^\W_])?\.)+"
    r"[^\W_]{2,63}(?![\w-])"
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+82[ .-]?10|010)[ .-]?\d{3,4}[ .-]?\d{4}"
    r"|\d{2,3}-\d{3,4}-\d{4}"
    r"|(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4})(?!\d)"
)


@dataclass(frozen=True)
class ContactInformationMatches:
    """Contact-like values found in source order without persistence or normalization."""

    email_addresses: tuple[str, ...]
    phone_numbers: tuple[str, ...]


def _mailbox_identity(value: str) -> tuple[str, str]:
    """Return exact local-part plus case-insensitive domain identity for one mailbox."""
    local_part, separator, domain_part = value.rpartition("@")
    if not separator:
        return value, ""
    return local_part, domain_part.casefold()


def _deduplicate_matches(
    matches: Iterable[re.Match[str]], *, preserve_mailbox_local_part: bool = False
) -> tuple[str, ...]:
    """Return unique match values in source order under the requested identity rule."""
    ordered_matches = sorted(matches, key=lambda match: (match.start(), match.end()))
    values: list[str] = []
    seen: set[object] = set()
    for match in ordered_matches:
        value = match.group(0)
        identity: object
        if preserve_mailbox_local_part:
            identity = _mailbox_identity(value)
        else:
            identity = value.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        values.append(value)
    return tuple(values)


def extract_contact_information(text: str) -> ContactInformationMatches:
    """Extract bounded email/phone patterns from caller-supplied text with no side effects.

    Mailbox local-parts are preserved and compared exactly while domains are compared
    case-insensitively. This avoids collapsing distinct SMTP mailboxes solely because
    their local-parts differ by case. The function does not log, persist, index, or
    transmit the input or extracted PII. Callers remain responsible for authorization,
    purpose limitation, retention, and any downstream disclosure. Pattern matching is
    intentionally bounded and is not a claim that every international email address or
    telephone numbering plan is recognized.
    """
    if len(text) > MAX_CONTACT_INPUT_CHARS:
        raise ValueError(
            f"Contact text must not exceed {MAX_CONTACT_INPUT_CHARS} characters"
        )

    email_matches = list(_ASCII_EMAIL_PATTERN.finditer(text))
    email_matches.extend(_UNICODE_EMAIL_PATTERN.finditer(text))
    phone_matches = _PHONE_PATTERN.finditer(text)
    return ContactInformationMatches(
        email_addresses=_deduplicate_matches(
            email_matches, preserve_mailbox_local_part=True
        ),
        phone_numbers=_deduplicate_matches(phone_matches),
    )
