"""Acceptance tests for Slice 3 buyer-visible inline-media quarantine persist."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from services.email_media_quarantine import (
    CLOSED_QUARANTINE_ERROR_CODES,
    EmailMediaQuarantinePersistError,
    InMemoryEmailMediaQuarantineStore,
    customer_next_action_for_error_code,
    persist_email_media_quarantine,
    persist_resolved_email_media_quarantine,
)
from services.email_media_resolution import (
    ContinuedDocumentImage,
    EmailInlineMediaResolution,
    QuarantinedInlineMedia,
    resolve_email_inline_media,
)
from services.email_parser import parse_eml, parse_eml_bytes

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "email_media_admission"
TRACKING_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
)


def _fixture_bytes(file_name: str) -> bytes:
    """Read one synthetic RFC 5322 admission fixture as raw message bytes."""
    return (FIXTURE_DIRECTORY / file_name).read_bytes()


def _related_image_message(
    *,
    html_body: str,
    content_id: str,
    content_type: str,
    payload: bytes,
    filename: str | None = None,
    content_location: str | None = None,
) -> bytes:
    """Build a multipart/related message with one inline image part."""
    disposition = "inline"
    if filename is not None:
        disposition = f'inline; filename="{filename}"'
    location_header = (
        f"Content-Location: {content_location}\r\n" if content_location else ""
    )
    return (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="rel-bound"; type="text/html"\r\n'
        "\r\n"
        "--rel-bound\r\n"
        'Content-Type: text/html; charset="utf-8"\r\n'
        "\r\n"
        f"{html_body}\r\n"
        "--rel-bound\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-ID: <{content_id}>\r\n"
        f"{location_header}"
        f"Content-Disposition: {disposition}\r\n"
        "Content-Transfer-Encoding: base64\r\n"
        "\r\n"
    ).encode("ascii") + base64.b64encode(payload) + b"\r\n--rel-bound--\r\n"


def test_closed_error_code_set_excludes_document_image() -> None:
    """Persist may record only the three admission drop codes, never document_image."""
    assert CLOSED_QUARANTINE_ERROR_CODES == frozenset(
        {
            "tracking_pixel",
            "unsupported_media",
            "unresolved_cid_reference",
        }
    )
    assert "document_image" not in CLOSED_QUARANTINE_ERROR_CODES


def test_customer_next_action_names_withheld_tracker() -> None:
    """Buyer copy is the next action: the tracker was withheld from any model."""
    assert customer_next_action_for_error_code("tracking_pixel") == (
        "This inline image was withheld as a tracking pixel. "
        "It was not sent to a model."
    )


def test_persist_records_resolution_tracking_pixel_without_source_bytes() -> None:
    """A resolved 1x1 tracker becomes one durable quarantine row from admission output."""
    resolution = resolve_email_inline_media(_fixture_bytes("tracking_pixel_1x1.eml"))
    store = InMemoryEmailMediaQuarantineStore()

    persisted = persist_resolved_email_media_quarantine(
        store=store,
        message_record_id=41,
        media_resolution=resolution,
    )

    assert len(persisted) == 1
    record = persisted[0]
    assert record.message_record_id == 41
    assert record.admission_error_code == "tracking_pixel"
    assert record.content_id_value == "open-pixel@naruon.test"
    assert record.source_part_index is not None
    assert record.source_bytes_sha256 is not None
    assert len(record.source_bytes_sha256) == 64
    assert record.evidence_boundary_label == "known"
    assert record.created_at.tzinfo is not None
    assert record.customer_next_action == customer_next_action_for_error_code(
        "tracking_pixel"
    )
    assert not hasattr(record, "payload_bytes")
    assert not hasattr(record, "source_bytes")
    assert "list-manage.com" not in repr(record)
    assert store.list_records(41) == persisted


def test_reparse_of_same_message_does_not_duplicate_quarantine_rows() -> None:
    """Idempotent upsert keeps one row when the same message is parsed again."""
    raw_message = _fixture_bytes("tracking_pixel_1x1.eml")
    store = InMemoryEmailMediaQuarantineStore()

    first = persist_resolved_email_media_quarantine(
        store=store,
        message_record_id=42,
        media_resolution=resolve_email_inline_media(raw_message),
    )
    second = persist_resolved_email_media_quarantine(
        store=store,
        message_record_id=42,
        media_resolution=resolve_email_inline_media(raw_message),
    )

    assert len(first) == 1
    assert second == first
    assert store.list_records(42) == first


def test_parse_eml_bytes_persists_dropped_filename_tracker() -> None:
    """The parse path records a named 1x1 CID tracker when it is dropped."""
    raw_message = _related_image_message(
        html_body='<p>Newsletter</p><img src="cid:open-pixel@naruon.test">',
        content_id="open-pixel@naruon.test",
        content_type="image/gif",
        payload=TRACKING_PIXEL_GIF,
        filename="open.gif",
        content_location="https://click.list-manage.com/track/open.php?u=fixture",
    )
    store = InMemoryEmailMediaQuarantineStore()

    parsed = parse_eml_bytes(
        raw_message,
        message_record_id=43,
        quarantine_store=store,
    )

    assert parsed["attachments"] == []
    records = store.list_records(43)
    assert len(records) == 1
    assert records[0].admission_error_code == "tracking_pixel"
    assert records[0].content_id_value == "open-pixel@naruon.test"
    assert records[0].customer_next_action == customer_next_action_for_error_code(
        "tracking_pixel"
    )


def test_parse_eml_persists_unresolved_cid_from_file(tmp_path: Path) -> None:
    """parse_eml records an unresolved CID so a later parse keeps the next action."""
    eml_path = tmp_path / "unresolved.eml"
    eml_path.write_bytes(_fixture_bytes("unresolved_cid.eml"))
    store = InMemoryEmailMediaQuarantineStore()

    parsed = parse_eml(
        eml_path,
        message_record_id=44,
        quarantine_store=store,
    )

    records = store.list_records(44)
    assert parsed["attachments"] == []
    assert len(records) == 1
    assert records[0].admission_error_code == "unresolved_cid_reference"
    assert records[0].content_id_value == "missing@naruon.test"
    assert records[0].source_bytes_sha256 is None
    assert records[0].source_part_index is None
    assert records[0].customer_next_action == customer_next_action_for_error_code(
        "unresolved_cid_reference"
    )


def test_resolve_path_persists_when_store_is_provided() -> None:
    """resolve_email_inline_media records dropped parts before returning them."""
    store = InMemoryEmailMediaQuarantineStore()

    result = resolve_email_inline_media(
        _fixture_bytes("tracking_pixel_1x1.eml"),
        message_record_id=45,
        quarantine_store=store,
    )

    assert result.document_images == ()
    assert [item.error_code for item in result.quarantined_media] == ["tracking_pixel"]
    assert [item.admission_error_code for item in store.list_records(45)] == [
        "tracking_pixel"
    ]


def test_document_image_parse_does_not_persist_a_quarantine() -> None:
    """A resolving CID chart continues as document evidence and is not quarantined."""
    store = InMemoryEmailMediaQuarantineStore()

    parsed = parse_eml_bytes(
        _fixture_bytes("cid_related_document_image.eml"),
        message_record_id=46,
        quarantine_store=store,
    )

    assert parsed["inline_media_resolution"].document_images[0].media_classification == (
        "document_image"
    )
    assert store.list_records(46) == ()


def test_persist_failure_fails_closed_and_does_not_continue_tracker() -> None:
    """A store failure must raise; the tracker must not become document_image."""

    class _FailingStore(InMemoryEmailMediaQuarantineStore):
        def upsert_records(self, records):  # type: ignore[no-untyped-def]
            raise RuntimeError("quarantine store unavailable")

    with pytest.raises(EmailMediaQuarantinePersistError, match="persist_failed"):
        parse_eml_bytes(
            _fixture_bytes("tracking_pixel_1x1.eml"),
            message_record_id=47,
            quarantine_store=_FailingStore(),
        )


def test_persist_rejects_document_image_as_quarantine() -> None:
    """Callers cannot launder a document_image through the quarantine table."""
    store = InMemoryEmailMediaQuarantineStore()
    document_row = QuarantinedInlineMedia(
        source_part_index=0,
        content_id="chart@naruon.test",
        content_sha256="ab" * 32,
        media_classification="document_image",
        error_code="document_image",
        evidence_boundary="known",
        raw_reference=None,
    )

    with pytest.raises(EmailMediaQuarantinePersistError, match="closed_error_code"):
        persist_email_media_quarantine(
            store=store,
            message_record_id=48,
            quarantined_media=(document_row,),
        )
    assert store.list_records(48) == ()


def test_empty_quarantine_is_a_successful_no_op() -> None:
    """No dropped parts means persist writes nothing and does not fail closed."""
    store = InMemoryEmailMediaQuarantineStore()
    resolution = EmailInlineMediaResolution(
        document_images=(
            ContinuedDocumentImage(
                source_part_index=1,
                content_id="chart@naruon.test",
                content_sha256="cd" * 32,
                media_classification="document_image",
                evidence_boundary="known",
                declared_content_type="image/png",
            ),
        ),
        quarantined_media=(),
        remote_fetch_policy="disabled",
    )

    persisted = persist_resolved_email_media_quarantine(
        store=store,
        message_record_id=49,
        media_resolution=resolution,
    )

    assert persisted == ()
    assert store.list_records(49) == ()
