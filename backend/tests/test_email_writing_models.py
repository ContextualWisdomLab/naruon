"""Model-level contracts for privacy-minimized email-writing evidence."""

from __future__ import annotations

import datetime
import json
import re

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.email_writing_evidence import (
    DiagnosticFeedbackEvent,
    EmailReviewSession,
    WritingDiagnosticRecord,
)

UTC = datetime.timezone.utc
REVISION_DIGEST = "7c" * 32
PROMPT_HASH = "sha256:" + "ab" * 32
CANDIDATE_HASH = "sha256:" + "cd" * 32
REPLACEMENT_HASH = "sha256:" + "de" * 32
EXPLANATION_HASH = "sha256:" + "ef" * 32
TWO_WORD_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
NEW_MODEL_TYPES = (
    EmailReviewSession,
    WritingDiagnosticRecord,
    DiagnosticFeedbackEvent,
)
FORBIDDEN_CONTENT_NAMES = {
    "source_body",
    "source_email_body",
    "source_text",
    "draft_body",
    "draft_text",
    "replacement_text",
    "explanation_text",
    "prompt_text",
    "raw_output",
    "provider_token",
    "orchestration_trace",
    "complete_trace",
}


def _now() -> datetime.datetime:
    return datetime.datetime(2026, 8, 12, 15, 0, tzinfo=UTC)


def _review_session(**overrides: object) -> EmailReviewSession:
    values: dict[str, object] = {
        "owner_user_id": "user_alpha",
        "owner_organization_id": "organization_alpha",
        "source_email_id": 1,
        "revision_algorithm": "SHA-256",
        "revision_digest": REVISION_DIGEST,
        "revision_entity_tag": f'"sha256-{REVISION_DIGEST}"',
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "review_mode": "deep",
        "language_profile": "ko-KR",
        "review_status": "completed",
        "workflow_identifier": "email_writing_review",
        "workflow_version": "1",
        "model_profile_id": "review_profile_v1",
        "rubric_version": "email_writing_rubric_v1",
        "judge_policy_version": "evaluation_only_v1",
        "orchestration_mode": "conduct",
        "prompt_hash": PROMPT_HASH,
        "latency_bucket_ms": 2_000,
        "cost_bucket_micro_usd": 5_000,
        "prompt_token_bucket": 2_000,
        "completion_token_bucket": 500,
        "created_at": _now(),
        "evidence_expires_at": _now() + datetime.timedelta(days=30),
    }
    values.update(overrides)
    return EmailReviewSession(**values)


def _diagnostic_record(**overrides: object) -> WritingDiagnosticRecord:
    values: dict[str, object] = {
        "diagnostic_identifier": "diagnostic_alpha",
        "diagnostic_category": "clarity",
        "diagnostic_priority": "important",
        "selector_start": 0,
        "selector_end": 5,
        "candidate_hash": CANDIDATE_HASH,
        "replacement_hash": REPLACEMENT_HASH,
        "explanation_hash": EXPLANATION_HASH,
        "criterion_categories_json": ["clarity", "actionability"],
        "judge_score": 0.92,
        "admission_status": "admitted",
        "admission_reason_code": "judge_supported",
        "created_at": _now(),
    }
    values.update(overrides)
    return WritingDiagnosticRecord(**values)


def _feedback_event(**overrides: object) -> DiagnosticFeedbackEvent:
    values: dict[str, object] = {
        "owner_user_id": "user_alpha",
        "owner_organization_id": "organization_alpha",
        "feedback_action": "applied",
        "reviewed_revision_digest": REVISION_DIGEST,
        "resulting_revision_digest": "8d" * 32,
        "conflict_reason_code": None,
        "stale_reason_code": None,
        "event_time": _now() + datetime.timedelta(minutes=1),
        "idempotency_key": "feedback_action_alpha",
    }
    values.update(overrides)
    return DiagnosticFeedbackEvent(**values)


