"""Focused status contracts for repository document previews.

These tests keep recognition state separate from unrelated embedding work and
prevent retained binary payloads from being rendered after PDF recognition
failure.
"""

from types import SimpleNamespace

from services.repository_asset_preview import build_document_preview


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
