import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from api.auth import AuthContext, get_auth_context
from db.models import DiskSageFileLineageRecord
from db.session import get_db
from services.disksage_file_lineage import (
    FileLineageEnvelope,
    FileLineageSummary,
    canonical_envelope_json,
    canonical_envelope_sha256,
    ontology_predicates,
)
from core.runtime_secrets import EncryptionKeyMissingError

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
        content_bytes=record.content_bytes,
        ontology_class=record.ontology_class,
        ontology_relation_count=record.ontology_relation_count,
        ontology_predicates=list(record.ontology_predicates or []),
        provider_name=record.provider_name,
        provider_sync_confirmed=record.provider_sync_confirmed,
        provider_sync_state=record.provider_sync_state,
        created_at=record.created_at.isoformat(),
    )


def _encrypted_envelope_json(envelope: FileLineageEnvelope) -> str:
    return canonical_envelope_json(envelope)


def _lineage_scope(auth_context: AuthContext) -> tuple[object, ...]:
    organization_filter = (
        DiskSageFileLineageRecord.organization_id == auth_context.organization_id
        if auth_context.organization_id is not None
        else DiskSageFileLineageRecord.organization_id.is_(None)
    )
    return (
        DiskSageFileLineageRecord.user_id == auth_context.user_id,
        organization_filter,
        DiskSageFileLineageRecord.workspace_id == auth_context.workspace_id,
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
            *_lineage_scope(auth_context),
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

    try:
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
            content_bytes=envelope.bytes,
            ontology_class=envelope.ontology_class,
            ontology_relation_count=len(envelope.ontology_relations),
            ontology_predicates=ontology_predicates(envelope),
            provider_name=envelope.cloud_copy.provider,
            provider_sync_confirmed=envelope.cloud_copy.provider_sync_confirmed,
            provider_sync_state=envelope.cloud_copy.provider_sync_state or "unknown",
            envelope_json_encrypted=_encrypted_envelope_json(envelope),
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
    except IntegrityError:
        await db.rollback()
        replayed_result = await db.execute(
            select(DiskSageFileLineageRecord).where(
                *_lineage_scope(auth_context),
                DiskSageFileLineageRecord.lineage_fingerprint == lineage_fingerprint,
            )
        )
        replayed = replayed_result.scalar_one_or_none()
        if replayed is None:
            raise
        if replayed.envelope_sha256 != envelope_sha256:
            raise HTTPException(
                status_code=409,
                detail="lineage fingerprint is already bound to different evidence",
            ) from None
        return _summary(replayed)
    except EncryptionKeyMissingError as error:
        await db.rollback()
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
            *_lineage_scope(auth_context),
        )
        .order_by(DiskSageFileLineageRecord.created_at.desc())
        .limit(limit)
    )
    return [_summary(record) for record in result.scalars().all()]