@pytest.fixture
def evidence_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql(
            "CREATE TABLE email_records (id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql("INSERT INTO email_records (id) VALUES (1)")
        for model_type in NEW_MODEL_TYPES:
            model_type.__table__.create(connection)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_new_database_objects_use_named_two_word_snake_case() -> None:
    """Every new table, column, index, constraint, and relationship is explicit."""
    for model_type in NEW_MODEL_TYPES:
        table = model_type.__table__
        assert TWO_WORD_SNAKE_CASE.fullmatch(table.name)
        assert all(TWO_WORD_SNAKE_CASE.fullmatch(column.name) for column in table.columns)
        assert table.constraints
        assert all(
            constraint.name is not None
            and TWO_WORD_SNAKE_CASE.fullmatch(constraint.name)
            for constraint in table.constraints
        )
        assert all(
            index.name is not None and TWO_WORD_SNAKE_CASE.fullmatch(index.name)
            for index in table.indexes
        )
        assert all(
            TWO_WORD_SNAKE_CASE.fullmatch(relationship.key)
            for relationship in model_type.__mapper__.relationships
        )


def test_evidence_schema_contains_no_raw_authored_or_provider_content() -> None:
    """The persistence boundary cannot accidentally accept sensitive plaintext."""
    all_column_names = {
        column.name
        for model_type in NEW_MODEL_TYPES
        for column in model_type.__table__.columns
    }
    assert all_column_names.isdisjoint(FORBIDDEN_CONTENT_NAMES)
    for forbidden_name in FORBIDDEN_CONTENT_NAMES:
        with pytest.raises(TypeError, match=forbidden_name):
            _review_session(**{forbidden_name: "SECRET_AUTHORED_CONTENT"})


def test_review_evidence_round_trip_and_safe_serialization(
    evidence_session: Session,
) -> None:
    """A complete evidence graph round-trips without storing authored content."""
    review_session = _review_session()
    diagnostic_record = _diagnostic_record()
    feedback_event = _feedback_event()
    diagnostic_record.diagnostic_feedback_events.append(feedback_event)
    review_session.writing_diagnostic_records.append(diagnostic_record)
    evidence_session.add(review_session)
    evidence_session.commit()

    loaded = evidence_session.query(EmailReviewSession).one()
    loaded_diagnostic = loaded.writing_diagnostic_records[0]
    loaded_feedback = loaded_diagnostic.diagnostic_feedback_events[0]
    assert loaded.review_session_id
    assert loaded_diagnostic.diagnostic_identifier == "diagnostic_alpha"
    assert loaded_feedback.feedback_action == "applied"

    serialized = json.dumps(
        [
            loaded.to_evidence_dict(),
            loaded_diagnostic.to_evidence_dict(),
            loaded_feedback.to_evidence_dict(),
        ],
        sort_keys=True,
        default=str,
    )
    rendered_log = "\n".join(
        [repr(loaded), repr(loaded_diagnostic), repr(loaded_feedback)]
    )
    for forbidden_value in (
        "SECRET_AUTHORED_CONTENT",
        "full draft body",
        "provider bearer token",
        "complete orchestration trace",
    ):
        assert forbidden_value not in serialized
        assert forbidden_value not in rendered_log
    assert "review_session_id" in serialized
    assert "prompt_hash" in serialized
    assert "source_email_id" in serialized
    assert "candidate_hash" in serialized
    assert "feedback_action" in serialized


def test_review_session_retention_and_owner_indexes_are_queryable(
    evidence_session: Session,
) -> None:
    """Operators can locate expired evidence without reading email content."""
    evidence_session.add(_review_session(review_status="abstained"))
    evidence_session.commit()

    database_inspector = inspect(evidence_session.get_bind())
    index_names = {
        index["name"]
        for index in database_inspector.get_indexes("email_review_session")
    }
    assert "ix_email_review_session_owner_scope" in index_names
    assert "ix_email_review_session_expiry_status" in index_names
    assert "ix_email_review_session_source_email" in index_names


def test_unique_diagnostic_identifier_per_review_session(
    evidence_session: Session,
) -> None:
    """A model response cannot duplicate one opaque diagnostic identifier."""
    review_session = _review_session()
    review_session.writing_diagnostic_records.extend(
        [_diagnostic_record(), _diagnostic_record()]
    )
    evidence_session.add(review_session)

    with pytest.raises(IntegrityError):
        evidence_session.commit()
    evidence_session.rollback()


def test_feedback_idempotency_key_is_unique_within_owner_scope(
    evidence_session: Session,
) -> None:
    """Retries cannot persist the same user action twice."""
    first_review = _review_session()
    first_diagnostic = _diagnostic_record(diagnostic_identifier="diagnostic_one")
    first_diagnostic.diagnostic_feedback_events.append(_feedback_event())
    first_review.writing_diagnostic_records.append(first_diagnostic)
    evidence_session.add(first_review)
    evidence_session.commit()

    second_review = _review_session()
    second_diagnostic = _diagnostic_record(diagnostic_identifier="diagnostic_two")
    second_diagnostic.diagnostic_feedback_events.append(_feedback_event())
    second_review.writing_diagnostic_records.append(second_diagnostic)
    evidence_session.add(second_review)

    with pytest.raises(IntegrityError):
        evidence_session.commit()
    evidence_session.rollback()


@pytest.mark.parametrize(
    ("factory", "overrides"),
    [
        (_review_session, {"review_mode": "keyword_mode"}),
        (_review_session, {"latency_bucket_ms": -1}),
        (_review_session, {"cost_bucket_micro_usd": -1}),
        (
            _review_session,
            {"evidence_expires_at": _now() - datetime.timedelta(seconds=1)},
        ),
        (_diagnostic_record, {"selector_start": -1}),
        (_diagnostic_record, {"selector_end": 0}),
        (_diagnostic_record, {"judge_score": 1.01}),
        (_diagnostic_record, {"admission_status": "automatically_trusted"}),
        (_feedback_event, {"feedback_action": "send_email"}),
        (_feedback_event, {"resulting_revision_digest": None}),
    ],
)
def test_database_checks_reject_invalid_evidence(
    evidence_session: Session,
    factory,
    overrides: dict[str, object],
) -> None:
    """Invalid enum, range, selector, retention, and Apply states fail closed."""
    review_session = _review_session()
    diagnostic_record = _diagnostic_record()
    feedback_event = _feedback_event()

    candidate = factory(**overrides)
    if isinstance(candidate, EmailReviewSession):
        review_session = candidate
    elif isinstance(candidate, WritingDiagnosticRecord):
        diagnostic_record = candidate
    else:
        feedback_event = candidate

    diagnostic_record.diagnostic_feedback_events.append(feedback_event)
    review_session.writing_diagnostic_records.append(diagnostic_record)
    evidence_session.add(review_session)

    with pytest.raises(IntegrityError):
        evidence_session.commit()
    evidence_session.rollback()


def test_deleting_review_session_cascades_minimized_evidence(
    evidence_session: Session,
) -> None:
    """Retention deletion removes dependent hashes and feedback in one operation."""
    review_session = _review_session()
    diagnostic_record = _diagnostic_record()
    diagnostic_record.diagnostic_feedback_events.append(_feedback_event())
    review_session.writing_diagnostic_records.append(diagnostic_record)
    evidence_session.add(review_session)
    evidence_session.commit()

    evidence_session.delete(review_session)
    evidence_session.commit()

    assert evidence_session.query(EmailReviewSession).count() == 0
    assert evidence_session.query(WritingDiagnosticRecord).count() == 0
    assert evidence_session.query(DiagnosticFeedbackEvent).count() == 0
