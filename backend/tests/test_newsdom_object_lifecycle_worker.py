"""Regression tests for NewsDOM document-object lifecycle transitions.

These tests keep the worker's parsed-document state and object-storage state in
one transaction boundary. A source object must become ``consumed`` only after
successful recognition; retryable pending work must retain its active payload.
"""

import base64

import pytest

from db.models import Document
from services.newsdom_pdf_recognition import (
    PDF_DOM_RECOGNITION_PENDING_STATUS,
    NewsdomRuntimeConfig,
)
import services.newsdom_worker as newsdom_worker_module


def _pending_document(document_id: str) -> Document:
    """Build a pending legacy-backed PDF that exercises the worker entrypoint."""
    return Document(
        document_id=document_id,
        workspace_id="workspace-1",
        organization_id="organization-1",
        document_name="evidence.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 realistic-payload").decode(
            "ascii"
        ),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )


def _runtime_config() -> NewsdomRuntimeConfig:
    """Return a valid deterministic provider configuration for recognition."""
    return NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token=None,
        request_language="auto",
        recognition_mode="auto",
        provider_name="primary",
    )


async def _configured_resolver(_session, _organization_id):
    """Resolve the deterministic provider used by the successful-path test."""
    return _runtime_config()


async def _unconfigured_resolver(_session, _organization_id):
    """Represent a tenant that intentionally has no active recognition provider."""
    return None


async def _recognized_response(**_kwargs):
    """Return the smallest non-empty NewsDOM response accepted by recognition."""
    return {
        "pages": [
            {
                "page_number": 1,
                "articles": [
                    {
                        "headline": "Acquisition evidence",
                        "body_blocks": ["Retain the source object lifecycle."],
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_successful_document_recognition_consumes_source_object(monkeypatch):
    """Mark the source object consumed in the same unit of work as parsing."""
    session = object()
    document = _pending_document("document-success")
    transitions = []

    async def mark_consumed(actual_session, document_id):
        transitions.append((actual_session, document_id))

    monkeypatch.setattr(
        newsdom_worker_module,
        "mark_document_payload_consumed",
        mark_consumed,
        raising=False,
    )

    result = await newsdom_worker_module.process_pending_document(
        session=session,
        document=document,
        config_resolver=_configured_resolver,
        request_fn=_recognized_response,
    )

    assert result == newsdom_worker_module.RESULT_RECOGNIZED
    assert document.document_status == "parsed"
    assert transitions == [(session, "document-success")]


@pytest.mark.asyncio
async def test_pending_document_does_not_consume_retryable_source_object(monkeypatch):
    """Keep source bytes active while recognition is waiting for configuration."""
    session = object()
    document = _pending_document("document-pending")
    transitions = []

    async def mark_consumed(actual_session, document_id):
        transitions.append((actual_session, document_id))

    monkeypatch.setattr(
        newsdom_worker_module,
        "mark_document_payload_consumed",
        mark_consumed,
        raising=False,
    )

    result = await newsdom_worker_module.process_pending_document(
        session=session,
        document=document,
        config_resolver=_unconfigured_resolver,
        request_fn=_recognized_response,
    )

    assert result == newsdom_worker_module.RESULT_PENDING
    assert document.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS
    assert transitions == []
