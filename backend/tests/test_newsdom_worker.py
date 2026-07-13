"""Unit tests for the NewsDOM recognition worker's per-item processing.

Fully mocked: in-memory models, an injected async config resolver, and a canned
sidecar ``request_fn`` — no database, no network. Covers the fail-closed
outcomes (unconfigured -> pending, bad payload -> failed, empty response ->
failed) that keep a pending PDF from ever masquerading as parsed.
"""

import base64

import pytest

from db.models import Attachment, Document, Email
from services.newsdom_pdf_recognition import (
    PDF_DOM_RECOGNITION_FAILED_STATUS,
    PDF_DOM_RECOGNITION_PENDING_STATUS,
    NewsdomRuntimeConfig,
)
from services.newsdom_worker import (
    RESULT_FAILED,
    RESULT_PENDING,
    RESULT_RECOGNIZED,
    process_pending_attachment,
    process_pending_document,
)


def _config() -> NewsdomRuntimeConfig:
    return NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token=None,
        request_language="auto",
        recognition_mode="auto",
        provider_name="primary",
    )


def _canned_response() -> dict:
    return {
        "pages": [
            {
                "page_number": 1,
                "articles": [
                    {"headline": "Headline", "body_blocks": ["Body one."]}
                ],
            }
        ]
    }


async def _resolver_with(config):
    async def resolve(_session, _org):
        return config

    return resolve


def _pending_attachment(payload: bytes = b"%PDF-1.7 fake") -> Attachment:
    email = Email()
    email.organization_id = "org-1"
    attachment = Attachment(
        filename="news.pdf",
        content=base64.b64encode(payload).decode("ascii"),
        parse_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )
    email.attachments.append(attachment)
    return attachment


@pytest.mark.asyncio
async def test_attachment_recognized_when_configured():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):
        return _canned_response()

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_RECOGNIZED
    assert attachment.parse_status == "parsed"
    assert "Headline" in attachment.content
    assert attachment.content_segments


@pytest.mark.asyncio
async def test_attachment_left_pending_when_no_provider():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):  # pragma: no cover - must not be called
        raise AssertionError("sidecar must not be called when unconfigured")

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(None),
        request_fn=request_fn,
    )
    assert result == RESULT_PENDING
    assert attachment.parse_status == PDF_DOM_RECOGNITION_PENDING_STATUS


@pytest.mark.asyncio
async def test_attachment_failed_on_invalid_payload():
    attachment = _pending_attachment()
    attachment.content = "not@@base64!!"

    async def request_fn(**_kwargs):  # pragma: no cover
        raise AssertionError("must not reach sidecar with a bad payload")

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert attachment.parse_status == PDF_DOM_RECOGNITION_FAILED_STATUS
    assert attachment.parse_error_code == "invalid_pending_payload"


@pytest.mark.asyncio
async def test_attachment_failed_on_empty_sidecar_response():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):
        return {"pages": []}

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert attachment.parse_status == PDF_DOM_RECOGNITION_FAILED_STATUS
    assert attachment.parse_error_code == "recognition_failed"
    # Never landed as parsed with empty content.
    assert attachment.parse_status != "parsed"


@pytest.mark.asyncio
async def test_document_recognized_when_configured():
    document = Document(
        document_id="doc-1",
        workspace_id="ws-1",
        organization_id="org-1",
        document_name="news.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )

    async def request_fn(**_kwargs):
        return _canned_response()

    result = await process_pending_document(
        session=object(),
        document=document,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_RECOGNIZED
    assert document.document_status == "parsed"
    assert "Headline" in document.document_content


@pytest.mark.asyncio
async def test_document_failed_on_empty_response():
    document = Document(
        document_id="doc-2",
        workspace_id="ws-1",
        organization_id="org-1",
        document_name="news.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )

    async def request_fn(**_kwargs):
        return {"pages": []}

    result = await process_pending_document(
        session=object(),
        document=document,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert document.document_status == PDF_DOM_RECOGNITION_FAILED_STATUS
