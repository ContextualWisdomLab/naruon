from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from .models import ProjectSemanticExtractionResult
from .repository import ProjectGraphPersistResult, ProjectGraphRepository


async def persist_project_graph_projection(
    session: AsyncSession,
    *,
    extraction: ProjectSemanticExtractionResult,
    user_id: str,
    organization_id: str | None,
    workspace_id: str,
    status_code: str = "candidate",
) -> ProjectGraphPersistResult:
    repository = ProjectGraphRepository(session)
    return await repository.persist_extraction(
        extraction=extraction,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        status_code=status_code,
    )


async def apply_project_graph_correction(
    session: AsyncSession,
    *,
    object_uid: str,
    user_id: str,
    organization_id: str | None,
    workspace_id: str,
    actor_user_id: str,
    correction_action: str,
    after_json: Mapping[str, Any],
    rationale: str | None = None,
    source_segment_uids: tuple[str, ...] | None = None,
):
    repository = ProjectGraphRepository(session)
    return await repository.apply_correction(
        object_uid=object_uid,
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        correction_action=correction_action,
        after_json=after_json,
        rationale=rationale,
        source_segment_uids=source_segment_uids,
    )
