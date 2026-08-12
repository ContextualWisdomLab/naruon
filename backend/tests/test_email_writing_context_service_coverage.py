"""Terminal branch coverage for the server-authoritative email context service."""

from __future__ import annotations

import datetime
from typing import Any

import pytest

from api.auth import AuthContext
from db.models import Email
from services import email_writing_context_service as context_service
from services.email_writing_contracts import EmailWritingReviewRequest

UTC = datetime.timezone.utc
DIGEST_HEX = "7c" * 32


def _auth(
    *,
    user_id: str = "user_alpha",
    organization_id: str | None = "organization_alpha",
) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id="workspace_alpha",
    )


def _request(**overrides: Any) -> EmailWritingReviewRequest:
    payload: dict[str, Any] = {
        "source_email_id": 10,
        "document_revision": {
            "algorithm": "SHA-256",
            "digest_hex": DIGEST_HEX,
            "strong_entity_tag": f'"sha256-{DIGEST_HEX}"',
        },
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "draft_plain_text": "Reply draft",
        "language_tag": "en-US",
        "review_mode": "deep",
        "reply_objective": "State the verified outcome.",
    }
    payload.update(overrides)
    return EmailWritingReviewRequest.model_validate(payload)


def _email(
    email_id: int,
    *,
    message_id: str | None = None,
    thread_id: str | None = "thread-alpha@example.test",
    user_id: str = "user_alpha",
    organization_id: str = "organization_alpha",
    sender: str | None = "Alice <alice@example.test>",
    reply_to: str | None = None,
    recipients: str | None = "Bob <bob@example.test>",
    subject: str | None = "Subject",
    body: str | None = "Body",
    sent_at: datetime.datetime | None = None,
) -> Email:
    return Email(
        id=email_id,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=None,
        sender=sender,
        reply_to=reply_to,
        recipients=recipients,
        subject=subject,
        in_reply_to=None,
        references=None,
        date=sent_at
        if sent_at is not None
        else datetime.datetime(2026, 8, 12, 12, tzinfo=UTC)
        + datetime.timedelta(seconds=email_id),
        body=body,
        is_read=True,
    )


class _Result:
    def __init__(self, rows: list[Email]):
        self.rows = rows

    def scalar_one_or_none(self) -> Email | None:
        return self.rows[0] if self.rows else None

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Email]:
        return list(self.rows)


class _Session:
    def __init__(self, selected: Email | None, thread_rows: list[Email]) -> None:
        self.selected = selected
        self.thread_rows = thread_rows
        self.call_count = 0

    async def execute(self, _query: Any) -> _Result:
        self.call_count += 1
        if self.call_count == 1:
            return _Result([] if self.selected is None else [self.selected])
        return _Result(self.thread_rows)


def _message(
    email_id: int,
    *,
    message_id: str | None = None,
    sender_header: str = "Alice <alice@example.test>",
    reply_to_header: str | None = None,
    recipient_header: str | None = None,
    selected_source: bool = False,
    second: int | None = None,
) -> context_service.EmailWritingMessageContext:
    return context_service.EmailWritingMessageContext(
        email_id=email_id,
        message_id=message_id or f"message-{email_id}@example.test",
        sent_at=datetime.datetime(
            2026,
            8,
            12,
            12,
            0,
            email_id if second is None else second,
            tzinfo=UTC,
        ),
        subject="Subject",
        sender_header=sender_header,
        reply_to_header=reply_to_header,
        recipient_header=recipient_header,
        body="Body",
        selected_source=selected_source,
    )


def test_safe_server_text_missing_and_invalid_unicode_fail_closed() -> None:
    with pytest.raises(context_service.EmailWritingContextError) as missing:
        context_service._safe_server_text(None, nullable=False)
    assert missing.value.reason_code == "required_server_text_missing"
    assert context_service._safe_server_text(None, nullable=True) is None

    with pytest.raises(context_service.EmailWritingContextError) as invalid:
        context_service._safe_server_text("bad\ud800text", nullable=False)
    assert invalid.value.reason_code == "invalid_server_unicode"


def test_thread_identifier_missing_and_normalization_failure_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = _email(10, message_id=None, thread_id=None)
    with pytest.raises(context_service.EmailWritingContextError) as captured:
        context_service._canonical_selected_thread_id(missing)
    assert captured.value.reason_code == "thread_identifier_missing"

    malformed = _email(10, message_id="message@example.test", thread_id="value")
    monkeypatch.setattr(context_service, "normalize_message_id", lambda _value: None)
    with pytest.raises(context_service.EmailWritingContextError) as normalized:
        context_service._canonical_selected_thread_id(malformed)
    assert normalized.value.reason_code == "thread_identifier_invalid"


