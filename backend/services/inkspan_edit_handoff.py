"""Probe a read-only Inkspan edit handoff for recognized HWPX attachments.

Naruon already exposes ordered HWPX paragraphs through the repository-asset
preview. This module does not convert those paragraphs into an editable
document, does not overwrite the original attachment, and does not invent a
write API. It only records whether a released, installed Inkspan Hangul
document engine is present and whether an authorized editor contract exists.

Released Inkspan remains a Markdown/HTML editor. Hangul import/edit/export is
owned by unreleased inkspan Draft #320 and is not installed here, so the host
adapter hook stays empty and the buyer-visible handoff fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HANDOFF_STATE_UNAVAILABLE = "unavailable"
EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE = "inkspan_hangul_document_engine"
ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE = "inkspan_hangul_capability_unavailable"
ERROR_INKSPAN_EDIT_CONTRACT_UNAVAILABLE = "inkspan_edit_contract_unavailable"
NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT = "keep_reading_recognized_text"
HWPX_PARSER_FAMILY = "hwpx"
AUTHORIZED_EDIT_CONTRACTS: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class InkspanEditHandoff:
    """Carry one scoped, non-mutating Inkspan handoff for a recognized HWPX file."""

    source_asset_key: str
    source_asset_type: str
    parser_family: str | None
    handoff_state: Literal["unavailable"]
    editor_capability_name: str
    mutation_allowed: bool
    converts_source_to_plain_text: bool
    overwrites_original: bool
    provider_write_executed: bool
    next_action: str
    error_code: str
    editable_document_payload: None = None


def registered_inkspan_editor_capability() -> object | None:
    """Return the host-owned Inkspan editor adapter when one is installed.

    Naruon does not vendor Inkspan. A future host adapter may register here
    after a released Hangul document engine exists. The default workspace has
    no such adapter.
    """

    return None


def installed_inkspan_editor_capability() -> object | None:
    """Return a Hangul engine adapter only when it accepts HWPX without conversion."""

    adapter = registered_inkspan_editor_capability()
    if _is_hangul_hwpx_capability(adapter):
        return adapter
    return None


def _adapter_field(adapter: object | None, field_name: str) -> object | None:
    """Read one adapter attribute without treating missing hosts as installed."""

    if adapter is None:
        return None
    return getattr(adapter, field_name, None)


def _accepted_source_families(adapter: object | None) -> tuple[str, ...]:
    """Return the source families an adapter can open without conversion."""

    families = _adapter_field(adapter, "accepted_source_families")
    if not families:
        return ()
    return tuple(str(family) for family in families)


def _is_hangul_hwpx_capability(adapter: object | None) -> bool:
    """True only for a Hangul engine that accepts HWPX as HWPX."""

    capability_name = _adapter_field(adapter, "capability_name")
    return (
        capability_name == EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE
        and HWPX_PARSER_FAMILY in _accepted_source_families(adapter)
    )


def _unavailable_handoff(
    preview: object,
    error_code: str,
) -> InkspanEditHandoff:
    """Build a fail-closed handoff that keeps the exact source identity."""

    return InkspanEditHandoff(
        source_asset_key=str(getattr(preview, "asset_key")),
        source_asset_type=str(getattr(preview, "asset_type")),
        parser_family=str(getattr(preview, "parser_family") or "") or None,
        handoff_state=HANDOFF_STATE_UNAVAILABLE,
        editor_capability_name=EDITOR_CAPABILITY_HANGUL_DOCUMENT_ENGINE,
        mutation_allowed=False,
        converts_source_to_plain_text=False,
        overwrites_original=False,
        provider_write_executed=False,
        next_action=NEXT_ACTION_KEEP_READING_RECOGNIZED_TEXT,
        error_code=error_code,
        editable_document_payload=None,
    )


def build_inkspan_edit_handoff(preview: object) -> InkspanEditHandoff | None:
    """Return a read-only Inkspan handoff for recognized HWPX, or None.

    Pending, failed, unavailable, and non-HWPX previews do not offer an edit
    control. Recognized HWPX always preserves the preview asset key and fails
    closed unless a released Hangul capability and an authorized editor
    contract are both present. No authorized contract exists in this slice.
    """

    preview_state = str(getattr(preview, "preview_state", "") or "")
    parser_family = str(getattr(preview, "parser_family", "") or "")
    if preview_state != "recognized" or parser_family != HWPX_PARSER_FAMILY:
        return None

    adapter = registered_inkspan_editor_capability()
    if not _is_hangul_hwpx_capability(adapter):
        return _unavailable_handoff(
            preview,
            ERROR_INKSPAN_HANGUL_CAPABILITY_UNAVAILABLE,
        )

    contract_name = _adapter_field(adapter, "mutation_contract_name")
    if (
        not isinstance(contract_name, str)
        or contract_name not in AUTHORIZED_EDIT_CONTRACTS
    ):
        return _unavailable_handoff(
            preview,
            ERROR_INKSPAN_EDIT_CONTRACT_UNAVAILABLE,
        )

    return _unavailable_handoff(
        preview,
        ERROR_INKSPAN_EDIT_CONTRACT_UNAVAILABLE,
    )
