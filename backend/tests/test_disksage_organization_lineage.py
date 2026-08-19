import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api.auth import AuthContext
from api.disksage import ingest_organization_lineage, list_organization_lineage
from services.disksage_organization_lineage import (
    OrganizationLineageBatch,
    canonical_batch_sha256,
)


def _batch() -> dict[str, object]:
    return {
        "schema": "disksage.organization-lineage-batch",
        "version": 1,
        "generated_at_ms": 1_000,
        "complete": True,
        "batch_fingerprint_sha256": "a" * 64,
        "items": [
            {
                "lineage_fingerprint": "b" * 64,
                "source_size": 42,
                "source_mtime_ms": 123,
                "production_time_ms": 456,
                "production_time_source": "embedded:exiftool:MediaCreateDate",
                "production_time_confidence": "high",
                "ontology_class": "https://disksage.app/ontology#Media",
                "destination_relation": "targetFolder",
                "action": "move",
            }
        ],
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
    def __init__(self, results):
        self._results = iter(results)
        self.statements = []
        self.commit_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return next(self._results)

    def add(self, _record):
        pass

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, _record):
        pass

    async def rollback(self):
        pass


def _auth() -> AuthContext:
    return AuthContext(
        user_id="user-1",
        role="member",
        organization_id="org-1",
        group_ids=(),
        workspace_id="workspace-1",
    )


def _record(**overrides):
    batch = OrganizationLineageBatch.model_validate(_batch())
    values = {
        "organization_lineage_record_uid": "disksage_org_lineage_1",
        "batch_fingerprint_sha256": batch.batch_fingerprint_sha256,
        "envelope_sha256": canonical_batch_sha256(batch),
        "schema_version": 1,
        "item_count": 1,
        "ontology_classes": ["https://disksage.app/ontology#Media"],
        "created_at": datetime.datetime.now(datetime.timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_contract_is_path_free_and_rejects_unknown_fields():
    envelope = OrganizationLineageBatch.model_validate(_batch())
    assert envelope.items[0].ontology_class.endswith("#Media")
    unsafe = _batch()
    unsafe["source_path"] = "/private/source/secret.mov"
    with pytest.raises(ValidationError):
        OrganizationLineageBatch.model_validate(unsafe)


def test_contract_rejects_duplicate_lineage_fingerprints():
    unsafe = _batch()
    unsafe["items"] = [unsafe["items"][0], unsafe["items"][0]]
    with pytest.raises(ValidationError):
        OrganizationLineageBatch.model_validate(unsafe)


@pytest.mark.asyncio
async def test_replayed_batch_is_idempotent_and_workspace_scoped():
    envelope = OrganizationLineageBatch.model_validate(_batch())
    record = _record()
    session = _Session([_Result(record)])

    result = await ingest_organization_lineage(
        envelope=envelope,
        auth_context=_auth(),
        db=session,
    )

    assert result.organization_lineage_record_uid == record.organization_lineage_record_uid
    assert session.commit_count == 0
    statement = str(session.statements[0])
    assert "workspace_id" in statement
    assert "user_id" in statement
    assert "organization_id" in statement


@pytest.mark.asyncio
async def test_list_returns_redacted_summaries_only():
    session = _Session([_Result(records=[_record()])])

    result = await list_organization_lineage(limit=50, auth_context=_auth(), db=session)

    assert len(result) == 1
    assert result[0].ontology_classes == ["https://disksage.app/ontology#Media"]
    assert "envelope_json_encrypted" not in result[0].model_dump()