def test_thread_membership_handles_missing_matching_and_nonmatching_values() -> None:
    matching = _email(
        10,
        message_id="<thread-alpha@example.test>",
        thread_id=None,
    )
    assert context_service._row_belongs_to_thread(
        matching,
        "thread-alpha@example.test",
    )

    nonmatching = _email(
        11,
        message_id="other-message@example.test",
        thread_id="other-thread@example.test",
    )
    assert not context_service._row_belongs_to_thread(
        nonmatching,
        "thread-alpha@example.test",
    )


def test_message_identifier_and_timestamp_terminal_validation() -> None:
    missing_identifier = _email(10, message_id=None)
    with pytest.raises(context_service.EmailWritingContextError) as identifier_error:
        context_service._normalized_message_id(missing_identifier)
    assert identifier_error.value.reason_code == "message_identifier_invalid"

    with pytest.raises(context_service.EmailWritingContextError) as timestamp_error:
        context_service._normalized_timestamp(None)
    assert timestamp_error.value.reason_code == "message_timestamp_missing"

    naive = datetime.datetime(2026, 8, 12, 12, 0)
    assert context_service._normalized_timestamp(naive).tzinfo == UTC
    aware = datetime.datetime(
        2026,
        8,
        12,
        21,
        0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=9)),
    )
    assert context_service._normalized_timestamp(aware) == datetime.datetime(
        2026,
        8,
        12,
        12,
        0,
        tzinfo=UTC,
    )


@pytest.mark.parametrize("selected_source", [True, False])
def test_subject_bounds_distinguish_selected_and_related_messages(
    selected_source: bool,
) -> None:
    email = _email(
        10,
        message_id="message@example.test",
        subject="x" * (context_service.MAX_SUBJECT_GRAPHEMES + 1),
    )
    with pytest.raises(context_service.EmailWritingContextError) as captured:
        context_service._message_context(email, selected_source=selected_source)
    expected = (
        "selected_subject_too_large"
        if selected_source
        else "related_subject_too_large"
    )
    assert captured.value.reason_code == expected


def test_related_body_bound_uses_complete_message_omission_policy() -> None:
    email = _email(
        11,
        message_id="related@example.test",
        body="x" * (context_service.MAX_RELATED_BODY_GRAPHEMES + 1),
    )
    with pytest.raises(context_service.EmailWritingContextError) as captured:
        context_service._message_context(email, selected_source=False)
    assert captured.value.reason_code == "related_message_too_large"


def test_address_parser_rejects_invalid_and_duplicate_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert context_service._parsed_addresses(None) == ()
    monkeypatch.setattr(
        context_service,
        "getaddresses",
        lambda _headers: [
            ("", ""),
            ("", "bad\ud800@example.test"),
            ("bad\ud800", "display@example.test"),
            ("Alice", "ALICE@example.test"),
            ("Alice", "ALICE@example.test"),
        ],
    )
    assert context_service._parsed_addresses("ignored") == (
        ("Alice", "alice@example.test"),
    )


def test_participant_role_duplicate_and_reply_target_fallback_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = _message(
        10,
        sender_header="Alice <alice@example.test>",
        reply_to_header=None,
        selected_source=True,
    )
    duplicate = _message(
        10,
        sender_header="Alice <alice@example.test>",
    )
    participants = context_service._participant_roles((selected, duplicate), selected)
    assert sum(participant.role_code == "sender" for participant in participants) == 1
    assert any(participant.role_code == "reply_target" for participant in participants)

    original = context_service._parsed_addresses

    def repeated(value: str | None):
        if value == "Reply <reply@example.test>":
            return (
                ("Reply", "reply@example.test"),
                ("Reply", "reply@example.test"),
            )
        return original(value)

    monkeypatch.setattr(context_service, "_parsed_addresses", repeated)
    selected_with_reply = _message(
        20,
        sender_header="Alice <alice@example.test>",
        reply_to_header="Reply <reply@example.test>",
        selected_source=True,
    )
    reply_participants = context_service._participant_roles(
        (selected_with_reply,),
        selected_with_reply,
    )
    assert (
        sum(
            participant.role_code == "reply_target"
            for participant in reply_participants
        )
        == 1
    )


