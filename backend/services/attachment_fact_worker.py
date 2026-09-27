"""Infer attachment candidates outside recognition transactions and sweep leases."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.config import settings
from db.models import Attachment, ProjectGraphObjectRecord
from db.session import AsyncSessionLocal
from services.llm_provider_selection import resolve_runtime_llm_provider
from services.project_graph import (
    ProjectObjectType,
    ProjectSemanticExtractionResult,
    ProjectSourceSegment,
    persist_project_graph_projection,
)
from services.project_graph.extractor_registry import KgExtractorContext, run_extraction
from services.project_graph.llm_extractor import (
    LLM_EXTRACTOR_NAME,
    LLM_EXTRACTOR_VERSION,
)


async def infer_attachment_facts(attachment_id: int) -> bool:
    """Commit candidates only if the committed source and ownership still match."""
    async with AsyncSessionLocal() as session:
        attachment = await session.scalar(
            select(Attachment)
            .where(
                Attachment.id == attachment_id,
                Attachment.parse_status == "parsed",
            )
            .options(
                selectinload(Attachment.email),
                selectinload(Attachment.content_segments),
            )
        )
        if (
            attachment is None
            or attachment.fact_extractor_version == LLM_EXTRACTOR_VERSION
        ):
            return False
        email = attachment.email
        if email is None:
            return False
        owner = (email.user_id, email.organization_id, email.id)
        segments = tuple(
            ProjectSourceSegment(
                content_segment_uid=s.content_segment_uid,
                source_kind=s.source_kind,
                source_record_uid=s.source_record_uid,
                safe_text_content=s.safe_text_content,
                heading_path=s.heading_path,
                segment_path=s.segment_path,
                ordinal_index=s.ordinal_index,
            )
            for s in attachment.content_segments
            if s.source_kind == "attachment"
        )
        if not segments:
            return False
        provider = await resolve_runtime_llm_provider(
            session,
            user_id=owner[0],
            organization_id=owner[1],
        )
        if provider is None:
            return False
    # No DB session or recognition lease is held while the provider runs.
    result = await run_extraction(
        list(segments),
        selector=settings.PROJECT_GRAPH_EXTRACTOR,
        context=KgExtractorContext(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.chat_model,
            orchestrator_base_url=settings.PROJECT_GRAPH_ORCHESTRATOR_BASE_URL,
        ),
    )
    if result.extractor_name != LLM_EXTRACTOR_NAME:
        return False
    facts = tuple(
        o for o in result.objects if o.object_type is ProjectObjectType.ATTACHMENT_FACT
    )
    async with AsyncSessionLocal() as session:
        attachment = await session.scalar(
            select(Attachment)
            .where(Attachment.id == attachment_id)
            .with_for_update()
            .options(
                selectinload(Attachment.email),
                selectinload(Attachment.content_segments),
            )
        )
        if (
            attachment is None
            or attachment.parse_status != "parsed"
            or attachment.fact_extractor_version == LLM_EXTRACTOR_VERSION
        ):
            return False
        if (
            attachment.email is None
            or (
                attachment.email.user_id,
                attachment.email.organization_id,
                attachment.email.id,
            )
            != owner
        ):
            return False
        current = {
            s.content_segment_uid: s.safe_text_content
            for s in attachment.content_segments
            if s.source_kind == "attachment"
        }
        if current != {s.content_segment_uid: s.safe_text_content for s in segments}:
            return False
        if facts:
            existing = set(
                (
                    await session.scalars(
                        select(ProjectGraphObjectRecord.object_uid).where(
                            ProjectGraphObjectRecord.object_uid.in_(
                                [fact.uid for fact in facts]
                            ),
                            ProjectGraphObjectRecord.user_id == owner[0],
                            ProjectGraphObjectRecord.organization_id == owner[1],
                        )
                    )
                ).all()
            )
            # Existing facts may carry user corrections; inference never replaces them.
            new_facts = tuple(fact for fact in facts if fact.uid not in existing)
            new_endpoints = {fact.uid for fact in new_facts} | {
                f"segment:{segment.content_segment_uid}" for segment in segments
            }
            extraction = ProjectSemanticExtractionResult(
                objects=new_facts,
                edges=tuple(
                    edge
                    for edge in result.edges
                    if edge.source_uid in new_endpoints
                    and edge.target_uid in new_endpoints
                ),
                extractor_name=result.extractor_name,
                extractor_version=result.extractor_version,
            )
            if new_facts:
                await persist_project_graph_projection(
                    session,
                    extraction=extraction,
                    user_id=owner[0],
                    organization_id=owner[1],
                    workspace_id=f"workspace-{owner[1] or owner[0]}",
                )
        attachment.fact_extractor_version = LLM_EXTRACTOR_VERSION
        await session.commit()
    return True
