"""Build read-only repository-asset previews from already recognized text.

This module does not recognize HWPX, call a model, or reconstruct layout. It
only maps stored attachment or document evidence into a buyer-visible preview
state so missing text cannot be mistaken for empty content.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from services.text_safety import strip_html_markup

PreviewState = Literal["recognized", "pending", "failed", "unavailable"]
AssetType = Literal["email_attachment", "workspace_document"]

ERROR_REPOSITORY_ASSET_NOT_FOUND = "repository_asset_not_found"
ERROR_HWPX_RECOGNITION_PENDING = "hwpx_recognition_pending"
ERROR_HWPX_RECOGNITION_FAILED = "hwpx_recognition_failed"

NEXT_ACTION_READ_RECOGNIZED_TEXT = "read_recognized_text"
NEXT_ACTION_WAIT_FOR_RECOGNITION = "wait_for_recognition"
NEXT_ACTION_CHOOSE_ANOTHER_FILE = "choose_another_file"

HWPX_PENDING_STATUS = "hwpx_xml_package_pending"
HWPX_PARSED_STATUS = "hwpx_xml_package_parsed"
HWPX_FAILED_STATUS = "hwpx_xml_package_failed"
HWPX_PARSER_FAMILY = "hwpx"

_DEFERRED_PENDING_STATUSES = frozenset(
    {
        HWPX_PENDING_STATUS,
        "pdf_dom_recognition_pending",
        "hwp_conversion_pending",
        "embedding_pending",
    }
)
_FAILED_PARSE_STATUSES = frozenset(
    {
        HWPX_FAILED_STATUS,
        "invalid_hwpx_payload",
        "invalid_hwp_payload",
        "invalid_pdf_payload",
    }
)
_DOCUMENT_PENDING_STATUSES = frozenset(
    {
        "embedding_pending",
        "hwp_conversion_pending",
        "pdf_dom_recognition_pending",
    }
)


@dataclass(frozen=True, slots=True)
class RepositoryAssetPreview:
    """Carry one scoped, read-only preview for an attachment or document."""

    asset_key: str
    asset_type: AssetType
    preview_state: PreviewState
    parser_family: str | None
    paragraph_texts: tuple[str, ...]
    preview_text: str | None
    next_action: str
    error_code: str | None
    provider_write_executed: bool = False


def _safe_paragraph(value: object) -> str:
    """Return one display-safe paragraph, or an empty string when absent."""

    return strip_html_markup(str(value or "")).strip()


def _paragraphs_from_text(value: str | None) -> tuple[str, ...]:
    """Split stored recognized text into ordered non-empty paragraphs."""

    if not value:
        return ()
    return tuple(
        paragraph
        for paragraph in (
            _safe_paragraph(part) for part in str(value).split("\n\n")
        )
        if paragraph
    )


def _paragraphs_from_segments(source: object) -> tuple[str, ...]:
    """Return content-graph paragraphs in ordinal order when they exist."""

    if isinstance(source, (list, tuple)):
        segments = list(source)
    else:
        segments = list(getattr(source, "content_segments", None) or [])
    if not segments:
        return ()
    ordered = sorted(
        segments,
        key=lambda segment: int(getattr(segment, "ordinal_index", 0)),
    )
    return tuple(
        paragraph
        for paragraph in (
            _safe_paragraph(getattr(segment, "safe_text_content", ""))
            for segment in ordered
        )
        if paragraph
    )


def _recognized_preview(
    *,
    asset_key: str,
    asset_type: AssetType,
    parser_family: str | None,
    paragraph_texts: tuple[str, ...],
) -> RepositoryAssetPreview:
    """Build a recognized preview only when paragraph text is actually present."""

    return RepositoryAssetPreview(
        asset_key=asset_key,
        asset_type=asset_type,
        preview_state="recognized",
        parser_family=parser_family,
        paragraph_texts=paragraph_texts,
        preview_text="\n\n".join(paragraph_texts),
        next_action=NEXT_ACTION_READ_RECOGNIZED_TEXT,
        error_code=None,
        provider_write_executed=False,
    )


def _blocked_preview(
    *,
    asset_key: str,
    asset_type: AssetType,
    preview_state: Literal["pending", "failed"],
    parser_family: str | None,
    next_action: str,
    error_code: str,
) -> RepositoryAssetPreview:
    """Build a pending or failed preview that never pretends text is empty."""

    return RepositoryAssetPreview(
        asset_key=asset_key,
        asset_type=asset_type,
        preview_state=preview_state,
        parser_family=parser_family,
        paragraph_texts=(),
        preview_text=None,
        next_action=next_action,
        error_code=error_code,
        provider_write_executed=False,
    )


def build_attachment_preview(
    asset_key: str,
    attachment: object,
    content_segments: Sequence[object] | None = None,
) -> RepositoryAssetPreview:
    """Map one email attachment onto a buyer-visible read-only preview."""

    parser_family = str(getattr(attachment, "parser_key", "") or "") or None
    parse_status = str(getattr(attachment, "parse_status", "") or "")
    is_hwpx = parser_family == HWPX_PARSER_FAMILY or parse_status.startswith("hwpx_")

    if parse_status in _DEFERRED_PENDING_STATUSES:
        return _blocked_preview(
            asset_key=asset_key,
            asset_type="email_attachment",
            preview_state="pending",
            parser_family=parser_family,
            next_action=NEXT_ACTION_WAIT_FOR_RECOGNITION,
            error_code=(
                ERROR_HWPX_RECOGNITION_PENDING
                if is_hwpx
                else "recognition_pending"
            ),
        )
    if parse_status in _FAILED_PARSE_STATUSES:
        return _blocked_preview(
            asset_key=asset_key,
            asset_type="email_attachment",
            preview_state="failed",
            parser_family=parser_family,
            next_action=NEXT_ACTION_CHOOSE_ANOTHER_FILE,
            error_code=(
                ERROR_HWPX_RECOGNITION_FAILED
                if is_hwpx
                else "recognition_failed"
            ),
        )

    paragraph_texts = _paragraphs_from_segments(
        content_segments if content_segments is not None else attachment
    )
    if not paragraph_texts and parse_status in {HWPX_PARSED_STATUS, "parsed"}:
        paragraph_texts = _paragraphs_from_text(
            str(getattr(attachment, "content", "") or "")
        )
    if paragraph_texts:
        return _recognized_preview(
            asset_key=asset_key,
            asset_type="email_attachment",
            parser_family=parser_family,
            paragraph_texts=paragraph_texts,
        )
    return _blocked_preview(
        asset_key=asset_key,
        asset_type="email_attachment",
        preview_state="failed",
        parser_family=parser_family,
        next_action=NEXT_ACTION_CHOOSE_ANOTHER_FILE,
        error_code=(
            ERROR_HWPX_RECOGNITION_FAILED if is_hwpx else "recognition_failed"
        ),
    )


def build_document_preview(
    asset_key: str,
    document: object,
) -> RepositoryAssetPreview:
    """Map one workspace document onto a buyer-visible read-only preview."""

    document_status = str(getattr(document, "document_status", "") or "")
    if document_status in _DOCUMENT_PENDING_STATUSES:
        return _blocked_preview(
            asset_key=asset_key,
            asset_type="workspace_document",
            preview_state="pending",
            parser_family=None,
            next_action=NEXT_ACTION_WAIT_FOR_RECOGNITION,
            error_code="recognition_pending",
        )
    paragraph_texts = _paragraphs_from_text(
        getattr(document, "document_content", None)
    )
    if paragraph_texts:
        return _recognized_preview(
            asset_key=asset_key,
            asset_type="workspace_document",
            parser_family=None,
            paragraph_texts=paragraph_texts,
        )
    return _blocked_preview(
        asset_key=asset_key,
        asset_type="workspace_document",
        preview_state="failed",
        parser_family=None,
        next_action=NEXT_ACTION_CHOOSE_ANOTHER_FILE,
        error_code="document_content_unavailable",
    )
