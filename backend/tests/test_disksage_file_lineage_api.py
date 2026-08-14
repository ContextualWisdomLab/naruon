import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.auth import AuthContext
from api.disksage import ingest_file_lineage, list_file_lineage
from core.runtime_secrets import EncryptionKeyMissingError
from services.disksage_file_lineage import (
    FileLineageEnvelope,
    canonical_envelope_sha256,
)


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


class _Result:
    def __init__(self, record=None, records=()):
        self._record = record
        self._records = tuple(records)

    def scalar_one_or_none(self):
        return self._record

    def scalars(self):
        return self

    def all(self):
        return list(self._records)


class _Session:
    def __init__(self, results, *, commit_error=None):
        self._results = iter(results)
        self.commit_error = commit_error
        self.statements = []
        self.rollback_count = 0
        self.commit_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return next(self._results)

    def add(self, _record):
        pass

    async def commit(self):
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def refresh(self, _record):
        pass

    async def rollback(self):
        self.rollback_count += 1


def _auth() -> AuthContext:
    return AuthContext(
        user_id="user-1",
        role="member",
        organization_id="org-1",
        group_ids=(),
        workspace_id="workspace-1",
    )


def _record(**overrides):
    values = {
        "lineage_record_uid": "disksage_lineage_1",
        "lineage_fingerprint": "f" * 64,
        "schema_version": 1,
        "source_kind": "file",
        "archive_kind": "media",
        "raw_content_sha256": "a" * 64,
        "raw_content_blake3": "b" * 64,
        "content_bytes": 1,
        "ontology_class": "https://disksage.app/ontology#Media",
        "ontology_relation_count": 0,
        "ontology_predicates": [],
        "provider_name": "icloud",
        "provider_sync_confirmed": False,
        "provider_sync_state": "pending-upload",
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "envelope_sha256": "c" * 64,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_replayed_lineage_is_idempotent_with_workspace_and_org_scope():
    envelope = FileLineageEnvelope.model_validate(_envelope())
    record = _record(envelope_sha256=canonical_envelope_sha256(envelope))
    session = _Session([_Result(record)])

    result = await ingest_file_lineage(
        envelope=envelope,
        auth_context=_auth(),
        db=session,
    )

    assert result.lineage_record_uid == record.lineage_record_uid
    assert session.commit_count == 0
    statement = str(session.statements[0])
    assert "organization_id" in statement
    assert "workspace_id" in statement


@pytest.mark.asyncio
async def test_conflicting_lineage_fingerprint_returns_conflict():
    envelope = FileLineageEnvelope.model_validate(_envelope())
    session = _Session([_Result(_record())])

    with pytest.raises(HTTPException) as error:
        await ingest_file_lineage(
            envelope=envelope,
            auth_context=_auth(),
            db=session,
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_missing_encryption_key_rolls_back_as_service_unavailable():
    envelope = FileLineageEnvelope.model_validate(_envelope())
    session = _Session(
        [_Result(None)],
        commit_error=EncryptionKeyMissingError("missing active key"),
    )

    with pytest.raises(HTTPException) as error:
        await ingest_file_lineage(
            envelope=envelope,
            auth_context=_auth(),
            db=session,
        )

    assert error.value.status_code == 503
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_list_lineage_query_is_tenant_scoped():
    session = _Session([_Result(records=[_record()])])

    result = await list_file_lineage(limit=50, auth_context=_auth(), db=session)

    assert len(result) == 1
    statement = str(session.statements[0])
    assert "organization_id" in statement
    assert "workspace_id" in statement
    assert "user_id" in statement
