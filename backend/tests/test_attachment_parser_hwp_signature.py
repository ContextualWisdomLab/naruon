"""HWP binary signature admission tests for deferred conversion."""

from __future__ import annotations

import base64

import pytest

from services import attachment_parser as parser


def _ole_payload(*, include_hwp_signature: bool) -> bytes:
    """Build a bounded OLE-like payload with optional HWP FileHeader evidence."""
    payload = bytearray(parser._HWP_OLE_MAGIC)
    payload.extend(b"\x00" * 64)
    if include_hwp_signature:
        payload.extend(parser._HWP_DOCUMENT_SIGNATURE)
        payload.extend(b"\x00" * (32 - len(parser._HWP_DOCUMENT_SIGNATURE)))
    payload.extend(b"fixture body")
    return bytes(payload)


def test_hwp_admission_rejects_an_unrelated_ole_container() -> None:
    """Do not treat the generic Compound File signature as HWP authority."""
    result = parser.parse_email_attachment(
        filename="unrelated.hwp",
        content_type="application/x-hwp",
        raw_content=_ole_payload(include_hwp_signature=False),
    )

    assert result.parse_status == "invalid_hwp_payload"
    assert result.parse_error_code == "invalid_hwp_payload"
    assert result.content == ""


def test_hwp_admission_accepts_ole_plus_hwp_file_header_signature() -> None:
    """Queue a bounded payload only when both container and HWP identity exist."""
    payload = _ole_payload(include_hwp_signature=True)

    result = parser.parse_email_attachment(
        filename="document.hwp",
        content_type="application/x-hwp",
        raw_content=payload,
    )

    assert result.parse_status == "hwp_conversion_pending"
    assert result.parse_error_code is None
    assert (
        parser.decode_deferred_attachment_payload(
            result.content,
            "application/x-hwp",
        )
        == payload
    )


def test_hwp_deferred_decoder_rechecks_hwp_file_header_signature() -> None:
    """Keep stored-payload decoding fail-closed after import-time admission."""
    encoded = base64.b64encode(
        _ole_payload(include_hwp_signature=False)
    ).decode("ascii")

    with pytest.raises(ValueError, match="not a HWP binary"):
        parser.decode_deferred_attachment_payload(
            encoded,
            "application/x-hwp",
        )
