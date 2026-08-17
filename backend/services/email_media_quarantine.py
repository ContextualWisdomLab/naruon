"""Persist already-classified email inline-media quarantine outcomes.

This module is the #1350 Slice 3 buyer-visible persist boundary. It records
``tracking_pixel``, ``unsupported_media``, and ``unresolved_cid_reference``
outcomes already produced by ``admit_email_inline_media()`` /
``resolve_email_inline_media()``. It does not classify media, fetch remote
``http(s)`` URLs, store decoded image bytes or the email body, run OCR, a
VLM, NewsDOM, or a model, or copy the #1376 ``EmailMediaArtifact`` pixel
contract.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol

from services.email_media_admission import (
    DOCUMENT_IMAGE_CLASSIFICATION,
    TRACKING_PIXEL_CLASSIFICATION,
    UNRESOLVED_CID_ERROR_CODE,
    UNSUPPORTED_MEDIA_CLASSIFICATION,
)

TRACKING_PIXEL_ERROR_CODE = TRACKING_PIXEL_CLASSIFICATION
UNSUPPORTED_MEDIA_ERROR_CODE = UNSUPPORTED_MEDIA_CLASSIFICATION
CLOSED_QUARANTINE_ERROR_CODES = frozenset(
    {
        TRACKING_PIXEL_ERROR_CODE,
        UNSUPPORTED_MEDIA_ERROR_CODE,
        UNRESOLVED_CID_ERROR_CODE,
    }
)

CUSTOMER_NEXT_ACTIONS = {
    TRACKING_PIXEL_ERROR_CODE: (
        "This inline image was withheld as a tracking pixel. "
        "It was not sent to a model."
    ),
    UNSUPPORTED_MEDIA_ERROR_CODE: (
        "This inline image was withheld as unsupported media. "
        "It was not sent to a model."
    ),
    UNRESOLVED_CID_ERROR_CODE: (
        "This inline image was withheld as an unresolved CID reference. "
        "It was not sent to a model."
    ),
}


class EmailMediaQuarantinePersistError(Exception):
    """Fail-closed persist error with a deterministic ``error_code``."""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        super().__init__(f"{error_code}: {message}")


@dataclass(frozen=True)
class EmailMediaQuarantineWrite:
    """Purpose-bound quarantine row ready for durable upsert."""

    message_record_id: int
    source_part_index: int | None
    content_id_value: str | None
    source_bytes_sha256: str | None
    admission_error_code: str
    evidence_boundary_label: str | None
    created_at: datetime.datetime
    customer_next_action: str


class EmailMediaQuarantineStore(Protocol):
    """Durable upsert surface for purpose-bound quarantine rows."""

    def upsert_records(
        self, records: tuple[EmailMediaQuarantineWrite, ...]
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Insert missing identities and return the durable set."""

    def list_records(
        self, message_record_id: int
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Return rows already bound to one ``email_records`` identity."""


class InMemoryEmailMediaQuarantineStore:
    """Deterministic identity-map store used by parse-path persist tests."""

    def __init__(self) -> None:
        self._records: dict[
            tuple[int, int | None, str | None, str | None],
            EmailMediaQuarantineWrite,
        ] = {}

    def upsert_records(
        self, records: tuple[EmailMediaQuarantineWrite, ...]
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Keep the first row for each message/part/hash/Content-ID identity."""
        persisted: list[EmailMediaQuarantineWrite] = []
        for record in records:
            identity = quarantine_record_identity(
                message_record_id=record.message_record_id,
                source_part_index=record.source_part_index,
                source_bytes_sha256=record.source_bytes_sha256,
                content_id_value=record.content_id_value,
            )
            existing = self._records.get(identity)
            if existing is not None:
                persisted.append(existing)
                continue
            self._records[identity] = record
            persisted.append(record)
        return tuple(persisted)

    def list_records(
        self, message_record_id: int
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Return in-memory rows for one message identity, in insert order."""
        return tuple(
            record
            for record in self._records.values()
            if record.message_record_id == message_record_id
        )


class SessionAddEmailMediaQuarantineStore:
    """Add ORM rows for identities that are not already loaded."""

    def __init__(
        self,
        session: object,
        existing_records: Sequence[object] = (),
        record_factory: type | None = None,
    ) -> None:
        self._session = session
        self._record_factory = record_factory or SimpleNamespace
        self._identities: dict[
            tuple[int, int | None, str | None, str | None],
            EmailMediaQuarantineWrite,
        ] = {}
        for existing in existing_records:
            write = _write_from_existing(existing)
            identity = quarantine_record_identity(
                message_record_id=write.message_record_id,
                source_part_index=write.source_part_index,
                source_bytes_sha256=write.source_bytes_sha256,
                content_id_value=write.content_id_value,
            )
            self._identities[identity] = write

    def upsert_records(
        self, records: tuple[EmailMediaQuarantineWrite, ...]
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Insert missing identities through ``session.add``."""
        persisted: list[EmailMediaQuarantineWrite] = []
        for record in records:
            identity = quarantine_record_identity(
                message_record_id=record.message_record_id,
                source_part_index=record.source_part_index,
                source_bytes_sha256=record.source_bytes_sha256,
                content_id_value=record.content_id_value,
            )
            existing = self._identities.get(identity)
            if existing is not None:
                persisted.append(existing)
                continue
            self._session.add(  # type: ignore[attr-defined]
                self._record_factory(
                    message_record_id=record.message_record_id,
                    source_part_index=record.source_part_index,
                    content_id_value=record.content_id_value,
                    source_bytes_sha256=record.source_bytes_sha256,
                    admission_error_code=record.admission_error_code,
                    evidence_boundary_label=record.evidence_boundary_label,
                    created_at=record.created_at,
                )
            )
            self._identities[identity] = record
            persisted.append(record)
        return tuple(persisted)

    def list_records(
        self, message_record_id: int
    ) -> tuple[EmailMediaQuarantineWrite, ...]:
        """Return loaded plus newly added rows for one message identity."""
        return tuple(
            record
            for record in self._identities.values()
            if record.message_record_id == message_record_id
        )


def customer_next_action_for_error_code(error_code: str) -> str:
    """Return the buyer-visible next action for one closed quarantine code.

    Args:
        error_code: One persistable admission/resolution drop code.

    Returns:
        The withheld-from-model next action for that code.

    Raises:
        EmailMediaQuarantinePersistError: If ``error_code`` is outside the
            closed persist set, including ``document_image``.
    """
    next_action = CUSTOMER_NEXT_ACTIONS.get(error_code)
    if next_action is None:
        raise EmailMediaQuarantinePersistError(
            "closed_error_code",
            "quarantine error_code is outside the closed persist set",
        )
    return next_action


def quarantine_record_identity(
    *,
    message_record_id: int,
    source_part_index: int | None,
    source_bytes_sha256: str | None,
    content_id_value: str | None,
) -> tuple[int, int | None, str | None, str | None]:
    """Return the closest durable identity for one quarantine row.

    The user-visible unique key is message, part index, and source-byte
    SHA-256. Content-ID is included so unresolved CID rows, which have no
    part index or hash, remain distinct.
    """
    return (
        message_record_id,
        source_part_index,
        source_bytes_sha256,
        content_id_value,
    )


def persist_email_media_quarantine(
    *,
    store: EmailMediaQuarantineStore,
    message_record_id: int,
    quarantined_media: Sequence[object],
) -> tuple[EmailMediaQuarantineWrite, ...]:
    """Upsert already-produced quarantine outcomes for one message.

    Args:
        store: Durable upsert implementation.
        message_record_id: ``email_records`` primary key.
        quarantined_media: Outcomes from ``resolve_email_inline_media()``.

    Returns:
        The durable rows, reusing existing identities on re-parse.

    Raises:
        EmailMediaQuarantinePersistError: If identity, closed-set, or store
            persist checks fail. Callers must not continue a tracker as
            ``document_image``.
    """
    if type(message_record_id) is not int:
        raise EmailMediaQuarantinePersistError(
            "message_record_id",
            "message_record_id must be the email_records primary key",
        )
    if isinstance(quarantined_media, (str, bytes)) or not isinstance(
        quarantined_media, Sequence
    ):
        raise EmailMediaQuarantinePersistError(
            "quarantined_media",
            "quarantined_media must be resolution outcomes",
        )

    created_at = _aware_now()
    writes: list[EmailMediaQuarantineWrite] = []
    for item in quarantined_media:
        writes.append(
            _write_from_quarantined(
                message_record_id=message_record_id,
                item=item,
                created_at=created_at,
            )
        )
    try:
        return store.upsert_records(tuple(writes))
    except EmailMediaQuarantinePersistError:
        raise
    except Exception as exc:
        raise EmailMediaQuarantinePersistError(
            "persist_failed",
            "quarantine persist failed",
        ) from exc


def persist_resolved_email_media_quarantine(
    *,
    store: EmailMediaQuarantineStore,
    message_record_id: int,
    media_resolution: object,
) -> tuple[EmailMediaQuarantineWrite, ...]:
    """Persist ``quarantined_media`` already attached to one resolution."""
    quarantined_media = getattr(media_resolution, "quarantined_media", None)
    if not isinstance(quarantined_media, Sequence) or isinstance(
        quarantined_media, (str, bytes)
    ):
        raise EmailMediaQuarantinePersistError(
            "quarantined_media",
            "media_resolution must expose resolution quarantined_media",
        )
    return persist_email_media_quarantine(
        store=store,
        message_record_id=message_record_id,
        quarantined_media=quarantined_media,
    )


def persist_parsed_email_media_quarantine(
    *,
    session: object,
    message_record_id: int,
    parsed_email: object,
    existing_records: Sequence[object] = (),
    record_factory: type | None = None,
) -> tuple[EmailMediaQuarantineWrite, ...]:
    """Persist quarantine rows from a ``parse_eml`` / ``parse_eml_bytes`` mapping.

    Args:
        session: Unit-of-work object with ``add``.
        message_record_id: ``email_records`` primary key after flush.
        parsed_email: ``EmailData`` mapping from the existing parse path.
        existing_records: Already-loaded rows for idempotent re-parse.
        record_factory: ORM class or namespace factory for new rows.

    Returns:
        Durable rows for dropped parts, or an empty tuple when the parse
        payload has no resolution.

    Raises:
        EmailMediaQuarantinePersistError: If ``parsed_email`` is not a mapping
            or persist fails closed.
    """
    if not isinstance(parsed_email, Mapping):
        raise EmailMediaQuarantinePersistError(
            "parsed_email",
            "parsed_email must be an EmailData mapping",
        )
    media_resolution = parsed_email.get("inline_media_resolution")
    if media_resolution is None:
        return ()
    store = SessionAddEmailMediaQuarantineStore(
        session,
        existing_records=existing_records,
        record_factory=record_factory,
    )
    return persist_resolved_email_media_quarantine(
        store=store,
        message_record_id=message_record_id,
        media_resolution=media_resolution,
    )


def persist_resolution_if_requested(
    *,
    media_resolution: object,
    message_record_id: int | None,
    quarantine_store: EmailMediaQuarantineStore | None,
) -> None:
    """Record dropped parts when the parse/resolve caller supplied a store.

    Raises:
        EmailMediaQuarantinePersistError: If a store is provided without a
            message identity, or persist itself fails.
    """
    if quarantine_store is None:
        return
    if message_record_id is None:
        raise EmailMediaQuarantinePersistError(
            "message_record_id",
            "message_record_id is required when a quarantine store is provided",
        )
    persist_resolved_email_media_quarantine(
        store=quarantine_store,
        message_record_id=message_record_id,
        media_resolution=media_resolution,
    )


def _aware_now() -> datetime.datetime:
    """Return a timezone-aware UTC timestamp for new quarantine rows."""
    return datetime.datetime.now(datetime.timezone.utc)


def _write_from_quarantined(
    *,
    message_record_id: int,
    item: object,
    created_at: datetime.datetime,
) -> EmailMediaQuarantineWrite:
    """Copy purpose-bound fields from one resolution quarantine outcome."""
    media_classification = getattr(item, "media_classification", None)
    error_code = getattr(item, "error_code", None)
    if media_classification == DOCUMENT_IMAGE_CLASSIFICATION or (
        error_code not in CLOSED_QUARANTINE_ERROR_CODES
    ):
        raise EmailMediaQuarantinePersistError(
            "closed_error_code",
            "document_image and unknown codes cannot be quarantined",
        )
    return EmailMediaQuarantineWrite(
        message_record_id=message_record_id,
        source_part_index=getattr(item, "source_part_index", None),
        content_id_value=getattr(item, "content_id", None),
        source_bytes_sha256=getattr(item, "content_sha256", None),
        admission_error_code=error_code,
        evidence_boundary_label=getattr(item, "evidence_boundary", None),
        created_at=created_at,
        customer_next_action=customer_next_action_for_error_code(error_code),
    )


def _write_from_existing(existing: object) -> EmailMediaQuarantineWrite:
    """Rebuild a write DTO from a previously persisted row."""
    if isinstance(existing, EmailMediaQuarantineWrite):
        return existing
    error_code = getattr(existing, "admission_error_code")
    return EmailMediaQuarantineWrite(
        message_record_id=getattr(existing, "message_record_id"),
        source_part_index=getattr(existing, "source_part_index", None),
        content_id_value=getattr(existing, "content_id_value", None),
        source_bytes_sha256=getattr(existing, "source_bytes_sha256", None),
        admission_error_code=error_code,
        evidence_boundary_label=getattr(existing, "evidence_boundary_label", None),
        created_at=getattr(existing, "created_at"),
        customer_next_action=customer_next_action_for_error_code(error_code),
    )
