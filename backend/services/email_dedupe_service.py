import datetime
import hashlib
import json
from dataclasses import dataclass

from db.models import Email
from services.threading_service import normalize_message_id


@dataclass(frozen=True)
class EmailDedupeCandidate:
    candidate_key: str
    message_id: str | None = None
    sender: str | None = None
    recipients: str | None = None
    subject: str | None = None
    date: datetime.datetime | None = None
    body: str | None = None


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
    if not (
        sender
        and sender.strip()
        and subject
        and subject.strip()
        and date is not None
        and body
        and body.strip()
    ):
        return None
    fingerprint_source = json.dumps(
        [sender, subject, _date_to_fingerprint_value(date), body],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


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
    return strong_email_fingerprint(
        sender=email_row.sender,
        subject=email_row.subject,
        date=email_row.date,
        body=email_row.body,
    )
