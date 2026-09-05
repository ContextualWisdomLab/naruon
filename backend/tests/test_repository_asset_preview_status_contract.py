"""Focused status contracts for repository asset previews.

These tests keep recognition state separate from unrelated embedding work,
prevent retained binary payloads from being rendered after PDF recognition
failure, and keep preview responses within a bounded buyer-facing payload.
"""

from types import SimpleNamespace

from services.repository_asset_preview import (
    build_attachment_preview,
    build_document_preview,
)


def _document(*, status: str, content: str) -> SimpleNamespace:
    """Return the minimum document shape consumed by the preview service."""

    return SimpleNamespace(document_status=status, document_content=content)


def test_failed_pdf_status_blocks_retained_binary_payload() -> None:
    """A failed PDF recognition state must never expose retained upload bytes."""

    preview = build_document_preview(
        "doc-pdf-failed",
        _document(
            status="pdf_dom_recognition_failed",
            content="JVBERi0xLjQKcmV0YWluZWQtYmFzZTY0LXBkZi1ieXRlcw==",
        ),
    )

    assert preview.preview_state == "failed"
    assert preview.paragraph_texts == ()
    assert preview.preview_text is None
    assert preview.error_code == "pdf_dom_recognition_failed"


def test_embedding_pending_keeps_existing_text_readable() -> None:
    """Embedding regeneration must not hide already-recognized document text."""

    preview = build_document_preview(
        "doc-embedding-pending",
        _document(
            status="embedding_pending",
            content="Readable source text\n\nSecond paragraph.",
        ),
    )

    assert preview.preview_state == "recognized"
    assert preview.paragraph_texts == (
        "Readable source text",
        "Second paragraph.",
    )
    assert preview.preview_text == "Readable source text\n\nSecond paragraph."
    assert preview.error_code is None


def test_oversized_document_preview_fails_closed_without_returning_partial_text() -> None:
    """Oversized document text must not become a multi-megabyte preview payload."""

    preview = build_document_preview(
        "doc-too-large-for-inline-preview",
        _document(status="uploaded", content="A" * 65_537),
    )

    assert preview.preview_state == "unavailable"
    assert preview.paragraph_texts == ()
    assert preview.preview_text is None
    assert preview.error_code == "repository_asset_preview_too_large"


def test_oversized_hwpx_segments_fail_closed_without_returning_partial_text() -> None:
    """Large recognized HWPX segments stay out of the inline preview response."""

    attachment = SimpleNamespace(
        parser_key="hwpx",
        parse_status="hwpx_xml_package_parsed",
        content="",
        content_segments=[
            SimpleNamespace(ordinal_index=0, safe_text_content="가" * 65_537),
        ],
    )

    preview = build_attachment_preview("asset-large-hwpx", attachment)

    assert preview.preview_state == "unavailable"
    assert preview.paragraph_texts == ()
    assert preview.preview_text is None
    assert preview.error_code == "repository_asset_preview_too_large"
