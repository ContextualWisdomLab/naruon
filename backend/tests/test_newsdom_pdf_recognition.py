"""Fast, fully-mocked unit tests for NewsDOM PDF DOM recognition.

No database and no network: the NewsDOM client is replaced with a canned
``ParseResponse`` and the content-graph mapping / config resolution are
exercised against in-memory model instances.
"""

import os

import pytest

from db.models import Attachment, Email, NewsdomProvider
from services.newsdom_pdf_recognition import (
    NewsdomRuntimeConfig,
    build_recognition_records,
    normalize_parse_response,
    recognize_pdf_dom,
    resolve_newsdom_runtime_config,
)
from services.newsdom_worker import (
    apply_recognition_to_attachment,
    recognize_attachment_pdf,
)


def _canned_parse_response() -> dict:
    return {
        "document_id": "doc-123",
        "pages": [
            {
                "page_number": 1,
                "articles": [
                    {
                        "article_id": "a1",
                        "headline": "First Headline",
                        "body_blocks": ["Body one.", "Body two."],
                    },
                    {
                        "article_id": "a2",
                        "headline": "Second Headline",
                        "body_blocks": ["Only body."],
                    },
                ],
            },
            {
                "page_number": 2,
                "articles": [
                    {
                        "article_id": "a3",
                        "headline": "",
                        "body_blocks": ["   ", "Third page body."],
                    }
                ],
            },
        ],
        "quality": {"status": "success", "parser": "mineru", "warnings": []},
    }


def test_normalize_parse_response_flattens_articles_in_order():
    sections = normalize_parse_response(_canned_parse_response())

    assert [section.heading for section in sections] == [
        "First Headline",
        "Second Headline",
        "",
    ]
    assert sections[0].paragraphs == ("Body one.", "Body two.")
    # Blank body blocks are dropped.
    assert sections[2].paragraphs == ("Third page body.",)
    assert sections[0].page_number == 1
    assert sections[2].page_number == 2


def test_normalize_parse_response_tolerates_garbage():
    assert normalize_parse_response({}) == []
    assert normalize_parse_response({"pages": "nope"}) == []
    assert normalize_parse_response({"pages": [{"articles": [42, {"headline": 3}]}]}) == []


def test_build_recognition_records_builds_document_section_paragraph_tree():
    records = build_recognition_records(
        _canned_parse_response(),
        source_kind="attachment",
        source_record_uid="att-1",
        display_name="news.pdf",
    )

    parse_result = records.parse_result
    node_kinds = [node.node_kind for node in parse_result.nodes]
    assert node_kinds.count("document") == 1
    assert node_kinds.count("section") == 3
    # 2 + 1 + 1 body paragraphs across the three sections.
    assert node_kinds.count("paragraph") == 4

    document_nodes = [n for n in parse_result.nodes if n.node_kind == "document"]
    (document_node,) = document_nodes
    assert document_node.parent_node_uid is None
    assert document_node.display_label == "news.pdf"

    section_nodes = [n for n in parse_result.nodes if n.node_kind == "section"]
    assert all(
        n.parent_node_uid == document_node.content_node_uid for n in section_nodes
    )
    section_uids = {n.content_node_uid for n in section_nodes}
    paragraph_nodes = [n for n in parse_result.nodes if n.node_kind == "paragraph"]
    assert all(n.parent_node_uid in section_uids for n in paragraph_nodes)

    segment_kinds = [seg.segment_kind for seg in parse_result.segments]
    # Two headlines are non-empty -> two heading segments; the empty headline
    # produces no heading segment.
    assert segment_kinds.count("heading") == 2
    assert segment_kinds.count("paragraph") == 4

    # parse_content text (for embeddings) carries every headline + body block.
    assert "First Headline" in records.parse_text
    assert "Third page body." in records.parse_text
    assert records.source_content_hash


def test_recognition_uid_is_stable_for_identical_payload():
    payload = _canned_parse_response()
    first = build_recognition_records(
        payload, source_kind="attachment", source_record_uid="att-1"
    )
    second = build_recognition_records(
        payload, source_kind="attachment", source_record_uid="att-1"
    )
    assert [n.content_node_uid for n in first.parse_result.nodes] == [
        n.content_node_uid for n in second.parse_result.nodes
    ]


