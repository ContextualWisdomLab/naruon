"""Boundary coverage for purpose-bound email-media quarantine persist."""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from services import email_media_admission as admission
from services import email_media_quarantine as quarantine
from services.email_media_resolution import (
    QuarantinedInlineMedia,
    resolve_email_inline_media,
)
from services.email_parser import parse_eml_bytes


def _png_header(width: int, height: int) -> bytes:
    """Return a signature-bearing PNG whose IHDR carries the given size."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"payload"
    )


def _related_message(
    html_body: str,
    image_parts: list[tuple[str, str, bytes, str | None, str | None]],
) -> bytes:
    """Build a multipart/related message with optional image filenames."""
    raw = (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="rel"; type="text/html"\r\n'
        "\r\n"
        "--rel\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html_body}\r\n"
    ).encode("utf-8")
    for content_id, content_type, payload, content_location, filename in image_parts:
        headers = (
            f"--rel\r\nContent-Type: {content_type}\r\n"
            f"Content-ID: <{content_id}>\r\n"
        )
        if content_location is not None:
            headers += f"Content-Location: {content_location}\r\n"
        if filename is not None:
            headers += f'Content-Disposition: inline; filename="{filename}"\r\n'
        raw += (
            headers.encode("ascii")
            + b"Content-Transfer-Encoding: base64\r\n\r\n"
            + base64.b64encode(payload)
            + b"\r\n"
        )
    return raw + b"--rel--\r\n"


def _quarantined(
    *,
    error_code: str,
    source_part_index: int | None = 0,
    content_id: str | None = "part@naruon.test",
    content_sha256: str | None = "ab" * 32,
    media_classification: str | None = None,
    evidence_boundary: str | None = "known",
) -> QuarantinedInlineMedia:
    """Build one already-classified quarantine outcome for persist tests."""
    return QuarantinedInlineMedia(
        source_part_index=source_part_index,
        content_id=content_id,
        content_sha256=content_sha256,
        media_classification=media_classification or error_code,
        error_code=error_code,
        evidence_boundary=evidence_boundary,
        raw_reference=None,
    )


def test_customer_copy_covers_every_closed_error_code() -> None:
    """Each persistable error_code has a withheld-from-model next action."""
    assert quarantine.customer_next_action_for_error_code("unsupported_media") == (
        "This inline image was withheld as unsupported media. "
        "It was not sent to a model."
    )
    assert quarantine.customer_next_action_for_error_code(
        "unresolved_cid_reference"
    ) == (
        "This inline image was withheld as an unresolved CID reference. "
        "It was not sent to a model."
    )


def test_unknown_error_code_has_no_customer_copy() -> None:
    """Unknown codes fail closed instead of inventing buyer copy."""
    with pytest.raises(
        quarantine.EmailMediaQuarantinePersistError, match="closed_error_code"
    ):
        quarantine.customer_next_action_for_error_code("document_image")


def test_persist_records_unsupported_media_from_resolution() -> None:
    """SVG and signature-mismatched parts persist as unsupported_media only."""
    raw_message = _related_message(
        '<p>images</p><img src="cid:vector@naruon.test">',
        [
            ("vector@naruon.test", "image/svg+xml", b"<svg></svg>", None, "logo.svg"),
        ],
    )
    store = quarantine.InMemoryEmailMediaQuarantineStore()

    resolve_email_inline_media(
        raw_message,
        message_record_id=61,
        quarantine_store=store,
    )

    records = store.list_records(61)
    assert [item.admission_error_code for item in records] == ["unsupported_media"]
    assert records[0].content_id_value == "vector@naruon.test"
    assert records[0].source_bytes_sha256 is not None


def test_persist_requires_message_record_id_when_store_is_provided() -> None:
    """A store without message identity is fail-closed, not a silent skip."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    with pytest.raises(
        quarantine.EmailMediaQuarantinePersistError, match="message_record_id"
    ):
        resolve_email_inline_media(
            _related_message(
                '<img src="cid:vector@naruon.test">',
                [
                    (
                        "vector@naruon.test",
                        "image/svg+xml",
                        b"<svg></svg>",
                        None,
                        None,
                    )
                ],
            ),
            quarantine_store=store,
        )
    assert store.list_records(0) == ()


def test_parse_without_store_still_drops_tracker() -> None:
    """Existing parse callers without a store keep the drop-only contract."""
    parsed = parse_eml_bytes(
        _related_message(
            '<img src="cid:open-pixel@naruon.test">',
            [
                (
                    "open-pixel@naruon.test",
                    "image/gif",
                    b"GIF89a" + (1).to_bytes(2, "little") + (1).to_bytes(2, "little"),
                    "https://click.list-manage.com/track/open.php?u=fixture",
                    "open.gif",
                )
            ],
        )
    )

    assert parsed["attachments"] == []
    assert {
        item.error_code
        for item in parsed["inline_media_resolution"].quarantined_media
    } == {"tracking_pixel"}


