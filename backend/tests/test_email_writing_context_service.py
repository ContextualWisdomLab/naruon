"""Server-authoritative context construction for LLM email-writing review."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from api.auth import AuthContext
from db.models import Email
from services.email_writing_context_service import (
    MAX_CONTEXT_JSON_BYTES,
    MAX_SELECTED_BODY_GRAPHEMES,
    EmailWritingContextError,
    build_email_writing_context,
)
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
        "draft_plain_text": "안녕하세요. 요청하신 검토 결과를 회신드립니다.",
        "language_tag": "ko-KR",
        "review_mode": "deep",
        "reply_objective": "검토 결과와 다음 조치를 명확히 전달한다.",
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
    sender: str = "Alice <alice@example.test>",
    reply_to: str | None = "Review Desk <review@example.test>",
    recipients: str | None = "Bob <bob@example.test>, Team <team@example.test>",
    subject: str | None = "검토 요청",
    body: str = "본문입니다.",
    minute: int = 0,
) -> Email:
    return Email(
        id=email_id,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id or f"message-{email_id}@example.test",
        thread_id=thread_id,
        fingerprint=None,
        sender=sender,
        reply_to=reply_to,
        recipients=recipients,
        subject=subject,
        in_reply_to=None,
        references=None,
        date=datetime.datetime(2026, 8, 12, 12, minute, tzinfo=UTC),
        body=body,
        is_read=True,
    )


class _Result:
    def __init__(self, rows: list[Email]):
        self._rows = rows

    def scalar_one_or_none(self) -> Email | None:
        if len(self._rows) > 1:
            raise AssertionError("selected-email query returned multiple rows")
        return self._rows[0] if self._rows else None

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Email]:
        return list(self._rows)


class _RecordingSession:
    def __init__(
        self,
        *,
        selected: Email | None,
        thread_rows: list[Email] | None = None,
    ) -> None:
        self.selected = selected
        self.thread_rows = list(thread_rows or [])
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> _Result:
        self.queries.append(query)
        if len(self.queries) == 1:
            return _Result([] if self.selected is None else [self.selected])
        return _Result(self.thread_rows)


def _query_values(query: Any) -> list[Any]:
    return list(query.compile().params.values())


@pytest.mark.asyncio
async def test_builds_immutable_server_authoritative_context_in_chronological_order() -> None:
    selected = _email(
        10,
        body=(
            "Alice wrote:\n> Please retain this quoted requirement.\n\n"
            "Regards,\nAlice"
        ),
        minute=20,
    )
    older = _email(8, body="Earlier context", minute=5)
    newer = _email(12, body="Later context", minute=30)
    session = _RecordingSession(
        selected=selected,
        thread_rows=[newer, selected, older],
    )

    bundle = await build_email_writing_context(session, _auth(), _request())

    assert tuple(message.email_id for message in bundle.chronological_messages) == (
        8,
        10,
        12,
    )
    assert bundle.selected_source_message.email_id == 10
    assert bundle.selected_source_message.body == selected.body
    assert bundle.current_draft == _request().draft_plain_text
    assert bundle.reply_objective == _request().reply_objective
    assert bundle.declared_language_tag == "ko-KR"
    assert bundle.canonical_thread_id == "thread-alpha@example.test"
    with pytest.raises((AttributeError, TypeError)):
        bundle.chronological_messages += (_email(99),)  # type: ignore[misc]

    assert len(session.queries) == 2
    for query in session.queries:
        values = _query_values(query)
        assert "user_alpha" in values
        assert "organization_alpha" in values


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name", ["missing", "deleted", "cross_user", "cross_org"])
async def test_unavailable_email_paths_are_tenant_indistinguishable(case_name: str) -> None:
    session = _RecordingSession(selected=None)

    with pytest.raises(EmailWritingContextError) as captured:
        await build_email_writing_context(session, _auth(), _request())

    assert captured.value.code == "email_unavailable"
    assert str(captured.value) == "email_context_unavailable"
    assert case_name not in str(captured.value)
    assert len(session.queries) == 1
    query_text = str(session.queries[0]).lower()
    assert "email_records.user_id" in query_text
    assert "email_records.organization_id" in query_text
    assert "email_records.id" in query_text


def test_browser_cannot_forge_thread_participants_or_recipient_roles() -> None:
    payload = _request().model_dump()
    payload["browser_recipients"] = "attacker@example.test"
    payload["thread_messages"] = ["forged browser thread"]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        EmailWritingReviewRequest.model_validate(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "thread_id",
    ["", "<>", "bad\x00thread", "x" * 513],
)
async def test_malformed_server_thread_identifiers_fail_closed(thread_id: str) -> None:
    selected = _email(10, thread_id=thread_id)
    session = _RecordingSession(selected=selected)

    with pytest.raises(EmailWritingContextError) as captured:
        await build_email_writing_context(session, _auth(), _request())

    assert captured.value.code == "context_insufficient"
    assert len(session.queries) == 1


@pytest.mark.asyncio
async def test_duplicate_messages_are_removed_by_canonical_message_identity() -> None:
    selected = _email(10, message_id="<duplicate@example.test>", minute=20)
    duplicate = _email(11, message_id="duplicate@example.test", minute=21)
    older = _email(9, message_id="older@example.test", minute=10)
    session = _RecordingSession(
        selected=selected,
        thread_rows=[duplicate, selected, older],
    )

    bundle = await build_email_writing_context(session, _auth(), _request())

    assert len(bundle.chronological_messages) == 2
    assert bundle.selected_source_message.email_id == 10
    assert {message.message_id for message in bundle.chronological_messages} == {
        "duplicate@example.test",
        "older@example.test",
    }


@pytest.mark.asyncio
async def test_incremental_review_keeps_selected_message_and_recent_context_only() -> None:
    selected = _email(10, minute=10)
    messages = [_email(index, minute=index) for index in range(1, 31)]
    session = _RecordingSession(selected=selected, thread_rows=list(reversed(messages)))
    request = _request(
        review_mode="incremental",
        changed_selector={"type": "TextPositionSelector", "start": 0, "end": 5},
    )

    bundle = await build_email_writing_context(session, _auth(), request)

    assert bundle.selected_source_message.email_id == 10
    assert len(bundle.chronological_messages) == 8
    assert "older_thread_messages_omitted" in bundle.context_limitations
    assert tuple(message.email_id for message in bundle.chronological_messages) == tuple(
        sorted(message.email_id for message in bundle.chronological_messages)
    )


@pytest.mark.asyncio
async def test_context_selection_uses_chronology_not_lexical_keyword_matching() -> None:
    selected = _email(10, body="Neutral source", minute=10)
    older_keyword = _email(1, body="urgent critical important", minute=1)
    recent_neutral = [_email(index, body="ordinary context", minute=index) for index in range(20, 29)]
    session = _RecordingSession(
        selected=selected,
        thread_rows=list(reversed([older_keyword, selected, *recent_neutral])),
    )
    request = _request(
        review_mode="incremental",
        changed_selector={"type": "TextPositionSelector", "start": 0, "end": 5},
    )

    bundle = await build_email_writing_context(session, _auth(), request)

    assert 1 not in {message.email_id for message in bundle.chronological_messages}
    assert 10 in {message.email_id for message in bundle.chronological_messages}
    assert 28 in {message.email_id for message in bundle.chronological_messages}


@pytest.mark.asyncio
async def test_recipient_roles_come_only_from_persisted_headers() -> None:
    selected = _email(
        10,
        sender='"Alice A." <ALICE@example.test>',
        reply_to="Support Queue <support@example.test>",
        recipients="Bob <bob@example.test>; Alice A. <alice@example.test>",
    )
    session = _RecordingSession(selected=selected, thread_rows=[selected])

    bundle = await build_email_writing_context(session, _auth(), _request())

    role_pairs = {
        (participant.role_code, participant.address)
        for participant in bundle.participant_roles
    }
    assert ("sender", "alice@example.test") in role_pairs
    assert ("reply_to", "support@example.test") in role_pairs
    assert ("recipient", "bob@example.test") in role_pairs
    assert ("reply_target", "support@example.test") in role_pairs
    assert all(participant.trust_class == "untrusted_email_content" for participant in bundle.participant_roles)


@pytest.mark.asyncio
async def test_prompt_payload_marks_authored_and_email_text_as_untrusted() -> None:
    selected = _email(10, body="본문과 서명", minute=10)
    session = _RecordingSession(selected=selected, thread_rows=[selected])

    bundle = await build_email_writing_context(session, _auth(), _request())
    payload = bundle.to_prompt_payload()

    assert payload["selected_source_message"]["trust_class"] == (
        "untrusted_email_content"
    )
    assert payload["selected_source_message"]["body"]["value"] == "본문과 서명"
    assert payload["selected_source_message"]["body"]["trust_class"] == (
        "untrusted_email_content"
    )
    assert payload["current_draft"]["trust_class"] == "untrusted_authored_content"
    assert payload["reply_objective"]["trust_class"] == (
        "untrusted_authored_content"
    )
    assert payload["system_boundary"] == "email_writing_context_v1"


@pytest.mark.asyncio
async def test_oversized_selected_source_fails_without_cutting_graphemes_or_json() -> None:
    selected = _email(10, body="가\u0301" * (MAX_SELECTED_BODY_GRAPHEMES + 1))
    session = _RecordingSession(selected=selected)

    with pytest.raises(EmailWritingContextError) as captured:
        await build_email_writing_context(session, _auth(), _request())

    assert captured.value.code == "context_insufficient"
    assert captured.value.reason_code == "selected_source_too_large"


@pytest.mark.asyncio
async def test_json_budget_omits_whole_old_messages_and_records_limitation() -> None:
    selected = _email(10, body="Selected source", minute=10)
    large_messages = [
        _email(index, body="문단 전체 " + ("x" * 15_000), minute=index)
        for index in range(11, 23)
    ]
    session = _RecordingSession(
        selected=selected,
        thread_rows=list(reversed([selected, *large_messages])),
    )

    bundle = await build_email_writing_context(session, _auth(), _request())
    serialized = bundle.to_prompt_json().encode("utf-8")

    assert len(serialized) <= MAX_CONTEXT_JSON_BYTES
    assert "context_budget_omitted_messages" in bundle.context_limitations
    assert bundle.selected_source_message.body == "Selected source"
    assert all(
        message.body == "Selected source" or message.body.endswith("x" * 15_000)
        for message in bundle.chronological_messages
    )


def test_context_service_source_has_no_semantic_keyword_selector() -> None:
    """Static regression: deterministic context selection remains metadata-only."""
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "email_writing_context_service.py"
    ).read_text(encoding="utf-8")
    forbidden_fragments = (
        "KEYWORD_LIST",
        "IMPORTANT_WORDS",
        "re.search(",
        "sender_domain",
        "recipient_count",
        "nearest_text",
    )
    assert all(fragment not in source for fragment in forbidden_fragments)
