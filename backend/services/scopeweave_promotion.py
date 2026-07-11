"""Promote evidence-grounded project-graph objects into scopeweave.

Flow: resolve the workspace's encrypted scopeweave target from the database,
load the citation-backed evidence for the requested object, push it to the
scopeweave import endpoint, and persist the naruon ``object_uid`` <->
scopeweave work-item mapping. When no target is configured the caller receives
``ScopeweaveNotConfiguredError`` so the API can degrade gracefully instead of
failing hard.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ScopeweavePromotionLink, ScopeweavePromotionTarget
from services.project_graph.project_registration import (
    ProjectEvidence,
    ProjectGraphQueryScope,
)
from services.project_graph.traceability import get_project_evidence
from services.scopeweave_client import (
    ScopeweaveConfigError,
    ScopeweaveImportResult,
    ScopeweavePushError,
    push_work_item,
)

SOURCE_SYSTEM = "naruon"


class ScopeweaveNotConfiguredError(RuntimeError):
    """No active scopeweave promotion target exists for the workspace."""


@dataclass(frozen=True, slots=True)
class ScopeweavePromotionOutcome:
    project_uid: str
    object_uid: str
    object_type: str
    scopeweave_work_item_id: str
    scopeweave_work_item_url: str | None
    promoted_confidence: float
    citation_count: int
    created: bool


async def load_active_target(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
) -> ScopeweavePromotionTarget | None:
    """Resolve the active scopeweave target for the caller's workspace."""
    statement = select(ScopeweavePromotionTarget).where(
        ScopeweavePromotionTarget.workspace_id == scope.workspace_id,
        ScopeweavePromotionTarget.organization_id == scope.organization_id,
        ScopeweavePromotionTarget.is_active.is_(True),
    )
    result = await session.execute(statement)
    return result.scalars().first()


def build_import_payload(evidence: ProjectEvidence) -> dict[str, Any]:
    """Serialize evidence into the scopeweave import contract, keeping citations.

    Every citation carries the source segment uid, the originating email/thread
    record, and positional context so scopeweave can trace the work item back to
    grounded evidence rather than a free-text summary.
    """
    citations = [
        {
            "content_segment_uid": citation.content_segment_uid,
            "source_kind": citation.source_kind,
            "source_record_uid": citation.source_record_uid,
            "heading_path": citation.heading_path,
            "segment_path": citation.segment_path,
            "ordinal_index": citation.ordinal_index,
            "safe_text_excerpt": citation.safe_text_excerpt,
        }
        for citation in evidence.citation_bundle
    ]
    return {
        "source_system": SOURCE_SYSTEM,
        "external_ref": {
            "project_uid": evidence.project_uid,
            "object_uid": evidence.object_uid,
        },
        "work_item": {
            "object_type": evidence.object_type,
            "title": evidence.title,
            "summary": evidence.summary,
            "status_code": evidence.status_code,
            "confidence": evidence.confidence,
        },
        "citations": citations,
    }


async def _upsert_link(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    evidence: ProjectEvidence,
    actor_user_id: str,
    result: ScopeweaveImportResult,
    citation_count: int,
) -> bool:
    statement = select(ScopeweavePromotionLink).where(
        ScopeweavePromotionLink.workspace_id == scope.workspace_id,
        ScopeweavePromotionLink.object_uid == evidence.object_uid,
    )
    existing = (await session.execute(statement)).scalars().first()
    now = datetime.datetime.now(datetime.timezone.utc)
    if existing is None:
        session.add(
            ScopeweavePromotionLink(
                user_id=scope.user_id,
                organization_id=scope.organization_id,
                workspace_id=scope.workspace_id,
                project_uid=evidence.project_uid,
                object_uid=evidence.object_uid,
                object_type=evidence.object_type,
                scopeweave_work_item_id=result.work_item_id,
                scopeweave_work_item_url=result.work_item_url,
                promoted_confidence=evidence.confidence,
                citation_count=citation_count,
                promoted_by_user_id=actor_user_id,
            )
        )
        return True

    existing.project_uid = evidence.project_uid
    existing.object_type = evidence.object_type
    existing.scopeweave_work_item_id = result.work_item_id
    existing.scopeweave_work_item_url = result.work_item_url
    existing.promoted_confidence = evidence.confidence
    existing.citation_count = citation_count
    existing.promoted_by_user_id = actor_user_id
    existing.updated_at = now
    return False


async def promote_project_object(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
    object_uid: str,
    actor_user_id: str,
) -> ScopeweavePromotionOutcome:
    """Push a project-graph object to scopeweave and persist the mapping.

    Raises ``ScopeweaveNotConfiguredError`` when the workspace has no active
    target (graceful degradation), ``ProjectGraphNotFoundError`` when the object
    or its evidence is missing, ``ScopeweaveConfigError`` for an invalid target
    URL, and ``ScopeweavePushError`` when scopeweave rejects the request.
    """
    target = await load_active_target(session, scope=scope)
    if target is None:
        raise ScopeweaveNotConfiguredError(
            "Scopeweave promotion is not configured for this workspace"
        )

    evidence = await get_project_evidence(
        session,
        scope=scope,
        project_uid=project_uid,
        object_uid=object_uid,
    )

    payload = build_import_payload(evidence)
    result = await push_work_item(
        base_url=target.base_url,
        access_token=target.access_token,
        payload=payload,
    )

    created = await _upsert_link(
        session,
        scope=scope,
        evidence=evidence,
        actor_user_id=actor_user_id,
        result=result,
        citation_count=len(evidence.citation_bundle),
    )

    return ScopeweavePromotionOutcome(
        project_uid=evidence.project_uid,
        object_uid=evidence.object_uid,
        object_type=evidence.object_type,
        scopeweave_work_item_id=result.work_item_id,
        scopeweave_work_item_url=result.work_item_url,
        promoted_confidence=evidence.confidence,
        citation_count=len(evidence.citation_bundle),
        created=created,
    )


__all__ = [
    "ScopeweaveConfigError",
    "ScopeweaveNotConfiguredError",
    "ScopeweavePromotionOutcome",
    "ScopeweavePushError",
    "build_import_payload",
    "load_active_target",
    "promote_project_object",
]