def test_persist_rejects_non_integer_message_record_id() -> None:
    """Message identity must be the durable email_records primary key."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    with pytest.raises(quarantine.EmailMediaQuarantinePersistError, match="message_record_id"):
        quarantine.persist_email_media_quarantine(
            store=store,
            message_record_id="41",  # type: ignore[arg-type]
            quarantined_media=(_quarantined(error_code="tracking_pixel"),),
        )


def test_persist_rejects_unknown_error_code() -> None:
    """A second classifier vocabulary cannot enter the quarantine table."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    with pytest.raises(
        quarantine.EmailMediaQuarantinePersistError, match="closed_error_code"
    ):
        quarantine.persist_email_media_quarantine(
            store=store,
            message_record_id=62,
            quarantined_media=(_quarantined(error_code="logo_signature"),),
        )
    assert store.list_records(62) == ()


def test_persist_rejects_non_sequence_quarantine_input() -> None:
    """Persist consumes already-produced resolution tuples, not raw MIME."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    with pytest.raises(quarantine.EmailMediaQuarantinePersistError, match="quarantined_media"):
        quarantine.persist_email_media_quarantine(
            store=store,
            message_record_id=63,
            quarantined_media="not-a-sequence",  # type: ignore[arg-type]
        )


def test_list_records_is_scoped_to_one_message() -> None:
    """Buyer-visible rows stay bound to the persisted message identity."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    quarantine.persist_email_media_quarantine(
        store=store,
        message_record_id=64,
        quarantined_media=(_quarantined(error_code="tracking_pixel"),),
    )
    quarantine.persist_email_media_quarantine(
        store=store,
        message_record_id=65,
        quarantined_media=(
            _quarantined(
                error_code="unresolved_cid_reference",
                source_part_index=None,
                content_sha256=None,
                media_classification=None,
                content_id="missing@naruon.test",
            ),
        ),
    )

    assert [item.message_record_id for item in store.list_records(64)] == [64]
    assert [item.admission_error_code for item in store.list_records(65)] == [
        "unresolved_cid_reference"
    ]
    assert store.list_records(66) == ()


def test_session_store_upserts_new_rows_and_skips_existing_identity() -> None:
    """SQLAlchemy-backed persist adds only missing identities, then reuses them."""
    added: list[object] = []
    session = SimpleNamespace(add=added.append)
    existing = [
        SimpleNamespace(
            message_record_id=70,
            source_part_index=0,
            source_bytes_sha256="ab" * 32,
            content_id_value="part@naruon.test",
            admission_error_code="tracking_pixel",
            evidence_boundary_label="known",
            created_at=quarantine._aware_now(),
        )
    ]
    store = quarantine.SessionAddEmailMediaQuarantineStore(
        session,
        existing_records=existing,
    )
    first = _quarantined(error_code="tracking_pixel")
    second = _quarantined(
        error_code="unsupported_media",
        source_part_index=1,
        content_id="vector@naruon.test",
        content_sha256="cd" * 32,
    )

    persisted = quarantine.persist_email_media_quarantine(
        store=store,
        message_record_id=70,
        quarantined_media=(first, second),
    )

    assert [item.admission_error_code for item in persisted] == [
        "tracking_pixel",
        "unsupported_media",
    ]
    assert len(added) == 1
    created = added[0]
    assert created.admission_error_code == "unsupported_media"
    assert created.message_record_id == 70
    assert created.content_id_value == "vector@naruon.test"
    assert not hasattr(created, "payload_bytes")
    assert store.list_records(70)[0].admission_error_code == "tracking_pixel"


def test_store_persist_error_is_reraised_without_wrapping() -> None:
    """A deterministic store error_code must survive the persist wrapper."""

    class _CodedStore(quarantine.InMemoryEmailMediaQuarantineStore):
        def upsert_records(self, records):  # type: ignore[no-untyped-def]
            raise quarantine.EmailMediaQuarantinePersistError(
                "persist_failed",
                "store rejected the upsert",
            )

    with pytest.raises(
        quarantine.EmailMediaQuarantinePersistError, match="persist_failed"
    ) as captured:
        quarantine.persist_email_media_quarantine(
            store=_CodedStore(),
            message_record_id=85,
            quarantined_media=(_quarantined(error_code="tracking_pixel"),),
        )
    assert captured.value.error_code == "persist_failed"


