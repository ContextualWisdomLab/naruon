"""Security bounds for deferred HWPX package recognition."""

from __future__ import annotations

import io
import zipfile

import pytest

from services import attachment_parser as parser


def _hwpx_bytes(
    *,
    mimetype: bytes = b"application/hwp+zip",
    extra_entries: tuple[str, ...] = (),
    duplicate_mimetype: bool = False,
) -> bytes:
    """Build a small HWPX-shaped package with configurable ZIP metadata."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", mimetype)
        if duplicate_mimetype:
            archive.writestr("mimetype", mimetype)
        archive.writestr("version.xml", '<version app="Naruon" />')
        archive.writestr("Contents/content.hpf", "<package />")
        archive.writestr("Contents/section0.xml", "<section />")
        for entry_name in extra_entries:
            archive.writestr(entry_name, b"")
    return buffer.getvalue()


def _parse_hwpx(payload: bytes):
    """Run the public import boundary with an explicit HWPX media type."""
    return parser.parse_email_attachment(
        filename="bounded.hwpx",
        content_type="application/hwp+zip",
        raw_content=payload,
    )


def test_hwpx_recognition_requires_exact_mimetype_signature() -> None:
    """Reject an ordinary ZIP that only imitates HWPX member names."""
    result = _parse_hwpx(_hwpx_bytes(mimetype=b"application/zip"))

    assert result.parse_status == "invalid_hwpx_payload"
    assert result.parse_error_code == "invalid_hwpx_payload"
    assert result.content == ""


def test_hwpx_recognition_rejects_ambiguous_duplicate_mimetype_entries() -> None:
    """Reject duplicate signature members instead of trusting ZIP lookup order."""
    with pytest.warns(UserWarning, match="Duplicate name"):
        payload = _hwpx_bytes(duplicate_mimetype=True)

    result = _parse_hwpx(payload)

    assert result.parse_status == "invalid_hwpx_payload"
    assert result.parse_error_code == "invalid_hwpx_payload"


def test_hwpx_recognition_bounds_central_directory_entry_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject package metadata that exceeds the bounded recognition budget."""
    monkeypatch.setattr(parser, "MAX_HWPX_ZIP_ENTRIES", 3)

    result = _parse_hwpx(_hwpx_bytes())

    assert result.parse_status == "invalid_hwpx_payload"


def test_hwpx_recognition_bounds_central_directory_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject an oversized ZIP directory before member inspection."""
    monkeypatch.setattr(parser, "MAX_HWPX_CENTRAL_DIRECTORY_BYTES", 1)

    result = _parse_hwpx(_hwpx_bytes())

    assert result.parse_status == "invalid_hwpx_payload"


def test_hwpx_recognition_bounds_aggregate_member_name_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject metadata expansion through many or very long member names."""
    monkeypatch.setattr(parser, "MAX_HWPX_ZIP_NAME_BYTES", 32)

    result = _parse_hwpx(
        _hwpx_bytes(extra_entries=(f"Contents/{'x' * 64}.xml",))
    )

    assert result.parse_status == "invalid_hwpx_payload"


def test_hwpx_recognition_bounds_mimetype_member_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a signature member that exceeds its tiny deterministic contract."""
    monkeypatch.setattr(parser, "MAX_HWPX_MIMETYPE_BYTES", 8)

    result = _parse_hwpx(_hwpx_bytes())

    assert result.parse_status == "invalid_hwpx_payload"


def test_hwpx_recognition_accepts_the_bounded_canonical_package() -> None:
    """Retain valid HWPX bytes after all package metadata checks pass."""
    payload = _hwpx_bytes()

    result = _parse_hwpx(payload)

    assert result.parse_status == "hwpx_xml_package_pending"
    assert result.parse_error_code is None
    assert (
        parser.decode_deferred_attachment_payload(
            result.content,
            "application/hwp+zip",
        )
        == payload
    )
