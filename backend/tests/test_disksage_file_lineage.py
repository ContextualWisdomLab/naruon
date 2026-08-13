import pytest
from pydantic import ValidationError

from services.disksage_file_lineage import (
    FileLineageEnvelope,
    canonical_envelope_sha256,
    ontology_predicates,
)


def _envelope(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "schema_kind": "disksage.file-lineage",
        "source_kind": "file",
        "archive_kind": "media",
        "source_filename": "Video 1.mov",
        "source_relative_path": "DaVinci Resolve/Video 1.mov",
        "source_context": "DaVinci Resolve",
        "ontology_class": "https://disksage.app/ontology#Media",
        "ontology_relations": [
            {
                "subject": "/Users/example/Movies/Video 1.mov",
                "predicate": "https://disksage.app/ontology#archivedTo",
                "object": "/Users/example/iCloud/DiskSage Archive/Video 1.mov",
                "source": "archive-destination-planner",
            },
            {
                "subject": "source",
                "predicate": "https://disksage.app/ontology#archivedTo",
                "object": "destination",
                "source": "test",
            },
        ],
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
                "field": "production_time",
                "value": "2026-04-28T00:00:00Z",
                "source": "exiftool:MediaCreateDate",
                "confidence": "high",
            }
        ],
        "content_title": "Video 1",
        "content_authors": [],
        "content_context": ["DaVinci Resolve"],
        "duration_ms": 60000,
        "review": {
            "candidate_fingerprint": "c" * 64,
            "review_fingerprint": "d" * 64,
            "requires_review": True,
            "reason_codes": ["destination-account-scope-unknown"],
            "decision_id": "decision-1",
            "disposition": "approved",
            "reviewed_at_ms": 4,
            "reviewed_by": "human:local:test",
            "rationale": "Account scope reviewed",
        },
        "cloud_copy": {
            "receipt_id": "e" * 64,
            "lineage_fingerprint": "f" * 64,
            "provider": "icloud",
            "destination_account_scope": "unknown",
            "destination": "/Users/example/iCloud/DiskSage Archive/Video 1.mov",
            "copied_at_ms": 5,
            "copy_verification_method": "copied-by-disk-sage",
            "local_copy_verified": True,
            "provider_write_executed": False,
            "provider_sync_confirmed": False,
            "sync_evidence_record_id": None,
            "sync_evidence_kind": None,
            "sync_evidence_id": None,
            "sync_confirmed_at_ms": None,
            "remote_object_id": None,
            "remote_revision": None,
            "remote_location_bound": None,
        },
    }
    payload.update(overrides)
    return payload


def test_valid_envelope_keeps_graph_projection_deterministic():
    envelope = FileLineageEnvelope.model_validate(_envelope())

    assert envelope.schema_kind == "disksage.file-lineage"
    assert len(envelope.ontology_relations) == 2
    assert ontology_predicates(envelope) == ["https://disksage.app/ontology#archivedTo"]
    assert len(canonical_envelope_sha256(envelope)) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_relative_path", "/absolute/path.mov"),
        ("source_relative_path", "../escape.mov"),
        ("source_filename", "different.mov"),
    ],
)
def test_path_binding_rejects_unsafe_or_mismatched_values(field: str, value: str):
    with pytest.raises(ValidationError):
        FileLineageEnvelope.model_validate(_envelope(**{field: value}))


def test_provider_write_claim_is_rejected_even_when_copy_is_verified():
    payload = _envelope()
    payload["cloud_copy"] = {
        **payload["cloud_copy"],  # type: ignore[arg-type]
        "provider_write_executed": True,
    }
    with pytest.raises(ValidationError):
        FileLineageEnvelope.model_validate(payload)


def test_provider_sync_state_preserves_pending_upload_without_eviction_claim():
    payload = _envelope()
    payload["cloud_copy"] = {
        **payload["cloud_copy"],  # type: ignore[arg-type]
        "provider_sync_state": "pending-upload",
    }

    envelope = FileLineageEnvelope.model_validate(payload)

    assert envelope.cloud_copy.provider_sync_state == "pending-upload"
    assert envelope.cloud_copy.provider_sync_confirmed is False


def test_unknown_fields_are_rejected_at_the_handoff_boundary():
    payload = _envelope(untrusted_private_value="must-not-persist")
    with pytest.raises(ValidationError):
        FileLineageEnvelope.model_validate(payload)


def test_naruon_exposes_the_scoped_lineage_resource():
    from main import app

    assert "/api/disksage/file-lineage" in app.openapi()["paths"]
