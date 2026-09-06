"""Read-only Inkspan edit handoff must fail closed without a Hangul engine.

Mail preview can already show recognized HWPX paragraphs. These tests require an
explicit buyer-visible ``Edit in Inkspan`` capability probe that preserves the
exact attachment identity, refuses silent HWPX-to-text conversion, never
overwrites the original, and does not invent a write API. Released Inkspan is a
Markdown/HTML editor; Hangul import/edit/export remains unreleased, so the
default installed capability is absent.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.inkspan_edit_handoff import (
    EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE,
    ERROR_INKSPAN_EDIT_CONTRACT_UNAVAILABLE,
    ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE,
    HANDOFF_STATE_UNAVAILABLE,
    NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT,
    build_inkspan_edit_handoff,
    installed_inkspan_editor_capability,
)
from services.repository_asset_preview import (
    NEXT_ACTION_READ_RECOGNIZED_TEXT,
    RepositoryAssetPreview,
    build_attachment_preview,
)


def _recognized_hwpx_preview() -> RepositoryAssetPreview:
    """Return one recognized HWPX preview with the exact source asset key."""

    return RepositoryAssetPreview(
        asset_key="asset_mail_hwpx_recognized",
        asset_type="email_attachment",
        preview_state="recognized",
        parser_family="hwpx",
        paragraph_texts=("Quarterly decision record", "Approve the next action."),
        preview_text="Quarterly decision record\n\nApprove the next action.",
        next_action=NEXT_ACTION_READ_RECOGNIZED_TEXT,
        error_code=None,
        provider_write_executed=False,
    )


def _hwpx_attachment(*, parse_status: str, content: str) -> SimpleNamespace:
    """Build one in-memory HWPX attachment for preview-to-handoff tests."""

    return SimpleNamespace(
        filename="decision.hwpx",
        content=content,
        content_type="application/hwp+zip",
        parse_content_type="application/hwp+zip",
        parser_key="hwpx",
        parse_status=parse_status,
        parse_error_code=None,
        content_segments=[
            SimpleNamespace(
                ordinal_index=0,
                safe_text_content="Quarterly decision record",
            ),
            SimpleNamespace(
                ordinal_index=1,
                safe_text_content="Approve the next action.",
            ),
        ],
    )


def test_installed_inkspan_editor_capability_is_absent_by_default() -> None:
    """Naruon has no released/installed Inkspan Hangul engine adapter."""

    assert installed_inkspan_editor_capability() is None


def test_recognized_hwpx_handoff_fails_closed_without_hangul_capability() -> None:
    """Recognized HWPX keeps identity and tells the buyer to keep reading."""

    handoff = build_inkspan_edit_handoff(_recognized_hwpx_preview())

    assert handoff is not None
    assert handoff.source_asset_key == "asset_mail_hwpx_recognized"
    assert handoff.source_asset_type == "email_attachment"
    assert handoff.parser_family == "hwpx"
    assert handoff.handoff_state == HANDOFF_STATE_UNAVAILABLE
    assert handoff.editor_capability_name == EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE
    assert handoff.mutation_allowed is False
    assert handoff.converts_source_to_plain_text is False
    assert handoff.overwrites_original is False
    assert handoff.provider_write_executed is False
    assert handoff.next_action == NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT
    assert handoff.error_code == ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE
    assert handoff.editable_document_payload is None
    assert "Quarterly decision record" not in repr(handoff)


def test_malformed_adapter_family_metadata_fails_closed_without_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-iterable accepted_source_families must not 500 a recognized preview."""

    monkeypatch.setattr(
        "services.inkspan_edit_handoff.registered_inkspan_editor_capability",
        lambda: SimpleNamespace(
            capability_name=EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE,
            accepted_source_families=1,
            mutation_contract_name=None,
        ),
    )

    handoff = build_inkspan_edit_handoff(_recognized_hwpx_preview())

    assert handoff is not None
    assert handoff.handoff_state == HANDOFF_STATE_UNAVAILABLE
    assert handoff.mutation_allowed is False
    assert handoff.provider_write_executed is False
    assert handoff.converts_source_to_plain_text is False
    assert handoff.overwrites_original is False
    assert handoff.editable_document_payload is None
    assert handoff.source_asset_key == "asset_mail_hwpx_recognized"
    assert handoff.error_code == ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE
    assert handoff.next_action == NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT


