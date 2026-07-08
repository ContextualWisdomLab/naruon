"""Map a recognized NewsDOM PDF into naruon's content graph.

The NewsDOM sidecar returns a ``pages -> articles -> body_blocks`` tree (see the
``ParseResponse`` schema in newsdom-api). This module normalizes that tree into:

* ``parse_text`` — a flat text rendering used for attachment / document
  embeddings, and
* a :class:`~services.content_graph.ParseResult` — a document -> section ->
  paragraph :class:`ContentNode` / :class:`ContentSegment` tree.

Provider configuration (base URL + bearer token) is always resolved from the
database (:class:`db.models.NewsdomProvider`); this module never reads service
config or secrets from the environment.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NewsdomProvider
from services.content_graph import ParseResult, PdfDomSection, parse_pdf_dom
from services.newsdom_client import (
    NewsdomConfigurationError,
    request_pdf_dom,
)

PDF_DOM_RECOGNITION_PENDING_STATUS = "pdf_dom_recognition_pending"
PDF_DOM_RECOGNITION_PARSED_STATUS = "parsed"
PDF_PARSER_KEY = "pdf"
PDF_PARSE_CONTENT_TYPE = "text/plain"


@dataclass(frozen=True)
class NewsdomRuntimeConfig:
    base_url: str
    api_token: str | None
    request_language: str
    recognition_mode: str
    provider_name: str


@dataclass(frozen=True)
class PdfDomRecognitionRecords:
    parse_text: str
    source_content_hash: str
    parse_result: ParseResult


ParseRequestFn = Callable[..., Awaitable[dict]]


def resolve_newsdom_runtime_config(
    provider: NewsdomProvider | None,
) -> NewsdomRuntimeConfig | None:
    """Build a runtime config purely from a database row — never the env.

    Returns ``None`` when the provider is missing, inactive, or has no base URL,
    which is the signal that PDF DOM recognition should stay pending / degrade
    gracefully rather than raise.
    """
    if provider is None or not provider.is_active:
        return None
    base_url = (provider.base_url or "").strip()
    if not base_url:
        return None
    api_token = provider.api_token.strip() if provider.api_token else None
    return NewsdomRuntimeConfig(
        base_url=base_url,
        api_token=api_token or None,
        request_language=(provider.request_language or "auto").strip() or "auto",
        recognition_mode=(provider.recognition_mode or "auto").strip() or "auto",
        provider_name=provider.provider_name,
    )


async def get_active_newsdom_provider(
    session: AsyncSession,
    organization_id: str | None,
) -> NewsdomProvider | None:
    if not organization_id:
        return None
    result = await session.execute(
        select(NewsdomProvider)
        .where(
            NewsdomProvider.organization_id == organization_id,
            NewsdomProvider.is_active.is_(True),
        )
        .order_by(desc(NewsdomProvider.updated_at), desc(NewsdomProvider.id))
        .limit(1)
    )
    return result.scalars().first()


async def resolve_newsdom_config_from_db(
    session: AsyncSession,
    organization_id: str | None,
) -> NewsdomRuntimeConfig | None:
    provider = await get_active_newsdom_provider(session, organization_id)
    return resolve_newsdom_runtime_config(provider)


def normalize_parse_response(payload: dict) -> list[PdfDomSection]:
    """Flatten a NewsDOM ``ParseResponse`` dict into ordered sections.

    Each article (across every page, in page then article order) becomes one
    section. Robust to missing / malformed keys so a partial sidecar response
    never crashes the importer.
    """
    sections: list[PdfDomSection] = []
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list):
        return sections

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_number = page.get("page_number")
        page_number = page_number if isinstance(page_number, int) else None
        articles = page.get("articles")
        if not isinstance(articles, list):
            continue
        for article in articles:
            if not isinstance(article, dict):
                continue
            headline = article.get("headline")
            headline = headline if isinstance(headline, str) else ""
            body_blocks = article.get("body_blocks")
            paragraphs = tuple(
                block
                for block in (body_blocks if isinstance(body_blocks, list) else [])
                if isinstance(block, str) and block.strip()
            )
            if not headline.strip() and not paragraphs:
                continue
            sections.append(
                PdfDomSection(
                    heading=headline,
                    paragraphs=paragraphs,
                    page_number=page_number,
                )
            )
    return sections


def _render_parse_text(sections: list[PdfDomSection]) -> str:
    blocks: list[str] = []
    for section in sections:
        if section.heading.strip():
            blocks.append(section.heading.strip())
        blocks.extend(
            paragraph.strip() for paragraph in section.paragraphs if paragraph.strip()
        )
    return "\n\n".join(blocks)


def build_recognition_records(
    payload: dict,
    *,
    source_kind: str,
    source_record_uid: str,
    display_name: str = "",
) -> PdfDomRecognitionRecords:
    sections = normalize_parse_response(payload)
    parse_text = _render_parse_text(sections)
    source_content_hash = hashlib.sha256(
        parse_text.encode("utf-8", errors="surrogatepass")
    ).hexdigest()
    parse_result = parse_pdf_dom(
        source_kind=source_kind,
        source_record_uid=source_record_uid,
        sections=sections,
        source_content_hash=source_content_hash,
        display_name=display_name,
    )
    return PdfDomRecognitionRecords(
        parse_text=parse_text,
        source_content_hash=source_content_hash,
        parse_result=parse_result,
    )


async def recognize_pdf_dom(
    *,
    config: NewsdomRuntimeConfig | None,
    pdf_bytes: bytes,
    filename: str,
    source_kind: str,
    source_record_uid: str,
    display_name: str = "",
    request_fn: ParseRequestFn = request_pdf_dom,
) -> PdfDomRecognitionRecords:
    """Call the sidecar and map the response into content graph records.

    ``request_fn`` is injectable so callers (and tests) can supply a mocked
    NewsDOM client. Raises :class:`NewsdomConfigurationError` when the sidecar is
    not configured, so the caller can keep the source pending instead of failing
    the whole import.
    """
    if config is None:
        raise NewsdomConfigurationError(
            "NewsDOM PDF DOM recognition is not configured for this workspace"
        )
    payload = await request_fn(
        base_url=config.base_url,
        api_token=config.api_token,
        pdf_bytes=pdf_bytes,
        filename=filename,
        language=config.request_language,
        mode=config.recognition_mode,
    )
    return build_recognition_records(
        payload,
        source_kind=source_kind,
        source_record_uid=source_record_uid,
        display_name=display_name,
    )
