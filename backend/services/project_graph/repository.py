from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    ContentSegmentRecord,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
)

from .models import ProjectSemanticEdge, ProjectSemanticExtractionResult


@dataclass(frozen=True, slots=True)
class ProjectGraphPersistResult:
    objects: tuple[ProjectGraphObjectRecord, ...]
    edges: tuple[ProjectGraphEdgeRecord, ...]


class ProjectGraphRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def persist_extraction(
        self,
        *,
        extraction: ProjectSemanticExtractionResult,
        user_id: str,
        organization_id: str | None,
        workspace_id: str,
        status_code: str = "candidate",
    ) -> ProjectGraphPersistResult:
        segment_uids = _unique_source_segment_uids(
            semantic_object.source_segment_uids
            for semantic_object in extraction.objects
        )
        segment_map = await self._load_segment_map(segment_uids)
        _validate_segment_scope(
            segment_map.values(),
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )

        object_records = await self._upsert_objects(
            extraction=extraction,
            segment_map=segment_map,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            status_code=status_code,
        )
        await self._session.flush()
        object_map = {record.object_uid: record for record in object_records}
        edge_records = await self._upsert_edges(
            edges=extraction.edges,
            object_map=object_map,
            segment_map=segment_map,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        await self._session.flush()

        return ProjectGraphPersistResult(
            objects=tuple(object_records),
            edges=tuple(edge_records),
        )

    async def apply_correction(
        self,
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
    ) -> ProjectGraphCorrectionRecord:
        project_object = await self._get_scoped_object(
            object_uid=object_uid,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        before_json = _object_snapshot(project_object)
        _apply_projection_updates(project_object, after_json)
        correction = ProjectGraphCorrectionRecord(
            project_object=project_object,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            correction_action=correction_action,
            before_json=before_json,
            after_json=_json_ready(dict(after_json)),
            rationale=rationale,
            source_segment_uids=list(
                source_segment_uids or tuple(project_object.source_segment_uids)
            ),
            created_at=_utcnow(),
        )
        self._session.add(correction)
        await self._session.flush()
        return correction

    async def _load_segment_map(
        self,
        segment_uids: tuple[str, ...],
    ) -> dict[str, ContentSegmentRecord]:
        if not segment_uids:
            raise ValueError("Project graph projection requires source segments")
        result = await self._session.execute(
            select(ContentSegmentRecord)
            .options(selectinload(ContentSegmentRecord.email))
            .where(ContentSegmentRecord.content_segment_uid.in_(segment_uids))
        )
        records = result.scalars().all()
        segment_map = {record.content_segment_uid: record for record in records}
        missing = sorted(set(segment_uids) - set(segment_map))
        if missing:
            raise ValueError(f"Missing project graph source segments: {missing}")
        return segment_map

    async def _upsert_objects(
        self,
        *,
        extraction: ProjectSemanticExtractionResult,
        segment_map: dict[str, ContentSegmentRecord],
        user_id: str,
        organization_id: str | None,
        workspace_id: str,
        status_code: str,
    ) -> list[ProjectGraphObjectRecord]:
        object_uids = tuple(
            semantic_object.uid for semantic_object in extraction.objects
        )
        existing = await self._load_object_map(object_uids)
        records: list[ProjectGraphObjectRecord] = []
        new_records: list[ProjectGraphObjectRecord] = []
        for semantic_object in extraction.objects:
            primary_segment = segment_map[semantic_object.source_segment_uids[0]]
            record = existing.get(semantic_object.uid)
            if record is None:
                record = ProjectGraphObjectRecord(
                    object_uid=semantic_object.uid,
                    user_id=user_id,
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    email_id=primary_segment.email_id,
                    attachment_id=primary_segment.attachment_id,
                    primary_content_segment_id=primary_segment.content_segment_id,
                    object_type=semantic_object.object_type.value,
                    title=semantic_object.title,
                    summary=semantic_object.summary,
                    status_code=status_code,
                    confidence=semantic_object.confidence,
                    source_segment_uids=list(semantic_object.source_segment_uids),
                    attributes_json=_json_ready(dict(semantic_object.attributes)),
                    extractor_name=semantic_object.extractor_name,
                    extractor_version=semantic_object.extractor_version,
                    created_at=_utcnow(),
                    updated_at=_utcnow(),
                )
                new_records.append(record)
            else:
                record.user_id = user_id
                record.organization_id = organization_id
                record.workspace_id = workspace_id
                record.email_id = primary_segment.email_id
                record.attachment_id = primary_segment.attachment_id
                record.primary_content_segment_id = primary_segment.content_segment_id
                record.object_type = semantic_object.object_type.value
                record.title = semantic_object.title
                record.summary = semantic_object.summary
                record.status_code = status_code
                record.confidence = semantic_object.confidence
                record.source_segment_uids = list(semantic_object.source_segment_uids)
                record.attributes_json = _json_ready(dict(semantic_object.attributes))
                record.extractor_name = semantic_object.extractor_name
                record.extractor_version = semantic_object.extractor_version
                record.updated_at = _utcnow()
            records.append(record)
        if new_records:
            self._session.add_all(new_records)
        return records

    async def _upsert_edges(
        self,
        *,
        edges: tuple[ProjectSemanticEdge, ...],
        object_map: dict[str, ProjectGraphObjectRecord],
        segment_map: dict[str, ContentSegmentRecord],
        user_id: str,
        organization_id: str | None,
        workspace_id: str,
    ) -> list[ProjectGraphEdgeRecord]:
        edge_uids = tuple(_edge_uid(edge) for edge in edges)
        existing = await self._load_edge_map(edge_uids)
        records: list[ProjectGraphEdgeRecord] = []
        new_records: list[ProjectGraphEdgeRecord] = []
        for semantic_edge in edges:
            primary_segment = segment_map[semantic_edge.source_segment_uids[0]]
            record = existing.get(_edge_uid(semantic_edge))
            source_object = object_map.get(semantic_edge.source_uid)
            target_object = object_map.get(semantic_edge.target_uid)
            if record is None:
                record = ProjectGraphEdgeRecord(
                    edge_uid=_edge_uid(semantic_edge),
                    user_id=user_id,
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    source_uid=semantic_edge.source_uid,
                    target_uid=semantic_edge.target_uid,
                    edge_type=semantic_edge.edge_type,
                    confidence=semantic_edge.confidence,
                    source_segment_uids=list(semantic_edge.source_segment_uids),
                    source_object=source_object,
                    target_object=target_object,
                    primary_content_segment_id=primary_segment.content_segment_id,
                    created_at=_utcnow(),
                )
                new_records.append(record)
            else:
                record.user_id = user_id
                record.organization_id = organization_id
                record.workspace_id = workspace_id
                record.source_uid = semantic_edge.source_uid
                record.target_uid = semantic_edge.target_uid
                record.edge_type = semantic_edge.edge_type
                record.confidence = semantic_edge.confidence
                record.source_segment_uids = list(semantic_edge.source_segment_uids)
                record.source_object = source_object
                record.target_object = target_object
                record.primary_content_segment_id = primary_segment.content_segment_id
            records.append(record)
        if new_records:
            self._session.add_all(new_records)
        return records

    async def _load_object_map(
        self,
        object_uids: tuple[str, ...],
    ) -> dict[str, ProjectGraphObjectRecord]:
        if not object_uids:
            return {}
        result = await self._session.execute(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid.in_(object_uids)
            )
        )
        return {record.object_uid: record for record in result.scalars().all()}

    async def _load_edge_map(
        self,
        edge_uids: tuple[str, ...],
    ) -> dict[str, ProjectGraphEdgeRecord]:
        if not edge_uids:
            return {}
        result = await self._session.execute(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.edge_uid.in_(edge_uids)
            )
        )
        return {record.edge_uid: record for record in result.scalars().all()}

    async def _get_scoped_object(
        self,
        *,
        object_uid: str,
        user_id: str,
        organization_id: str | None,
        workspace_id: str,
    ) -> ProjectGraphObjectRecord:
        result = await self._session.execute(
            select(ProjectGraphObjectRecord)
            .where(ProjectGraphObjectRecord.object_uid == object_uid)
            .where(ProjectGraphObjectRecord.user_id == user_id)
            .where(ProjectGraphObjectRecord.organization_id == organization_id)
            .where(ProjectGraphObjectRecord.workspace_id == workspace_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise ValueError("Project graph object is outside the requested scope")
        return record


def _unique_source_segment_uids(
    source_uid_groups: Iterable[tuple[str, ...]],
) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for source_uids in source_uid_groups:
        if not source_uids:
            raise ValueError("Project graph projection requires cited objects")
        for source_uid in source_uids:
            seen.setdefault(source_uid, None)
    return tuple(seen)


def _validate_segment_scope(
    segments: Iterable[ContentSegmentRecord],
    *,
    user_id: str,
    organization_id: str | None,
    workspace_id: str,
) -> None:
    for segment in segments:
        email = segment.email
        expected_workspace_id = (
            f"workspace-{organization_id}"
            if organization_id
            else f"workspace-{user_id}"
        )
        if (
            email.user_id != user_id
            or email.organization_id != organization_id
            or expected_workspace_id != workspace_id
        ):
            raise ValueError(
                "Project graph source segment belongs to a different scope"
            )


def _edge_uid(edge: ProjectSemanticEdge) -> str:
    payload = "|".join(
        (
            edge.source_uid,
            edge.target_uid,
            edge.edge_type,
            ",".join(edge.source_segment_uids),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"project_edge:{digest}"


def _object_snapshot(record: ProjectGraphObjectRecord) -> dict[str, object]:
    return {
        "title": record.title,
        "summary": record.summary,
        "status_code": record.status_code,
        "confidence": record.confidence,
        "attributes_json": record.attributes_json,
        "source_segment_uids": record.source_segment_uids,
    }


def _apply_projection_updates(
    record: ProjectGraphObjectRecord,
    after_json: Mapping[str, Any],
) -> None:
    if "title" in after_json:
        record.title = str(after_json["title"])
    if "summary" in after_json:
        record.summary = str(after_json["summary"])
    if "status_code" in after_json:
        record.status_code = str(after_json["status_code"])
    if "confidence" in after_json:
        confidence = float(after_json["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Project graph correction confidence must be 0..1")
        record.confidence = confidence
    if "attributes_json" in after_json:
        attributes = after_json["attributes_json"]
        if not isinstance(attributes, Mapping):
            raise ValueError(
                "Project graph correction attributes_json must be a mapping"
            )
        record.attributes_json = _json_ready(dict(attributes))
    record.updated_at = _utcnow()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
