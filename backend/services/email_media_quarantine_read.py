"""Read already-persisted email inline-media quarantine rows for the buyer UI.

This module is the #1350 Slice 3 buyer-visible read boundary. It lists
``email_media_quarantine_records`` already written by
``services.email_media_quarantine`` and maps the closed admission
``error_code`` set to the next action. It does not classify media, fetch
remote ``http(s)`` URLs, return withheld image bytes, run OCR, a VLM,
NewsDOM, or a model, or copy the #1376 ``EmailMediaArtifact`` pixel
contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from services.email_media_admission import (
    TRACKING_PIXEL_CLASSIFICATION,
    UNRESOLVED_CID_ERROR_CODE,
    UNSUPPORTED_MEDIA_CLASSIFICATION,
)

TRACKING_PIXEL_ERROR_CODE = TRACKING_PIXEL_CLASSIFICATION
UNSUPPORTED_MEDIA_ERROR_CODE = UNSUPPORTED_MEDIA_CLASSIFICATION
CLOSED_QUARANTINE_ERROR_CODES = frozenset(
    {
        TRACKING_PIXEL_ERROR_CODE,
        UNSUPPORTED_MEDIA_ERROR_CODE,
        UNRESOLVED_CID_ERROR_CODE,
    }
)

TRACKING_PIXEL_NEXT_ACTION = (
    "This inline image was withheld as a tracking pixel. "
    "It was not sent to a model."
)
UNSUPPORTED_MEDIA_NEXT_ACTION = (
    "This inline part is unsupported and was withheld. "
    "It was not sent to a model."
)
UNRESOLVED_CID_NEXT_ACTION = (
    "This cid: image could not be resolved from the same message "
    "and was withheld. It was not sent to a model."
)

BUYER_VISIBLE_NEXT_ACTIONS = {
    TRACKING_PIXEL_ERROR_CODE: TRACKING_PIXEL_NEXT_ACTION,
    UNSUPPORTED_MEDIA_ERROR_CODE: UNSUPPORTED_MEDIA_NEXT_ACTION,
    UNRESOLVED_CID_ERROR_CODE: UNRESOLVED_CID_NEXT_ACTION,
}


class EmailMediaQuarantineReadError(Exception):
    """Fail-closed read error with a deterministic ``error_code``."""

    def __init__(self, error_code: str, message: str) -> None:
        """Store a stable ``error_code`` separate from the exception text."""
        self.error_code = error_code
        super().__init__(f"{error_code}: {message}")


@dataclass(frozen=True)
class EmailMediaQuarantineRead:
    """Purpose-bound buyer row for one already-persisted quarantine outcome."""

    admission_error_code: str
    customer_next_action: str
    content_id_value: str | None


def customer_next_action_for_admission_error_code(error_code: str) -> str:
    """Return the buyer-visible next action for one persisted admission code.

    Args:
        error_code: Closed persist set member already stored on the row.

    Returns:
        The withheld-from-model next action for that code.

    Raises:
        EmailMediaQuarantineReadError: If ``error_code`` is outside the
            closed persist set, including ``document_image``.
    """
    next_action = BUYER_VISIBLE_NEXT_ACTIONS.get(error_code)
    if next_action is None:
        raise EmailMediaQuarantineReadError(
            "closed_error_code",
            "quarantine error_code is outside the closed persist set",
        )
    return next_action


def list_email_media_quarantine_records(
    persisted_rows: Sequence[object] | None,
) -> tuple[EmailMediaQuarantineRead, ...]:
    """Map already-persisted rows to buyer-visible next-action records.

    Unknown codes, ``document_image``, and non-row payloads fail closed to
    an empty tuple. The mapping does not classify media and does not expose
    sequential ``quarantine_record_id`` values or withheld bytes.

    Args:
        persisted_rows: ORM or namespace rows already bound to one message.

    Returns:
        Buyer-visible rows for closed admission codes only.
    """
    if persisted_rows is None or isinstance(persisted_rows, (str, bytes)):
        return ()
    if not isinstance(persisted_rows, Sequence):
        return ()

    records: list[EmailMediaQuarantineRead] = []
    for persisted_row in persisted_rows:
        error_code = getattr(persisted_row, "admission_error_code", None)
        next_action = BUYER_VISIBLE_NEXT_ACTIONS.get(error_code)
        if next_action is None:
            continue
        content_id_value = getattr(persisted_row, "content_id_value", None)
        records.append(
            EmailMediaQuarantineRead(
                admission_error_code=error_code,
                customer_next_action=next_action,
                content_id_value=(
                    content_id_value if isinstance(content_id_value, str) else None
                ),
            )
        )
    return tuple(records)
