"""Build server-authoritative, bounded context for LLM email-writing review.

This module owns only authorization, canonical thread membership, chronology,
recipient-role derivation, deterministic size bounds, and trust labeling. It does
not classify prose, select context by keywords, infer communication quality, or
accept browser-supplied mail/thread participants.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from email.utils import getaddresses
from typing import Any, Literal, Protocol, cast

import regex
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext
from db.models import Email
from services.email_writing_contracts import EmailWritingReviewRequest
from services.threading_service import normalize_message_id

EmailTrustClass = Literal[
    "untrusted_email_content",
    "untrusted_authored_content",
]
ParticipantRole = Literal["sender", "reply_to", "recipient", "reply_target"]

MAX_THREAD_IDENTIFIER_CHARS = 512
MAX_SUBJECT_GRAPHEMES = 2_048
MAX_SELECTED_BODY_GRAPHEMES = 40_000
MAX_RELATED_BODY_GRAPHEMES = 30_000
MAX_INCREMENTAL_THREAD_MESSAGES = 8
MAX_DEEP_THREAD_MESSAGES = 24
MAX_THREAD_CANDIDATES = 96
MAX_CONTEXT_JSON_BYTES = 120_000

_GRAPHEME_PATTERN = regex.compile(r"\X")


class _EmailQueryResult(Protocol):
    """Minimal SQLAlchemy result surface used by the context builder."""

    def scalar_one_or_none(self) -> Email | None:
        """Return the selected row or ``None``."""

    def scalars(self) -> "_EmailQueryResult":
        """Return a scalar result view."""

    def all(self) -> list[Email]:
        """Return materialized email rows."""


class _EmailContextSession(Protocol):
    """Async execution surface accepted by production and deterministic tests."""

    async def execute(self, query: Any) -> _EmailQueryResult:
        """Execute one server-owned SQLAlchemy query."""


class EmailWritingContextError(RuntimeError):
    """Redacted typed failure for unavailable or insufficient email context."""

    def __init__(
        self,
        code: Literal["email_unavailable", "context_insufficient"],
        *,
        reason_code: str,
    ) -> None:
        """Create a stable failure without exposing tenant or message identity."""
        message = (
            "email_context_unavailable"
            if code == "email_unavailable"
            else "email_context_insufficient"
        )
        super().__init__(message)
        self.code = code
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class EmailWritingParticipant:
    """One participant role derived from persisted server-side headers."""

    source_email_id: int
    role_code: ParticipantRole
    address: str
    display_name: str | None
    trust_class: Literal["untrusted_email_content"] = "untrusted_email_content"

    def to_prompt_payload(self) -> dict[str, Any]:
        """Return a trust-labeled prompt representation of the participant."""
        return {
            "source_email_id": self.source_email_id,
            "role_code": self.role_code,
            "address": _tagged_text(self.address, self.trust_class),
            "display_name": _tagged_text(self.display_name, self.trust_class),
            "trust_class": self.trust_class,
        }


@dataclass(frozen=True, slots=True)
class EmailWritingMessageContext:
    """One immutable chronological message admitted by server thread policy."""

    email_id: int
    message_id: str
    sent_at: datetime.datetime
    subject: str
    sender_header: str
    reply_to_header: str | None
    recipient_header: str | None
    body: str
    selected_source: bool
    trust_class: Literal["untrusted_email_content"] = "untrusted_email_content"

    def to_prompt_payload(self) -> dict[str, Any]:
        """Return the complete message with every authored field trust-labeled."""
        return {
            "email_id": self.email_id,
            "message_id": self.message_id,
            "sent_at": self.sent_at.isoformat(),
            "subject": _tagged_text(self.subject, self.trust_class),
            "sender_header": _tagged_text(self.sender_header, self.trust_class),
            "reply_to_header": _tagged_text(
                self.reply_to_header,
                self.trust_class,
            ),
            "recipient_header": _tagged_text(
                self.recipient_header,
                self.trust_class,
            ),
            "body": _tagged_text(self.body, self.trust_class),
            "selected_source": self.selected_source,
            "trust_class": self.trust_class,
        }


@dataclass(frozen=True, slots=True)
class EmailWritingContextBundle:
    """Immutable authorized context consumed by the candidate-review prompt layer."""

    selected_email_id: int
    canonical_thread_id: str
    subject: str
    selected_source_message: EmailWritingMessageContext
    chronological_messages: tuple[EmailWritingMessageContext, ...]
    participant_roles: tuple[EmailWritingParticipant, ...]
    reply_objective: str | None
    current_draft: str
    declared_language_tag: str
    review_mode: Literal["incremental", "deep"]
    document_revision_digest: str
    projection_name: str
    projection_version: int
    context_limitations: tuple[str, ...]

    def to_prompt_payload(self) -> dict[str, Any]:
        """Return canonical prompt data with explicit untrusted-content boundaries."""
        return {
            "system_boundary": "email_writing_context_v1",
            "selected_email_id": self.selected_email_id,
            "canonical_thread_id": self.canonical_thread_id,
            "subject": _tagged_text(self.subject, "untrusted_email_content"),
            "selected_source_message": self.selected_source_message.to_prompt_payload(),
            "chronological_messages": [
                message.to_prompt_payload()
                for message in self.chronological_messages
            ],
            "participant_roles": [
                participant.to_prompt_payload()
                for participant in self.participant_roles
            ],
            "reply_objective": _tagged_text(
                self.reply_objective,
                "untrusted_authored_content",
            ),
            "current_draft": _tagged_text(
                self.current_draft,
                "untrusted_authored_content",
            ),
            "declared_language_tag": _tagged_text(
                self.declared_language_tag,
                "untrusted_authored_content",
            ),
            "review_mode": self.review_mode,
            "document_revision_digest": self.document_revision_digest,
            "projection_name": self.projection_name,
            "projection_version": self.projection_version,
            "context_limitations": list(self.context_limitations),
        }

    def to_prompt_json(self) -> str:
        """Serialize the complete bundle without truncating any JSON string."""
        return json.dumps(
            self.to_prompt_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def _tagged_text(value: str | None, trust_class: EmailTrustClass) -> dict[str, Any]:
    """Wrap one complete text value with its prompt trust classification."""
    return {"value": value, "trust_class": trust_class}


def _grapheme_count(value: str) -> int:
    """Count extended grapheme clusters without splitting Unicode text."""
    return sum(1 for _ in _GRAPHEME_PATTERN.finditer(value))


def _contains_non_scalar_unicode(value: str) -> bool:
    """Return whether persisted text contains an invalid surrogate code point."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _safe_server_text(value: Any, *, nullable: bool) -> str | None:
    """Validate persisted text as complete Unicode without browser coercion."""
    if value is None:
        if nullable:
            return None
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="required_server_text_missing",
        )
    text = str(value)
    if _contains_non_scalar_unicode(text):
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="invalid_server_unicode",
        )
    return text


