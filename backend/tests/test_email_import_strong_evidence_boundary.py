import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import services.email_import_service as email_import_module
from services.email_dedupe_service import source_email_fingerprint, strong_email_fingerprint
from services.email_import_service import _dedupe_review_reason, _email_fingerprint


_DATE = datetime.datetime(2026, 9, 17, 6, 30, tzinfo=datetime.timezone.utc)
_SOURCE = b"From: sender@example.com\r\nTo: recipient@example.com\r\nSubject: Plan\r\n\r\nBody"
_COMPLETE = {
    "sender": "sender@example.com",
    "recipients": "recipient@example.com",
    "subject": "Plan",
    "body": "Body",
    "date": _DATE,
    "date_provenance": "parsed",
}


def test_import_metadata_strong_fingerprint_requires_recipient_evidence() -> None:
    expected_strong = strong_email_fingerprint(
        sender=_COMPLETE["sender"],
        subject=_COMPLETE["subject"],
        date=_DATE,
        body=_COMPLETE["body"],
    )
    assert expected_strong is not None
    assert _email_fingerprint(dict(_COMPLETE), _DATE, _SOURCE) == expected_strong

    incomplete = {**_COMPLETE, "recipients": ""}
    assert _email_fingerprint(incomplete, _DATE, _SOURCE) == source_email_fingerprint(
        _SOURCE,
        source_kind="raw",
    )


def test_import_review_reason_tracks_withheld_strong_metadata_evidence() -> None:
    assert _dedupe_review_reason(dict(_COMPLETE)) is None
    assert _dedupe_review_reason({**_COMPLETE, "recipients": ""}) == (
        "dedupe_review_required"
    )
    assert _dedupe_review_reason({**_COMPLETE, "date_provenance": "invalid"}) == (
        "dedupe_review_required"
    )


@pytest.mark.asyncio
async def test_import_result_marks_incomplete_metadata_for_dedupe_review(
    monkeypatch,
    tmp_path,
) -> None:
    eml_path = tmp_path / "message.eml"
    eml_path.write_bytes(_SOURCE)
    parsed = {
        **_COMPLETE,
        "message_id": "",
        "recipients": "",
        "attachments": [],
    }
    email_object = MagicMock()
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    monkeypatch.setattr(
        email_import_module.settings,
        "PROJECT_GRAPH_EXTRACTION_ENABLED",
        False,
    )
    monkeypatch.setattr(
        email_import_module,
        "_read_and_parse_eml",
        lambda _: (_SOURCE, parsed),
    )
    monkeypatch.setattr(
        email_import_module,
        "_find_existing_email",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        email_import_module,
        "assign_thread_id",
        AsyncMock(return_value="thread-1"),
    )
    monkeypatch.setattr(
        email_import_module,
        "_extract_and_generate_embeddings",
        AsyncMock(return_value=([], [[0.0] * email_import_module.EMBEDDING_DIMENSION])),
    )
    monkeypatch.setattr(
        email_import_module,
        "_build_email_object",
        lambda **_: (email_object, 0),
    )
    monkeypatch.setattr(
        email_import_module,
        "_persist_project_graph_projection",
        AsyncMock(),
    )

    result = await email_import_module._import_single_eml(
        session,
        eml_path=eml_path,
        display_filename="message.eml",
        user_id="user-1",
        organization_id="org-1",
    )

    assert result.status == "imported"
    assert result.reason_code == "dedupe_review_required"
    session.commit.assert_awaited_once()
