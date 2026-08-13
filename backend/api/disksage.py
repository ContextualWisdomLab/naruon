import datetime
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.models import DiskSageFileLineageRecord
from db.session import get_db
from services.disksage_file_lineage import (
    FileLineageEnvelope,
    FileLineageSummary,
    canonical_envelope_sha256,
    ontology_predicates,
)

router = APIRouter(prefix="/api/disksage", tags=["disksage"])


def _summary(record: DiskSageFileLineageRecord) -> FileLineageSummary:
    return FileLineageSummary(
        lineage_record_uid=record.lineage_record_uid,
        lineage_fingerprint=record.lineage_fingerprint,
        schema_version=record.schema_version,
        source_kind=record.source_kind,
        archive_kind=record.archive_kind,
        raw_content_sha256=record.raw_content_sha256,
        raw_content_blake3=record.raw_content_blake3,
        bytes=record.bytes,
        ontology_class=record.ontology_class,
        ontology_relation_count=record.ontology_relation_count,
        ontology_predicates=list(record.ontology_predicates or []),
        provider=record.provider,
        provider_sync_confirmed=record.provider_sync_confirmed,
        created_at=record.created_at.isoformat(),
    )


def _encrypted_envelope_json(envelope: FileLineageEnvelope) -> str:
    return json.dumps(
        envelope.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@router.post("/file-lineage", response_model=FileLineageSummary, status_code=201)
async def ingest_file_lineage(
    envelope: FileLineageEnvelope,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> FileLineageSummary:
    """Persist one validated DiskSage envelope without authorizing source eviction."""

    envelope_sha256 = canonical_envelope_sha256(envelope)
    lineage_fingerprint = envelope.cloud_copy.lineage_fingerprint
    existing_result = await db.execute(
        select(DiskSageFileLineageRecord).where(
            DiskSageFileLineageRecord.user_id == auth_context.user_id,
            DiskSageFileLineageRecord.workspace_id == auth_context.workspace_id,
            DiskSageFileLineageRecord.lineage_fingerprint == lineage_fingerprint,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if existing.envelope_sha256 != envelope_sha256:
            raise HTTPException(
                status_code=409,
                detail="lineage fingerprint is already bound to different evidence",
            )
        return _summary(existing)

    record = DiskSageFileLineageRecord(
        lineage_record_uid=f"disksage_lineage_{uuid.uuid4().hex}",
        user_id=auth_context.user_id,
        organization_id=auth_context.organization_id,
        workspace_id=auth_context.workspace_id,
        lineage_fingerprint=lineage_fingerprint,
        envelope_sha256=envelope_sha256,
        schema_version=envelope.schema_version,
        schema_kind=envelope.schema_kind,
        source_kind=envelope.source_kind,
        archive_kind=envelope.archive_kind,
        raw_content_sha256=envelope.raw_content_sha256,
        raw_content_blake3=envelope.raw_content_blake3,
        bytes=envelope.bytes,
        ontology_class=envelope.ontology_class,
        ontology_relation_count=len(envelope.ontology_relations),
        ontology_predicates=ontology_predicates(envelope),
        provider=envelope.cloud_copy.provider,
        provider_sync_confirmed=envelope.cloud_copy.provider_sync_confirmed,
        envelope_json_encrypted=_encrypted_envelope_json(envelope),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except RuntimeError as error:
        if "ENCRYPTION_KEY is required" not in str(error):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from error
    return _summary(record)


@router.get("/file-lineage", response_model=list[FileLineageSummary])
async def list_file_lineage(
    limit: int = Query(default=50, ge=1, le=100),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[FileLineageSummary]:
    """List redacted lineage graph projections; encrypted envelope values stay server-side."""

    result = await db.execute(
        select(DiskSageFileLineageRecord)
        .where(
            DiskSageFileLineageRecord.user_id == auth_context.user_id,
            DiskSageFileLineageRecord.workspace_id == auth_context.workspace_id,
        )
        .order_by(DiskSageFileLineageRecord.created_at.desc())
        .limit(limit)
    )
    return [_summary(record) for record in result.scalars().all()]