def _canonical_selected_thread_id(email: Email) -> str:
    """Return a bounded canonical thread key or fail closed on malformed storage."""
    raw_identifier = email.thread_id if email.thread_id is not None else email.message_id
    if raw_identifier is None:
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="thread_identifier_missing",
        )
    raw_text = str(raw_identifier)
    if (
        not raw_text
        or len(raw_text) > MAX_THREAD_IDENTIFIER_CHARS
        or _contains_non_scalar_unicode(raw_text)
        or any(ord(character) < 0x20 for character in raw_text)
    ):
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="thread_identifier_invalid",
        )
    normalized = normalize_message_id(raw_text)
    if not normalized or len(normalized) > MAX_THREAD_IDENTIFIER_CHARS:
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="thread_identifier_invalid",
        )
    return normalized


def _thread_lookup_values(canonical_thread_id: str) -> tuple[str, ...]:
    """Return deterministic persisted forms used by the thread membership query."""
    return (canonical_thread_id, f"<{canonical_thread_id}>")


def _row_matches_owner(email: Email, auth_context: AuthContext) -> bool:
    """Defensively confirm a row matches the signed-session tenant scope."""
    return (
        email.user_id == auth_context.user_id
        and email.organization_id == auth_context.organization_id
    )


def _row_belongs_to_thread(email: Email, canonical_thread_id: str) -> bool:
    """Check canonical persisted thread/message identifiers without text semantics."""
    candidate_values = (email.thread_id, email.message_id)
    for candidate in candidate_values:
        if candidate is None:
            continue
        normalized = normalize_message_id(str(candidate))
        if normalized == canonical_thread_id:
            return True
    return False


