"""Contract tests for deferred HWPX background recognition.

The attachment importer deliberately stores validated HWPX bytes as a pending
base64 payload. These tests require the existing recognition worker to consume
that pending state locally, without requiring a NewsDOM provider, while keeping
failure states explicit and bounded.
"""

from __future__ import annotations

import base64
import io
import zipfile

import pytest
from sqlalchemy.dialects import postgresql

from db.models import Attachment, Email
from services.newsdom_worker import (
    RESULT_FAILED,
    RESULT_RECOGNIZED,
    NewsdomRecognitionWorker,
    process_pending_attachment,
)

HWPX_PENDING_STATUS = "hwpx_xml_package_pending"
HWPX_PARSED_STATUS = "hwpx_xml_package_parsed"
HWPX_FAILED_STATUS = "hwpx_xml_package_failed"


def _hwpx_payload(*, include_section: bool = True) -> bytes:
    """Build one minimal standards-shaped HWPX package for worker tests."""

    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("mimetype", b"application/hwp+zip")
        archive.writestr(
            "Contents/content.hpf",
            b"""<?xml version='1.0' encoding='UTF-8'?>
<opf:package xmlns:opf='urn:oasis:names:tc:opendocument:xmlns:container'>
  <opf:manifest>
    <opf:item id='section0' href='section0.xml'/>
  </opf:manifest>
  <opf:spine>
    <opf:itemref idref='section0'/>
  </opf:spine>
</opf:package>
""",
        )
        if include_section:
            archive.writestr(
                "Contents/section0.xml",
                b"""<?xml version='1.0' encoding='UTF-8'?>
<hp:sec xmlns:hp='http://www.hancom.co.kr/hwpml/2011/paragraph'>
  <hp:p><hp:run><hp:t>Quarterly decision record</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>Approve the next action.</hp:t></hp:run></hp:p>
</hp:sec>
""",
            )
    return package.getvalue()


def _pending_hwpx_attachment(payload: bytes) -> Attachment:
    """Create an in-memory HWPX attachment with its owning email relationship."""

    email = Email()
    email.organization_id = "org-hwpx"
    attachment = Attachment(
        id=73,
        filename="decision.hwpx",
        content=base64.b64encode(payload).decode("ascii"),
        content_type="application/hwp+zip",
        parse_content_type="application/hwp+zip",
        parser_key="hwpx",
        parse_status=HWPX_PENDING_STATUS,
    )
    email.attachments.append(attachment)
    return attachment


async def _must_not_resolve_provider(*_args, **_kwargs):
    """Fail when deterministic HWPX recognition tries to resolve NewsDOM."""

    raise AssertionError("HWPX recognition must not require a NewsDOM provider")


async def _must_not_call_newsdom(**_kwargs):
    """Fail when deterministic HWPX recognition reaches the NewsDOM sidecar."""

    raise AssertionError("HWPX recognition must not call the NewsDOM sidecar")


@pytest.mark.asyncio
async def test_pending_hwpx_attachment_is_recognized_without_provider() -> None:
    """A pending HWPX package becomes searchable text plus graph provenance."""

    attachment = _pending_hwpx_attachment(_hwpx_payload())

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=_must_not_resolve_provider,
        request_fn=_must_not_call_newsdom,
    )

    assert result == RESULT_RECOGNIZED
    assert attachment.parse_status == HWPX_PARSED_STATUS
    assert attachment.parse_error_code is None
    assert attachment.parse_content_type == "application/hwp+zip"
    assert attachment.parser_key == "hwpx"
    assert attachment.content == (
        "Quarterly decision record\n\nApprove the next action."
    )
    assert [segment.safe_text_content for segment in attachment.content_segments] == [
        "Quarterly decision record",
        "Approve the next action.",
    ]
    assert attachment.content_nodes


@pytest.mark.asyncio
async def test_pending_hwpx_attachment_revalidates_retained_bytes() -> None:
    """Tampered retained bytes fail closed before any provider or XML work."""

    attachment = _pending_hwpx_attachment(b"not-a-zip")

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=_must_not_resolve_provider,
        request_fn=_must_not_call_newsdom,
    )

    assert result == RESULT_FAILED
    assert attachment.parse_status == HWPX_FAILED_STATUS
    assert attachment.parse_error_code == "invalid_pending_payload"
    assert attachment.content_nodes == []
    assert attachment.content_segments == []


@pytest.mark.asyncio
async def test_pending_hwpx_attachment_records_recognizer_failure() -> None:
    """A valid HWPX identity with a broken spine never masquerades as parsed."""

    attachment = _pending_hwpx_attachment(_hwpx_payload(include_section=False))

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=_must_not_resolve_provider,
        request_fn=_must_not_call_newsdom,
    )

    assert result == RESULT_FAILED
    assert attachment.parse_status == HWPX_FAILED_STATUS
    assert attachment.parse_error_code == "recognition_failed"
    assert attachment.content_nodes == []
    assert attachment.content_segments == []


@pytest.mark.asyncio
async def test_orphan_pending_hwpx_attachment_uses_hwpx_failure_status() -> None:
    """An orphan HWPX row fails visibly without being mislabeled as PDF."""

    attachment = Attachment(
        id=74,
        filename="orphan.hwpx",
        content=base64.b64encode(_hwpx_payload()).decode("ascii"),
        content_type="application/hwp+zip",
        parse_content_type="application/hwp+zip",
        parser_key="hwpx",
        parse_status=HWPX_PENDING_STATUS,
    )

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=_must_not_resolve_provider,
        request_fn=_must_not_call_newsdom,
    )

    assert result == RESULT_FAILED
    assert attachment.parse_status == HWPX_FAILED_STATUS
    assert attachment.parse_error_code == "orphan_attachment"


def test_worker_selects_pdf_and_hwpx_pending_attachments() -> None:
    """The bounded sweep must include both deferred attachment families."""

    worker = NewsdomRecognitionWorker(batch_limit=7)
    statement = worker._pending_attachment_statement(None)
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "pdf_dom_recognition_pending" in sql
    assert HWPX_PENDING_STATUS in sql
    assert "LIMIT 7" in sql