def test_limitation_deduplication_and_message_cap_branches() -> None:
    limitations: list[str] = []
    context_service._append_limitation(limitations, "one")
    context_service._append_limitation(limitations, "one")
    assert limitations == ["one"]
    assert (
        context_service._message_cap("incremental")
        == context_service.MAX_INCREMENTAL_THREAD_MESSAGES
    )
    assert context_service._message_cap("deep") == context_service.MAX_DEEP_THREAD_MESSAGES

    messages = [_message(index, second=index) for index in range(1, 31)]
    retained_limitations: list[str] = []
    retained = context_service._cap_chronological_messages(
        messages,
        selected_email_id=1,
        review_mode="incremental",
        limitations=retained_limitations,
    )
    assert retained[0].email_id == 1
    assert len(retained) == context_service.MAX_INCREMENTAL_THREAD_MESSAGES
    assert retained_limitations == ["older_thread_messages_omitted"]

    recent_limitations: list[str] = []
    recent = context_service._cap_chronological_messages(
        messages,
        selected_email_id=30,
        review_mode="incremental",
        limitations=recent_limitations,
    )
    assert recent[-1].email_id == 30


def test_json_budget_unicode_and_selected_only_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    selected = _message(10, selected_source=True)

    def invalid_json(_self: context_service.EmailWritingContextBundle) -> str:
        raise UnicodeEncodeError("utf-8", "x", 0, 1, "invalid")

    monkeypatch.setattr(
        context_service.EmailWritingContextBundle,
        "to_prompt_json",
        invalid_json,
    )
    with pytest.raises(context_service.EmailWritingContextError) as unicode_error:
        context_service._apply_json_budget(
            request=request,
            canonical_thread_id="thread-alpha@example.test",
            messages=[selected],
            limitations=[],
        )
    assert unicode_error.value.reason_code == "prompt_unicode_invalid"

    monkeypatch.undo()
    monkeypatch.setattr(context_service, "MAX_CONTEXT_JSON_BYTES", 0)
    with pytest.raises(context_service.EmailWritingContextError) as budget_error:
        context_service._apply_json_budget(
            request=request,
            canonical_thread_id="thread-alpha@example.test",
            messages=[selected],
            limitations=[],
        )
    assert budget_error.value.reason_code == "selected_context_budget_exceeded"


@pytest.mark.asyncio
async def test_defensive_owner_mismatch_is_indistinguishable_from_missing() -> None:
    selected = _email(
        10,
        message_id="message@example.test",
        user_id="other_user",
    )
    session = _Session(selected, [])
    with pytest.raises(context_service.EmailWritingContextError) as captured:
        await context_service.build_email_writing_context(
            session,
            _auth(),
            _request(),
        )
    assert captured.value.code == "email_unavailable"


@pytest.mark.asyncio
async def test_candidate_limit_and_invalid_related_message_are_recorded() -> None:
    selected = _email(10, message_id="selected@example.test")
    valid_rows = [
        _email(
            index,
            message_id=f"message-{index}@example.test",
            thread_id="thread-alpha@example.test",
        )
        for index in range(100, 198)
    ]
    invalid_related = _email(
        198,
        message_id="invalid-related@example.test",
        thread_id="thread-alpha@example.test",
        body="x" * (context_service.MAX_RELATED_BODY_GRAPHEMES + 1),
    )
    session = _Session(selected, [invalid_related, *valid_rows])

    bundle = await context_service.build_email_writing_context(
        session,
        _auth(),
        _request(),
    )

    assert "thread_candidate_limit_applied" in bundle.context_limitations
    assert "invalid_thread_message_omitted" in bundle.context_limitations


@pytest.mark.asyncio
async def test_thread_query_filters_same_id_wrong_owner_and_wrong_thread_rows() -> None:
    selected = _email(10, message_id="selected@example.test")
    same_id = _email(10, message_id="same-id@example.test")
    wrong_owner = _email(
        11,
        message_id="wrong-owner@example.test",
        user_id="other_user",
    )
    wrong_thread = _email(
        12,
        message_id="wrong-thread@example.test",
        thread_id="other-thread@example.test",
    )
    valid = _email(13, message_id="valid@example.test")
    session = _Session(selected, [same_id, wrong_owner, wrong_thread, valid])

    bundle = await context_service.build_email_writing_context(
        session,
        _auth(),
        _request(),
    )
    assert {message.email_id for message in bundle.chronological_messages} == {10, 13}
