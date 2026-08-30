import uuid

import asyncpg
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.disksage import ingest_file_lineage, list_file_lineage
from core.config import settings
from db.models import Base, DiskSageFileLineageRecord
from services.disksage_file_lineage import FileLineageEnvelope


def _envelope() -> dict[str, object]:
    return {
        "schema_version": 1,
        "schema_kind": "disksage.file-lineage",
        "source_kind": "file",
        "archive_kind": "media",
        "source_filename": "Video 1.mov",
        "source_relative_path": "DaVinci Resolve/Video 1.mov",
        "source_context": "DaVinci Resolve",
        "ontology_class": "https://disksage.app/ontology#Media",
        "ontology_relations": [],
        "raw_content_sha256": "a" * 64,
        "raw_content_blake3": "b" * 64,
        "bytes": 160085038,
        "production_time": {
            "selected_value_ms": 1,
            "selected_source": "embedded:exiftool:MediaCreateDate",
            "confidence": "high",
            "evidence_precedence": [
                "embedded_metadata",
                "explicit_filename_date",
                "filesystem_created_at",
                "filesystem_modified_at",
            ],
        },
        "filesystem_time": {"created_at_ms": 2, "modified_at_ms": 3},
        "metadata_evidence": [
            {
                "field": "production-date",
                "value": "1970-01-01",
                "source": "embedded:exiftool:MediaCreateDate",
                "confidence": "high",
            }
        ],
        "content_authors": [],
        "content_context": [],
        "review": {
            "candidate_fingerprint": "c" * 64,
            "review_fingerprint": "d" * 64,
            "requires_review": False,
            "reason_codes": [],
        },
        "cloud_copy": {
            "receipt_id": "e" * 64,
            "lineage_fingerprint": "f" * 64,
            "provider": "icloud",
            "destination_account_scope": "unknown",
            "destination": "/Users/example/iCloud/Video 1.mov",
            "copied_at_ms": 5,
            "copy_verification_method": "copied-by-disk-sage",
            "local_copy_verified": True,
            "provider_write_executed": False,
            "provider_sync_confirmed": False,
        },
    }


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_file_lineage_ingest_and_list_postgres_smoke():
    database_url = getattr(settings, "DATABASE_URL", None)
    if not database_url:
        pytest.skip("PostgreSQL smoke path unavailable: DATABASE_URL is not set")

    scope = uuid.uuid4().hex
    auth_context = AuthContext(
        user_id=f"disksage_smoke_user_{scope}",
        role="member",
        organization_id=f"disksage_smoke_org_{scope}",
        group_ids=(),
        workspace_id=f"disksage_smoke_workspace_{scope}",
    )
    envelope = FileLineageEnvelope.model_validate(_envelope())
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    previous_key = settings.ENCRYPTION_KEY
    settings.ENCRYPTION_KEY = SecretStr(Fernet.generate_key().decode("ascii"))
    record_uid = None
    try:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await connection.run_sync(Base.metadata.create_all)
        except (OperationalError, asyncpg.PostgresError, OSError):
            pytest.skip("PostgreSQL smoke schema is unavailable")

        async with session_factory() as session:
            summary = await ingest_file_lineage(
                envelope=envelope,
                auth_context=auth_context,
                db=session,
            )
            record_uid = summary.lineage_record_uid

        async with session_factory() as session:
            summaries = await list_file_lineage(
                limit=50,
                auth_context=auth_context,
                db=session,
            )
            assert [item.lineage_record_uid for item in summaries] == [record_uid]
            assert summaries[0].provider_sync_state == "unknown"
    finally:
        settings.ENCRYPTION_KEY = previous_key
        if record_uid is not None:
            async with session_factory() as session:
                await session.execute(
                    delete(DiskSageFileLineageRecord).where(
                        DiskSageFileLineageRecord.lineage_record_uid == record_uid
                    )
                )
                await session.commit()
        await engine.dispose()
