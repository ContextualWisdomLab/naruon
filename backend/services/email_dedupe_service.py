"""Email de-duplication fingerprints and the Fellegi-Sunter decision classifier.

This module is the deterministic core the import/IMAP paths compose to decide
whether an incoming email is a duplicate of a stored one, keeping strong
(auto-merge) evidence gated on genuine Date provenance (naruon#1086).
"""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from db.models import Email
from services.email_service import generate_email_fingerprint
from services.threading_service import normalize_message_id

# Fellegi & Sunter (1969) partition each candidate/record pair into three
# decision zones: a positive link (A1), a non-link (A3), and an indeterminate
# "possible match" band (A2) reserved for clerical review. naruon#1086 maps that
# rule onto email de-duplication: a reliable identity link auto-merges, a
# probable duplicate that lacks a reliable link is held for review instead of
# being silently kept or silently merged, and everything else is distinct.
DedupeDecision = Literal["auto_link", "review_required", "distinct"]


@dataclass(frozen=True)
class EmailDedupeCandidate:
    """An incoming email reduced to the fields the dedupe decision needs.

    ``date_provenance`` mirrors the parser's classification of the ``date``
    field (``parsed`` for a genuine RFC822 Date, otherwise a synthetic
    collection-time fallback); only ``parsed`` may seed a strong auto-dedupe
    match (naruon#1086).
    """

    candidate_key: str
    message_id: str | None = None
    sender: str | None = None
    recipients: str | None = None
    subject: str | None = None
    date: datetime.datetime | None = None
    body: str | None = None
    date_provenance: str = "unknown"


def _date_to_fingerprint_value(value: datetime.datetime | None) -> str:
    """Render a datetime as its ISO-8601 fingerprint token (``""`` when None)."""
    if value is None:
        return ""
    return value.isoformat()


def strong_email_fingerprint(
    *,
    sender: str | None,
    subject: str | None,
    date: datetime.datetime | None,
    body: str | None,
) -> str | None:
    """Return the strong (sender+subject+Date+body) auto-dedupe fingerprint.

    Requires a body; ``None`` for an empty body so bodyless rows cannot collapse
    to a shared hash. Callers gate this on genuine Date provenance.
    """
    if not body:
        return None
    return generate_email_fingerprint(
        {
            "sender": sender or "",
            "subject": subject or "",
            "date": _date_to_fingerprint_value(date),
            "body": body,
        }
    )


def candidate_message_lookup_values(candidate: EmailDedupeCandidate) -> set[str]:
    """Return the bracketed and bare Message-ID lookup forms (empty if none)."""
    normalized = normalize_message_id(candidate.message_id)
    if not normalized:
        return set()
    return {normalized, f"<{normalized}>"}


def candidate_strong_fingerprint(candidate: EmailDedupeCandidate) -> str | None:
    """Return the candidate's strong fingerprint (see strong_email_fingerprint)."""
    return strong_email_fingerprint(
        sender=candidate.sender,
        subject=candidate.subject,
        date=candidate.date,
        body=candidate.body,
    )


def email_strong_fingerprint(email_row: Email) -> str | None:
    """Return a stored row's strong fingerprint, gated on genuine Date provenance.

    A stored row may seed a strong (auto-dedupe) fingerprint only when its date
    is genuinely parsed sender metadata; rows with a synthetic or
    unknown-provenance date are excluded so they cannot manufacture a strong
    duplicate match (naruon#1086).
    """
    if getattr(email_row, "date_provenance", None) != "parsed":
        return None
    return strong_email_fingerprint(
        sender=email_row.sender,
        subject=email_row.subject,
        date=email_row.date,
        body=email_row.body,
    )