def _normalized_message_id(email: Email) -> str:
    """Return a valid canonical message identity for de-duplication and prompts."""
    normalized = normalize_message_id(email.message_id)
    if (
        normalized is None
        or len(normalized) > MAX_THREAD_IDENTIFIER_CHARS
        or _contains_non_scalar_unicode(normalized)
        or any(ord(character) < 0x20 for character in normalized)
    ):
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="message_identifier_invalid",
        )
    return normalized


def _normalized_timestamp(value: datetime.datetime | None) -> datetime.datetime:
    """Normalize a persisted timestamp to timezone-aware UTC chronology."""
    if value is None:
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code="message_timestamp_missing",
        )
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _message_context(email: Email, *, selected_source: bool) -> EmailWritingMessageContext:
    """Validate one complete persisted message without truncating authored fields."""
    subject = cast(str, _safe_server_text(email.subject or "", nullable=False))
    body = cast(str, _safe_server_text(email.body, nullable=False))
    sender = cast(str, _safe_server_text(email.sender, nullable=False))
    reply_to = _safe_server_text(email.reply_to, nullable=True)
    recipients = _safe_server_text(email.recipients, nullable=True)
    if _grapheme_count(subject) > MAX_SUBJECT_GRAPHEMES:
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code=(
                "selected_subject_too_large"
                if selected_source
                else "related_subject_too_large"
            ),
        )
    body_limit = (
        MAX_SELECTED_BODY_GRAPHEMES
        if selected_source
        else MAX_RELATED_BODY_GRAPHEMES
    )
    if _grapheme_count(body) > body_limit:
        raise EmailWritingContextError(
            "context_insufficient",
            reason_code=(
                "selected_source_too_large"
                if selected_source
                else "related_message_too_large"
            ),
        )
    return EmailWritingMessageContext(
        email_id=email.id,
        message_id=_normalized_message_id(email),
        sent_at=_normalized_timestamp(email.date),
        subject=subject,
        sender_header=sender,
        reply_to_header=reply_to,
        recipient_header=recipients,
        body=body,
        selected_source=selected_source,
    )


def _parsed_addresses(value: str | None) -> tuple[tuple[str | None, str], ...]:
    """Parse complete persisted address headers and preserve stable header order."""
    if not value:
        return ()
    parsed: list[tuple[str | None, str]] = []
    seen: set[tuple[str | None, str]] = set()
    for display_name, address in getaddresses([value.replace(";", ",")]):
        normalized_address = address.strip().lower()
        if (
            not normalized_address
            or _contains_non_scalar_unicode(normalized_address)
            or any(ord(character) < 0x20 for character in normalized_address)
        ):
            continue
        normalized_display = display_name.strip() or None
        if normalized_display is not None and _contains_non_scalar_unicode(
            normalized_display
        ):
            continue
        candidate = (normalized_display, normalized_address)
        if candidate not in seen:
            seen.add(candidate)
            parsed.append(candidate)
    return tuple(parsed)


