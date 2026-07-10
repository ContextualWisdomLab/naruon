import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts import verify_evidence_snapshot as verifier


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_evidence_snapshot.py"


def _valid_snapshot() -> dict[str, object]:
    snapshot: dict[str, object] = {
        "snapshot_version": "data_quality_evidence_snapshot.v1",
        "generated_at": "2026-07-02T00:00:00Z",
        "audit_event": "data.quality_surface.evidence_snapshot.viewed",
        "scope_label": "signed_workspace_scope",
        "privacy_redaction_policy": {
            "raw_content_exposed": False,
            "stable_identifiers_exposed": False,
            "provider_credentials_exposed": False,
            "redacted_fields": [
                "raw_email_body",
                "raw_html",
                "attachment_bytes",
                "message_id",
                "attachment_id",
                "source_record_id",
                "stable_database_id",
                "provider_credentials",
                "db_evidence_column_strings",
            ],
            "allowed_sample_fields": [
                "sample_key",
                "source_kind",
                "segment_kind",
                "edge_kind",
                "segment_path",
                "edge_path",
                "word_count",
                "endpoint_status",
            ],
        },
        "validation_status": {
            "status_code": "needs_attention",
            "checks_passed": 2,
            "checks_with_issues": 1,
            "total_checks": 3,
        },
        "parser_manifest_summary": [
            {
                "parser_key": "plain_text",
                "display_name": "Plain text attachments",
                "parse_status": "parsed",
                "content_types": ["text/plain"],
                "extensions": [".txt", ".text"],
            }
        ],
        "quality_checks": [
            {
                "check_key": "content_graph_coverage",
                "display_name": "Content graph coverage",
                "status_code": "needs_attention",
                "issue_count": 1,
                "total_count": 4,
                "detail_text": "Some scoped content still needs paragraph segments.",
            }
        ],
        "content_graph_topology_counts": [
            {"source_kind": "email_body", "segment_kind": "paragraph", "object_count": 6}
        ],
        "knowledge_graph_topology_counts": [
            {
                "source_kind": "email_body",
                "edge_kind": "node_has_segment",
                "object_count": 8,
            }
        ],
        "content_graph_evidence_samples": [
            {
                "sample_key": "segment_0123456789abcdef",
                "source_kind": "email_body",
                "segment_kind": "paragraph",
                "segment_path": "/document[1]/paragraph[1]",
                "word_count": 12,
            }
        ],
        "knowledge_graph_evidence_samples": [
            {
                "sample_key": "edge_0123456789abcdef",
                "source_kind": "email_body",
                "edge_kind": "node_has_segment",
                "edge_path": "/document[1]/paragraph[1]/has/segment[1]",
                "endpoint_status": "segment_backed",
            }
        ],
    }
    digest_payload = dict(snapshot)
    canonical_payload = json.dumps(
        digest_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    snapshot["snapshot_digest"] = hashlib.sha256(canonical_payload).hexdigest()
    snapshot["digest_algorithm"] = "sha256"
    snapshot["canonical_payload_fields"] = sorted(digest_payload)
    return snapshot


def test_verify_snapshot_payload_accepts_matching_digest():
    snapshot = _valid_snapshot()

    result = verifier.verify_snapshot_payload(snapshot)

    assert result.ok is True
    assert result.exit_code == 0
    assert result.actual_digest == snapshot["snapshot_digest"]
    assert result.expected_digest == snapshot["snapshot_digest"]
    assert result.canonical_payload_fields == snapshot["canonical_payload_fields"]


def test_verify_snapshot_payload_rejects_tampering_without_raw_leakage():
    snapshot = _valid_snapshot()
    snapshot["quality_checks"][0]["issue_count"] = 2
    snapshot["quality_checks"][0]["detail_text"] = (
        "source email body <asset-ready@example.com> cseg_email_paragraph_1 "
        "credentials_encrypted"
    )

    result = verifier.verify_snapshot_payload(snapshot)
    serialized = json.dumps(result.to_output(), sort_keys=True)

    assert result.ok is False
    assert result.exit_code == 4
    assert result.error_code == "digest_mismatch"
    assert result.expected_digest == snapshot["snapshot_digest"]
    assert result.actual_digest != snapshot["snapshot_digest"]
    for forbidden in (
        "source email body",
        "<asset-ready@example.com>",
        "cseg_email_paragraph_1",
        "credentials_encrypted",
    ):
        assert forbidden not in serialized


def test_verify_snapshot_payload_rejects_missing_and_unsupported_metadata():
    missing_digest = verifier.verify_snapshot_payload({"digest_algorithm": "sha256"})
    unsupported_algorithm = verifier.verify_snapshot_payload(
        {"snapshot_digest": "abc", "digest_algorithm": "sha512"}
    )

    assert missing_digest.ok is False
    assert missing_digest.exit_code == 2
    assert missing_digest.error_code == "missing_snapshot_digest"
    assert unsupported_algorithm.ok is False
    assert unsupported_algorithm.exit_code == 3
    assert unsupported_algorithm.error_code == "unsupported_digest_algorithm"


def test_cli_verifies_snapshot_file_and_stdin(tmp_path):
    snapshot = _valid_snapshot()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    file_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(snapshot_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    stdin_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "-"],
        input=json.dumps(snapshot),
        check=False,
        capture_output=True,
        text=True,
    )

    assert file_result.returncode == 0, file_result.stderr
    assert stdin_result.returncode == 0, stdin_result.stderr
    assert json.loads(file_result.stdout)["ok"] is True
    assert json.loads(stdin_result.stdout)["ok"] is True


def test_cli_rejects_invalid_json_without_echoing_input(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"raw_email_body": "source email body"', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(bad_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout) == {"ok": False, "error_code": "invalid_json"}
    assert "source email body" not in result.stdout