def content_email_fingerprint(
    *,
    sender: str | None,
    subject: str | None,
    body: str | None,
) -> str | None:
    """Return a Date-independent content fingerprint (sender+subject+body).

    Unlike the strong fingerprint it omits the Date, so it survives an
    untrustworthy Date provenance (naruon#1086) and can flag a probable
    duplicate that the strong path deliberately withholds. Requires a body so
    empty-body rows cannot collapse to a shared hash.
    """
    if not body:
        return None
    return generate_email_fingerprint(
        {
            "sender": sender or "",
            "subject": subject or "",
            "date": "",
            "body": body,
        }
    )


def candidate_content_fingerprint(candidate: EmailDedupeCandidate) -> str | None:
    """Return the candidate's Date-independent content fingerprint."""
    return content_email_fingerprint(
        sender=candidate.sender,
        subject=candidate.subject,
        body=candidate.body,
    )


def email_content_fingerprint(email_row: Email) -> str | None:
    """Return a stored row's Date-independent content fingerprint."""
    return content_email_fingerprint(
        sender=email_row.sender,
        subject=email_row.subject,
        body=email_row.body,
    )


def classify_dedupe_decision(
    candidate: EmailDedupeCandidate, existing_row: Email
) -> DedupeDecision:
    """Assign a Fellegi-Sunter (1969) decision zone to a candidate/existing pair.

    - ``auto_link`` (A1, positive link): the pair shares a reliable identity
      link -- the same normalized Message-ID, or a genuine strong match
      (identical sender/subject/Date/body with a trusted, parsed Date on *both*
      sides). These are safe to merge automatically.
    - ``review_required`` (A2, possible match): the pair shares a
      provenance-independent content signal (same sender/subject/body) but has
      no reliable identity link -- typically because at least one side's Date
      provenance is synthetic or unknown, so the strong fingerprint was withheld
      (naruon#1086). This is the clerical-review band: a probable duplicate that
      must not be silently merged or silently kept.
    - ``distinct`` (A3, non-link): no shared identity or content signal.
    """
    candidate_message = normalize_message_id(candidate.message_id)
    existing_message = normalize_message_id(existing_row.message_id)
    if candidate_message and existing_message and candidate_message == existing_message:
        return "auto_link"

    candidate_strong = candidate_strong_fingerprint(candidate)
    existing_strong = email_strong_fingerprint(existing_row)
    if (
        candidate.date_provenance == "parsed"
        and candidate_strong is not None
        and existing_strong is not None
        and candidate_strong == existing_strong
    ):
        return "auto_link"

    candidate_content = candidate_content_fingerprint(candidate)
    existing_content = email_content_fingerprint(existing_row)
    if (
        candidate_content is not None
        and existing_content is not None
        and candidate_content == existing_content
    ):
        return "review_required"

    return "distinct"


def resolve_candidate_disposition(
    candidate: EmailDedupeCandidate, existing_rows: Iterable[Email]
) -> tuple[DedupeDecision, Email | None]:
    """Resolve a candidate against many stored rows to one Fellegi-Sunter disposition.

    Real de-duplication compares one incoming email against the *set* of stored
    rows it might duplicate, not a single row, so this collapses the per-pair
    ``classify_dedupe_decision`` results by the Fellegi & Sunter (1969) zone
    priority A1 > A2 > A3:

    - the first stored row that yields ``auto_link`` (A1, a reliable identity
      link) wins immediately -- a positive link cannot be outranked;
    - absent any link, the first ``review_required`` match (A2) is held for
      clerical review rather than silently merged or silently kept;
    - only when no stored row shares any identity or content signal is the
      candidate ``distinct`` (A3).

    Returns the decision together with the stored row that drove a link or a
    review hold (``None`` when distinct), so the import/IMAP paths know which
    email the disposition targets without re-deriving the match.
    """
    review_match: Email | None = None
    for existing_row in existing_rows:
        decision = classify_dedupe_decision(candidate, existing_row)
        if decision == "auto_link":
            return "auto_link", existing_row
        if decision == "review_required" and review_match is None:
            review_match = existing_row
    if review_match is not None:
        return "review_required", review_match
    return "distinct", None