def _participant_roles(
    messages: tuple[EmailWritingMessageContext, ...],
    selected_message: EmailWritingMessageContext,
) -> tuple[EmailWritingParticipant, ...]:
    """Derive sender/reply/recipient roles only from admitted persisted headers."""
    participants: list[EmailWritingParticipant] = []
    seen: set[tuple[int, ParticipantRole, str]] = set()

    def add_roles(
        message: EmailWritingMessageContext,
        role_code: ParticipantRole,
        header_value: str | None,
    ) -> None:
        for display_name, address in _parsed_addresses(header_value):
            identity = (message.email_id, role_code, address)
            if identity in seen:
                continue
            seen.add(identity)
            participants.append(
                EmailWritingParticipant(
                    source_email_id=message.email_id,
                    role_code=role_code,
                    address=address,
                    display_name=display_name,
                )
            )

    for message in messages:
        add_roles(message, "sender", message.sender_header)
        add_roles(message, "reply_to", message.reply_to_header)
        add_roles(message, "recipient", message.recipient_header)

    reply_targets = _parsed_addresses(selected_message.reply_to_header)
    if not reply_targets:
        reply_targets = _parsed_addresses(selected_message.sender_header)
    for display_name, address in reply_targets:
        identity = (selected_message.email_id, "reply_target", address)
        if identity in seen:
            continue
        seen.add(identity)
        participants.append(
            EmailWritingParticipant(
                source_email_id=selected_message.email_id,
                role_code="reply_target",
                address=address,
                display_name=display_name,
            )
        )
    return tuple(participants)


def _append_limitation(limitations: list[str], code: str) -> None:
    """Append one stable limitation code at most once."""
    if code not in limitations:
        limitations.append(code)


def _message_cap(review_mode: Literal["incremental", "deep"]) -> int:
    """Return the documented chronology cap for the requested review mode."""
    if review_mode == "incremental":
        return MAX_INCREMENTAL_THREAD_MESSAGES
    return MAX_DEEP_THREAD_MESSAGES


def _cap_chronological_messages(
    messages: list[EmailWritingMessageContext],
    *,
    selected_email_id: int,
    review_mode: Literal["incremental", "deep"],
    limitations: list[str],
) -> list[EmailWritingMessageContext]:
    """Retain the selected source and most recent complete messages by chronology."""
    cap = _message_cap(review_mode)
    if len(messages) <= cap:
        return messages
    recent = list(messages[-cap:])
    if not any(message.email_id == selected_email_id for message in recent):
        selected = next(
            message for message in messages if message.email_id == selected_email_id
        )
        recent = [selected, *recent[-(cap - 1) :]]
        recent.sort(key=lambda message: (message.sent_at, message.email_id))
    _append_limitation(limitations, "older_thread_messages_omitted")
    return recent


def _build_bundle(
    *,
    request: EmailWritingReviewRequest,
    canonical_thread_id: str,
    messages: list[EmailWritingMessageContext],
    limitations: list[str],
) -> EmailWritingContextBundle:
    """Create one immutable bundle from admitted complete message objects."""
    selected = next(
        message for message in messages if message.email_id == request.source_email_id
    )
    message_tuple = tuple(messages)
    return EmailWritingContextBundle(
        selected_email_id=request.source_email_id,
        canonical_thread_id=canonical_thread_id,
        subject=selected.subject,
        selected_source_message=selected,
        chronological_messages=message_tuple,
        participant_roles=_participant_roles(message_tuple, selected),
        reply_objective=request.reply_objective,
        current_draft=request.draft_plain_text,
        declared_language_tag=request.language_tag,
        review_mode=request.review_mode,
        document_revision_digest=request.document_revision.digest_hex,
        projection_name=request.projection_name,
        projection_version=request.projection_version,
        context_limitations=tuple(limitations),
    )


