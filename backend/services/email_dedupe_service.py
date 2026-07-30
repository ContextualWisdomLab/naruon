import datetime
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
    candidate_key: str
    message_id: str | None = None
    sender: str | None = None
    recipients: str | None = None
    subject: str | None = None
    date: datetime.datetime | None = None
    body: str | None = None
    date_provenance: str = "unknown"


def _date_to_fingerprint_value(value: datetime.datetime | None) -> str:
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
    normalized = normalize_message_id(candidate.message_id)
    if not normalized:
        return set()
    return {normalized, f"<{normalized}>"}


def candidate_strong_fingerprint(candidate: EmailDedupeCandidate) -> str | None:
    return strong_email_fingerprint(
        sender=candidate.sender,
        subject=candidate.subject,
        date=candidate.date,
        body=candidate.body,
    )


def email_strong_fingerprint(email_row: Email) -> str | None:
    # A stored row may seed a strong (auto-dedupe) fingerprint only when its
    # date is genuinely parsed sender metadata; rows with a synthetic or
    # unknown-provenance date are excluded so they cannot manufacture a strong
    # duplicate match (naruon#1086).
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
    # A date-independent identity signal: sender + subject + body only. Unlike
    # the strong fingerprint it does not include the Date, so it survives an
    # untrustworthy Date provenance (naruon#1086) and can flag a probable
    # duplicate that the strong path deliberately withholds. Requires a body so
    # empty-body rows cannot collapse to a shared hash.
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
    return content_email_fingerprint(
        sender=candidate.sender,
        subject=candidate.subject,
        body=candidate.body,
    )


def email_content_fingerprint(email_row: Email) -> str | None:
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