def test_session_store_failure_is_fail_closed() -> None:
    """A session.add failure cannot continue a tracker as document evidence."""

    class _BrokenSession:
        def add(self, _record: object) -> None:
            raise RuntimeError("flush failed")

    store = quarantine.SessionAddEmailMediaQuarantineStore(_BrokenSession())
    with pytest.raises(quarantine.EmailMediaQuarantinePersistError, match="persist_failed"):
        quarantine.persist_email_media_quarantine(
            store=store,
            message_record_id=71,
            quarantined_media=(_quarantined(error_code="tracking_pixel"),),
        )


def test_quarantine_identity_uses_part_hash_and_content_id() -> None:
    """Closest durable identity is message, part index, hash, and Content-ID."""
    identity = quarantine.quarantine_record_identity(
        message_record_id=72,
        source_part_index=3,
        source_bytes_sha256="ef" * 32,
        content_id_value="scan@naruon.test",
    )
    assert identity == (72, 3, "ef" * 32, "scan@naruon.test")


def test_admission_constants_remain_the_persist_closed_set() -> None:
    """Persist does not invent a second classifier vocabulary."""
    assert quarantine.TRACKING_PIXEL_ERROR_CODE == (
        admission.TRACKING_PIXEL_CLASSIFICATION
    )
    assert quarantine.UNSUPPORTED_MEDIA_ERROR_CODE == (
        admission.UNSUPPORTED_MEDIA_CLASSIFICATION
    )
    assert quarantine.UNRESOLVED_CID_ERROR_CODE == admission.UNRESOLVED_CID_ERROR_CODE
    assert quarantine.DOCUMENT_IMAGE_CLASSIFICATION == (
        admission.DOCUMENT_IMAGE_CLASSIFICATION
    )


def test_persist_error_exposes_deterministic_error_code() -> None:
    """Route layers can map persist failures without parsing message text."""
    error = quarantine.EmailMediaQuarantinePersistError(
        "persist_failed",
        "quarantine persist failed",
    )
    assert error.error_code == "persist_failed"
    assert "persist_failed" in str(error)


def test_persist_parsed_email_binds_resolution_to_message() -> None:
    """Import/IMAP save paths persist from parse_eml_bytes resolution output."""
    added: list[object] = []
    session = SimpleNamespace(add=added.append)
    parsed = parse_eml_bytes(
        _related_message(
            '<img src="cid:open-pixel@naruon.test">',
            [
                (
                    "open-pixel@naruon.test",
                    "image/gif",
                    b"GIF89a" + (1).to_bytes(2, "little") + (1).to_bytes(2, "little"),
                    None,
                    None,
                )
            ],
        )
    )

    records = quarantine.persist_parsed_email_media_quarantine(
        session=session,
        message_record_id=80,
        parsed_email=parsed,
    )

    assert [item.admission_error_code for item in records] == ["tracking_pixel"]
    assert added
    assert added[0].message_record_id == 80


def test_persist_parsed_email_without_resolution_is_no_op() -> None:
    """Older parse payloads without a resolution must not invent quarantine rows."""
    added: list[object] = []
    session = SimpleNamespace(add=added.append)

    records = quarantine.persist_parsed_email_media_quarantine(
        session=session,
        message_record_id=81,
        parsed_email={},
    )

    assert records == ()
    assert added == []


def test_persist_resolved_rejects_missing_quarantined_media() -> None:
    """Persist does not invent drop outcomes from an incomplete resolution."""
    store = quarantine.InMemoryEmailMediaQuarantineStore()
    with pytest.raises(
        quarantine.EmailMediaQuarantinePersistError, match="quarantined_media"
    ):
        quarantine.persist_resolved_email_media_quarantine(
            store=store,
            message_record_id=83,
            media_resolution=SimpleNamespace(),
        )


def test_session_store_reuses_write_dto_existing_records() -> None:
    """Already-built write DTOs stay first-wins identities on re-parse."""
    existing = quarantine.persist_email_media_quarantine(
        store=quarantine.InMemoryEmailMediaQuarantineStore(),
        message_record_id=84,
        quarantined_media=(_quarantined(error_code="tracking_pixel"),),
    )
    session = SimpleNamespace(add=lambda _record: None)
    store = quarantine.SessionAddEmailMediaQuarantineStore(
        session,
        existing_records=existing,
    )
    persisted = quarantine.persist_email_media_quarantine(
        store=store,
        message_record_id=84,
        quarantined_media=(_quarantined(error_code="tracking_pixel"),),
    )
    assert persisted == existing


def test_persist_parsed_email_rejects_non_mapping() -> None:
    """Persist reads EmailData mappings only; raw MIME is not a second classifier."""
    with pytest.raises(quarantine.EmailMediaQuarantinePersistError, match="parsed_email"):
        quarantine.persist_parsed_email_media_quarantine(
            session=SimpleNamespace(add=lambda _record: None),
            message_record_id=82,
            parsed_email="not-email-data",
        )