def test_resolve_runtime_config_reads_from_db_row_not_env(monkeypatch):
    # Prove the resolver never consults the process environment for config.
    def _boom(*_args, **_kwargs):  # pragma: no cover - only fails if called
        raise AssertionError("config must come from the DB, not os.getenv")

    monkeypatch.setattr(os, "getenv", _boom)
    monkeypatch.setattr(os, "environ", {})

    provider = NewsdomProvider(
        user_id="u1",
        organization_id="org-1",
        provider_name="primary",
        base_url="https://newsdom.example.com",
        api_token="secret-token",
        request_language="ja",
        recognition_mode="newspaper",
        is_active=True,
    )
    config = resolve_newsdom_runtime_config(provider)
    assert config == NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token="secret-token",
        request_language="ja",
        recognition_mode="newspaper",
        provider_name="primary",
    )


def test_resolve_runtime_config_degrades_when_unconfigured():
    assert resolve_newsdom_runtime_config(None) is None
    inactive = NewsdomProvider(
        user_id="u",
        organization_id="o",
        provider_name="p",
        base_url="https://newsdom.example.com",
        is_active=False,
    )
    assert resolve_newsdom_runtime_config(inactive) is None
    no_url = NewsdomProvider(
        user_id="u",
        organization_id="o",
        provider_name="p",
        base_url="",
        is_active=True,
    )
    assert resolve_newsdom_runtime_config(no_url) is None


@pytest.mark.asyncio
async def test_recognize_pdf_dom_uses_mocked_client_with_config_values():
    captured = {}

    async def fake_request(**kwargs):
        captured.update(kwargs)
        return _canned_parse_response()

    config = NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token="tok",
        request_language="ja",
        recognition_mode="newspaper",
        provider_name="primary",
    )
    records = await recognize_pdf_dom(
        config=config,
        pdf_bytes=b"%PDF-1.7 fake",
        filename="news.pdf",
        source_kind="attachment",
        source_record_uid="att-1",
        display_name="news.pdf",
        request_fn=fake_request,
    )

    assert captured["base_url"] == "https://newsdom.example.com"
    assert captured["api_token"] == "tok"
    assert captured["language"] == "ja"
    assert captured["mode"] == "newspaper"
    assert captured["pdf_bytes"] == b"%PDF-1.7 fake"
    assert records.parse_text
    assert any(n.node_kind == "section" for n in records.parse_result.nodes)


@pytest.mark.asyncio
async def test_recognize_attachment_pdf_lands_text_and_content_graph():
    email = Email()
    attachment = Attachment(filename="news.pdf")
    email.attachments.append(attachment)

    async def fake_request(**_kwargs):
        return _canned_parse_response()

    config = NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token=None,
        request_language="auto",
        recognition_mode="auto",
        provider_name="primary",
    )
    await recognize_attachment_pdf(
        email=email,
        attachment=attachment,
        pdf_bytes=b"%PDF-1.7 fake",
        config=config,
        source_record_uid="att-1",
        request_fn=fake_request,
    )

    assert attachment.parse_status == "parsed"
    assert attachment.parser_key == "pdf"
    assert "First Headline" in attachment.parse_content
    # Content graph landed on both the email and the attachment.
    assert any(n.node_kind == "section" for n in attachment.content_nodes)
    assert any(n.node_kind == "document" for n in email.content_nodes)
    assert attachment.content_segments
    assert email.content_segments


@pytest.mark.asyncio
async def test_recognize_pdf_dom_rejects_empty_sidecar_response():
    from services.newsdom_client import NewsdomEmptyRecognitionError

    async def empty_request(**_kwargs):
        return {"pages": []}

    with pytest.raises(NewsdomEmptyRecognitionError):
        await recognize_pdf_dom(
            config=NewsdomRuntimeConfig(
                base_url="https://newsdom.example.com",
                api_token=None,
                request_language="auto",
                recognition_mode="auto",
                provider_name="primary",
            ),
            pdf_bytes=b"%PDF-1.7 fake",
            filename="news.pdf",
            source_kind="attachment",
            source_record_uid="att-1",
            request_fn=empty_request,
        )


def test_apply_recognition_to_attachment_is_pure_mapping():
    email = Email()
    attachment = Attachment(filename="news.pdf")
    email.attachments.append(attachment)
    records = build_recognition_records(
        _canned_parse_response(),
        source_kind="attachment",
        source_record_uid="att-1",
        display_name="news.pdf",
    )
    apply_recognition_to_attachment(email=email, attachment=attachment, records=records)
    assert len(attachment.content_nodes) == len(records.parse_result.nodes)
    assert len(attachment.content_segments) == len(records.parse_result.segments)