def test_markdown_only_inkspan_adapter_is_rejected_as_silent_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Released Markdown/HTML Inkspan must not receive HWPX as plain text."""

    monkeypatch.setattr(
        "services.inkspan_edit_handoff.registered_inkspan_editor_capability",
        lambda: SimpleNamespace(
            capability_name="inkspan_markdown_html_editor",
            accepted_source_families=("markdown", "html"),
            mutation_contract_name=None,
        ),
    )

    handoff = build_inkspan_edit_handoff(_recognized_hwpx_preview())

    assert handoff is not None
    assert handoff.handoff_state == HANDOFF_STATE_UNAVAILABLE
    assert handoff.converts_source_to_plain_text is False
    assert handoff.mutation_allowed is False
    assert handoff.overwrites_original is False
    assert handoff.provider_write_executed is False
    assert handoff.editable_document_payload is None
    assert handoff.source_asset_key == "asset_mail_hwpx_recognized"
    assert handoff.error_code == ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE
    assert handoff.next_action == NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT


def test_hangul_capability_without_edit_contract_still_refuses_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Hangul engine without an authorized editor contract cannot write."""

    monkeypatch.setattr(
        "services.inkspan_edit_handoff.registered_inkspan_editor_capability",
        lambda: SimpleNamespace(
            capability_name=EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE,
            accepted_source_families=("hwpx", "hwp"),
            mutation_contract_name=None,
        ),
    )

    handoff = build_inkspan_edit_handoff(_recognized_hwpx_preview())

    assert handoff is not None
    assert handoff.handoff_state == HANDOFF_STATE_UNAVAILABLE
    assert handoff.mutation_allowed is False
    assert handoff.overwrites_original is False
    assert handoff.provider_write_executed is False
    assert handoff.converts_source_to_plain_text is False
    assert handoff.editable_document_payload is None
    assert handoff.source_asset_key == "asset_mail_hwpx_recognized"
    assert handoff.error_code == ERROR_INKSPAN_EDIT_CONTRACT_UNAVAILABLE
    assert handoff.next_action == NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT


def test_pending_and_non_hwpx_previews_do_not_offer_edit_handoff() -> None:
    """Edit in Inkspan is only defined for recognized HWPX attachments."""

    pending = build_attachment_preview(
        "asset_mail_hwpx_pending",
        SimpleNamespace(
            filename="pending.hwpx",
            content="UEsDBAoAAAAAAretained-hwpx-bytes",
            content_type="application/hwp+zip",
            parse_content_type="application/hwp+zip",
            parser_key="hwpx",
            parse_status="hwpx_xml_package_pending",
            parse_error_code=None,
            content_segments=[],
        ),
    )
    markdown = RepositoryAssetPreview(
        asset_key="doc_repository_ready",
        asset_type="workspace_document",
        preview_state="recognized",
        parser_family=None,
        paragraph_texts=("# Q2 roadmap",),
        preview_text="# Q2 roadmap",
        next_action=NEXT_ACTION_READ_RECOGNIZED_TEXT,
        error_code=None,
        provider_write_executed=False,
    )

    assert pending.preview_state == "pending"
    assert build_inkspan_edit_handoff(pending) is None
    assert build_inkspan_edit_handoff(markdown) is None


def test_attachment_preview_attaches_fail_closed_handoff_for_recognized_hwpx() -> None:
    """The existing preview contract carries the read-only Inkspan handoff."""

    preview = build_attachment_preview(
        "asset_mail_hwpx_recognized",
        _hwpx_attachment(
            parse_status="hwpx_xml_package_parsed",
            content="Quarterly decision record\n\nApprove the next action.",
        ),
    )

    assert preview.preview_state == "recognized"
    assert preview.next_action == NEXT_ACTION_READ_RECOGNIZED_TEXT
    assert preview.edit_handoff is not None
    assert preview.edit_handoff.source_asset_key == preview.asset_key
    assert preview.edit_handoff.handoff_state == HANDOFF_STATE_UNAVAILABLE
    assert preview.edit_handoff.mutation_allowed is False
    assert preview.edit_handoff.provider_write_executed is False
    assert preview.edit_handoff.editable_document_payload is None
    assert preview.provider_write_executed is False