def _apply_json_budget(
    *,
    request: EmailWritingReviewRequest,
    canonical_thread_id: str,
    messages: list[EmailWritingMessageContext],
    limitations: list[str],
) -> EmailWritingContextBundle:
    """Omit whole older messages until canonical JSON fits the byte budget."""
    retained = list(messages)
    while True:
        bundle = _build_bundle(
            request=request,
            canonical_thread_id=canonical_thread_id,
            messages=retained,
            limitations=limitations,
        )
        try:
            payload_size = len(bundle.to_prompt_json().encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise EmailWritingContextError(
                "context_insufficient",
                reason_code="prompt_unicode_invalid",
            ) from exc
        if payload_size <= MAX_CONTEXT_JSON_BYTES:
            return bundle
        removable_index = next(
            (
                index
                for index, message in enumerate(retained)
                if message.email_id != request.source_email_id
            ),
            None,
        )
        if removable_index is None:
            raise EmailWritingContextError(
                "context_insufficient",
                reason_code="selected_context_budget_exceeded",
            )
        retained.pop(removable_index)
        _append_limitation(limitations, "context_budget_omitted_messages")


async def build_email_writing_context(
    session: AsyncSession | _EmailContextSession,
    auth_context: AuthContext,
    request: EmailWritingReviewRequest,
) -> EmailWritingContextBundle:
    """Build an authorized context bundle from persisted email and thread rows."""
    owner_filters = Email.owner_filters(
        auth_context.user_id,
        auth_context.organization_id,
    )
    selected_result = await session.execute(
        select(Email)
        .where(
            Email.id == request.source_email_id,
            *owner_filters,
        )
        .limit(1)
    )
    selected_email = selected_result.scalar_one_or_none()
    if selected_email is None or not _row_matches_owner(selected_email, auth_context):
        raise EmailWritingContextError(
            "email_unavailable",
            reason_code="email_not_available_in_owner_scope",
        )

    canonical_thread_id = _canonical_selected_thread_id(selected_email)
    lookup_values = _thread_lookup_values(canonical_thread_id)
    thread_result = await session.execute(
        select(Email)
        .where(
            *owner_filters,
            or_(
                Email.thread_id.in_(lookup_values),
                Email.message_id.in_(lookup_values),
            ),
        )
        .order_by(Email.date.desc(), Email.id.desc())
        .limit(MAX_THREAD_CANDIDATES + 1)
    )
    raw_thread_rows = list(thread_result.scalars().all())
    limitations: list[str] = []
    if len(raw_thread_rows) > MAX_THREAD_CANDIDATES:
        raw_thread_rows = raw_thread_rows[:MAX_THREAD_CANDIDATES]
        _append_limitation(limitations, "thread_candidate_limit_applied")

    admitted_rows = [selected_email]
    admitted_rows.extend(
        email
        for email in raw_thread_rows
        if email.id != selected_email.id
        and _row_matches_owner(email, auth_context)
        and _row_belongs_to_thread(email, canonical_thread_id)
    )

    unique_messages: list[EmailWritingMessageContext] = []
    seen_message_ids: set[str] = set()
    for email in admitted_rows:
        selected_source = email.id == selected_email.id
        try:
            message = _message_context(email, selected_source=selected_source)
        except EmailWritingContextError:
            if selected_source:
                raise
            _append_limitation(limitations, "invalid_thread_message_omitted")
            continue
        if message.message_id in seen_message_ids:
            _append_limitation(limitations, "duplicate_thread_messages_removed")
            continue
        seen_message_ids.add(message.message_id)
        unique_messages.append(message)

    unique_messages.sort(key=lambda message: (message.sent_at, message.email_id))
    capped_messages = _cap_chronological_messages(
        unique_messages,
        selected_email_id=selected_email.id,
        review_mode=request.review_mode,
        limitations=limitations,
    )
    return _apply_json_budget(
        request=request,
        canonical_thread_id=canonical_thread_id,
        messages=capped_messages,
        limitations=limitations,
    )
