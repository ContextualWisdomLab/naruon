"""Buyer-visible read of already-persisted email media quarantine rows."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from services.email_media_quarantine_read import (
    TRACKING_PIXEL_NEXT_ACTION,
    UNSUPPORTED_MEDIA_NEXT_ACTION,
    UNRESOLVED_CID_NEXT_ACTION,
    EmailMediaQuarantineReadError,
    customer_next_action_for_admission_error_code,
    list_email_media_quarantine_records,
)


def _persisted_row(**overrides: object) -> SimpleNamespace:
    payload = {
        "quarantine_record_id": 99,
        "message_record_id": 31,
        "source_part_index": 2,
        "content_id_value": "open-pixel@naruon.test",
        "source_bytes_sha256": "a" * 64,
        "admission_error_code": "tracking_pixel",
        "evidence_boundary_label": "known",
        "created_at": datetime.datetime(2026, 8, 17, 10, 0, tzinfo=datetime.timezone.utc),
        "payload_bytes": b"not-for-ui",
        "source_bytes": b"not-for-ui",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_customer_copy_uses_the_three_buyer_next_actions() -> None:
    """UI copy is the next action for each closed persisted admission code."""
    assert customer_next_action_for_admission_error_code("tracking_pixel") == (
        TRACKING_PIXEL_NEXT_ACTION
    )
    assert customer_next_action_for_admission_error_code("unsupported_media") == (
        UNSUPPORTED_MEDIA_NEXT_ACTION
    )
    assert customer_next_action_for_admission_error_code(
        "unresolved_cid_reference"
    ) == UNRESOLVED_CID_NEXT_ACTION
    assert TRACKING_PIXEL_NEXT_ACTION == (
        "This inline image was withheld as a tracking pixel. "
        "It was not sent to a model."
    )
    assert UNSUPPORTED_MEDIA_NEXT_ACTION == (
        "This inline part is unsupported and was withheld. "
        "It was not sent to a model."
    )
    assert UNRESOLVED_CID_NEXT_ACTION == (
        "This cid: image could not be resolved from the same message "
        "and was withheld. It was not sent to a model."
    )


def test_unknown_or_document_image_codes_fail_closed() -> None:
    """Read mapping does not invent a second classifier or default copy."""
    with pytest.raises(EmailMediaQuarantineReadError) as unknown:
        customer_next_action_for_admission_error_code("document_image")
    assert unknown.value.error_code == "closed_error_code"
    with pytest.raises(EmailMediaQuarantineReadError) as missing:
        customer_next_action_for_admission_error_code("")
    assert missing.value.error_code == "closed_error_code"


def test_list_maps_persisted_rows_without_bytes_or_record_ids() -> None:
    """Buyer rows expose purpose-bound next action, not withheld image bytes."""
    records = list_email_media_quarantine_records(
        (
            _persisted_row(),
            _persisted_row(
                quarantine_record_id=100,
                admission_error_code="unsupported_media",
                content_id_value="vector@naruon.test",
                source_part_index=3,
            ),
            _persisted_row(
                quarantine_record_id=101,
                admission_error_code="unresolved_cid_reference",
                content_id_value="missing@naruon.test",
                source_part_index=None,
                source_bytes_sha256=None,
            ),
        )
    )

    assert [record.admission_error_code for record in records] == [
        "tracking_pixel",
        "unsupported_media",
        "unresolved_cid_reference",
    ]
    assert [record.customer_next_action for record in records] == [
        TRACKING_PIXEL_NEXT_ACTION,
        UNSUPPORTED_MEDIA_NEXT_ACTION,
        UNRESOLVED_CID_NEXT_ACTION,
    ]
    assert records[0].content_id_value == "open-pixel@naruon.test"
    for record in records:
        assert not hasattr(record, "quarantine_record_id")
        assert not hasattr(record, "payload_bytes")
        assert not hasattr(record, "source_bytes")
        assert "http" not in record.customer_next_action


def test_list_fails_closed_to_empty_for_blank_or_unknown_rows() -> None:
    """Empty persist set and unknown codes do not invent withheld-media rows."""
    assert list_email_media_quarantine_records(()) == ()
    assert list_email_media_quarantine_records([]) == ()
    assert list_email_media_quarantine_records("not-rows") == ()
    assert list_email_media_quarantine_records(b"not-rows") == ()
    assert list_email_media_quarantine_records(None) == ()
    assert list_email_media_quarantine_records(31) == ()
    assert (
        list_email_media_quarantine_records(
            (_persisted_row(content_id_value=31),)
        )[0].content_id_value
        is None
    )
    assert (
        list_email_media_quarantine_records(
            (
                _persisted_row(admission_error_code="document_image"),
                _persisted_row(admission_error_code="not_a_quarantine"),
            )
        )
        == ()
    )
