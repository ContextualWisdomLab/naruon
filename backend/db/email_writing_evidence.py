"""Privacy-minimized persistence models for LLM email-writing review evidence.

The tables in this module deliberately retain only ownership, immutable revision
identifiers, bounded operational buckets, diagnostic hashes, admission outcomes,
and idempotent user feedback. They never persist source mail bodies, authored
drafts, replacement or explanation text, prompts, model output, provider tokens,
or orchestration traces.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models import Base, Email


def _utc_now() -> datetime.datetime:
    """Return a timezone-aware UTC timestamp for persisted evidence events."""
    return datetime.datetime.now(datetime.timezone.utc)


def _new_uuid() -> str:
    """Return a transport-neutral UUID string supported by SQLite and PostgreSQL."""
    return str(uuid.uuid4())


class EmailReviewSession(Base):
    """One tenant-scoped review of an immutable email-draft revision."""

    __tablename__ = "email_review_session"
    __table_args__ = (
        PrimaryKeyConstraint(
            "review_session_id",
            name="pk_email_review_session",
        ),
        ForeignKeyConstraint(
            ["source_email_id"],
            ["email_records.id"],
            name="fk_email_review_session_source_email",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "revision_algorithm = 'SHA-256'",
            name="ck_email_review_session_revision_algorithm",
        ),
        CheckConstraint(
            "length(revision_digest) = 64",
            name="ck_email_review_session_revision_digest",
        ),
        CheckConstraint(
            "length(revision_entity_tag) >= 73",
            name="ck_email_review_session_revision_entity_tag",
        ),
        CheckConstraint(
            "projection_version > 0",
            name="ck_email_review_session_projection_version",
        ),
        CheckConstraint(
            "review_mode IN ('incremental', 'deep')",
            name="ck_email_review_session_review_mode",
        ),
        CheckConstraint(
            "review_status IN ("
            "'pending', 'completed', 'abstained', 'unavailable', 'stale', "
            "'rejected', 'context_insufficient', 'judge_disagreement'"
            ")",
            name="ck_email_review_session_review_status",
        ),
        CheckConstraint(
            "orchestration_mode IN ('route', 'conduct')",
            name="ck_email_review_session_orchestration_mode",
        ),
        CheckConstraint(
            "prompt_hash LIKE 'sha256:%' AND length(prompt_hash) = 71",
            name="ck_email_review_session_prompt_hash",
        ),
        CheckConstraint(
            "latency_bucket_ms >= 0 AND cost_bucket_micro_usd >= 0 "
            "AND prompt_token_bucket >= 0 AND completion_token_bucket >= 0",
            name="ck_email_review_session_nonnegative_buckets",
        ),
        CheckConstraint(
            "evidence_expires_at > created_at",
            name="ck_email_review_session_retention_window",
        ),
        Index(
            "ix_email_review_session_owner_scope",
            "owner_user_id",
            "owner_organization_id",
            "created_at",
        ),
        Index(
            "ix_email_review_session_expiry_status",
            "evidence_expires_at",
            "review_status",
        ),
        Index(
            "ix_email_review_session_source_email",
            "source_email_id",
        ),
    )

    review_session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        nullable=False,
    )
    owner_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_organization_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_email_id: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_entity_tag: Mapped[str] = mapped_column(String(96), nullable=False)
    projection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    language_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(128), nullable=False)
    model_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(128), nullable=False)
    judge_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    orchestration_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    latency_bucket_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_bucket_micro_usd: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_token_bucket: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_token_bucket: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    evidence_expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_email_record: Mapped[Email] = relationship(
        Email,
        passive_deletes=True,
    )
    writing_diagnostic_records: Mapped[list[WritingDiagnosticRecord]] = relationship(
        "WritingDiagnosticRecord",
        back_populates="review_session_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_evidence_dict(self) -> dict[str, Any]:
        """Serialize only privacy-minimized operational evidence."""
        return {
            "review_session_id": self.review_session_id,
            "revision_algorithm": self.revision_algorithm,
            "revision_digest": self.revision_digest,
            "revision_entity_tag": self.revision_entity_tag,
            "projection_name": self.projection_name,
            "projection_version": self.projection_version,
            "review_mode": self.review_mode,
            "language_profile": self.language_profile,
            "review_status": self.review_status,
            "workflow_identifier": self.workflow_identifier,
            "workflow_version": self.workflow_version,
            "model_profile_id": self.model_profile_id,
            "rubric_version": self.rubric_version,
            "judge_policy_version": self.judge_policy_version,
            "orchestration_mode": self.orchestration_mode,
            "prompt_hash": self.prompt_hash,
            "latency_bucket_ms": self.latency_bucket_ms,
            "cost_bucket_micro_usd": self.cost_bucket_micro_usd,
            "prompt_token_bucket": self.prompt_token_bucket,
            "completion_token_bucket": self.completion_token_bucket,
            "created_at": self.created_at,
            "evidence_expires_at": self.evidence_expires_at,
        }

    def __repr__(self) -> str:
        """Return a log-safe representation containing no authored content."""
        return (
            "EmailReviewSession("
            f"review_session_id={self.review_session_id!r}, "
            f"review_status={self.review_status!r})"
        )


class WritingDiagnosticRecord(Base):
    """Hash-only evidence for one candidate diagnostic and Judge decision."""

    __tablename__ = "writing_diagnostic_record"
    __table_args__ = (
        PrimaryKeyConstraint(
            "diagnostic_record_id",
            name="pk_writing_diagnostic_record",
        ),
        ForeignKeyConstraint(
            ["review_session_id"],
            ["email_review_session.review_session_id"],
            name="fk_writing_diagnostic_record_review_session",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "review_session_id",
            "diagnostic_identifier",
            name="uq_writing_diagnostic_record_session_identifier",
        ),
        CheckConstraint(
            "selector_start >= 0 AND selector_end > selector_start",
            name="ck_writing_diagnostic_record_selector_order",
        ),
        CheckConstraint(
            "diagnostic_priority IN ('critical', 'important', 'advisory')",
            name="ck_writing_diagnostic_record_priority_code",
        ),
        CheckConstraint(
            "judge_score >= 0 AND judge_score <= 1",
            name="ck_writing_diagnostic_record_judge_score",
        ),
        CheckConstraint(
            "admission_status IN ('admitted', 'rejected', 'abstained')",
            name="ck_writing_diagnostic_record_admission_status",
        ),
        CheckConstraint(
            "candidate_hash LIKE 'sha256:%' AND length(candidate_hash) = 71 "
            "AND explanation_hash LIKE 'sha256:%' "
            "AND length(explanation_hash) = 71 "
            "AND (replacement_hash IS NULL OR ("
            "replacement_hash LIKE 'sha256:%' "
            "AND length(replacement_hash) = 71))",
            name="ck_writing_diagnostic_record_hash_shapes",
        ),
        Index(
            "ix_writing_diagnostic_record_session_status",
            "review_session_id",
            "admission_status",
        ),
    )

    diagnostic_record_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        nullable=False,
    )
    review_session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    diagnostic_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    diagnostic_category: Mapped[str] = mapped_column(String(128), nullable=False)
    diagnostic_priority: Mapped[str] = mapped_column(String(32), nullable=False)
    selector_start: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_end: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    replacement_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    explanation_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    criterion_categories_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    judge_score: Mapped[float] = mapped_column(Float, nullable=False)
    admission_status: Mapped[str] = mapped_column(String(32), nullable=False)
    admission_reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    review_session_record: Mapped[EmailReviewSession] = relationship(
        EmailReviewSession,
        back_populates="writing_diagnostic_records",
    )
    diagnostic_feedback_events: Mapped[list[DiagnosticFeedbackEvent]] = relationship(
        "DiagnosticFeedbackEvent",
        back_populates="diagnostic_record_entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_evidence_dict(self) -> dict[str, Any]:
        """Serialize hashes, selectors, categories, and admission evidence only."""
        return {
            "diagnostic_record_id": self.diagnostic_record_id,
            "review_session_id": self.review_session_id,
            "diagnostic_identifier": self.diagnostic_identifier,
            "diagnostic_category": self.diagnostic_category,
            "diagnostic_priority": self.diagnostic_priority,
            "selector_start": self.selector_start,
            "selector_end": self.selector_end,
            "candidate_hash": self.candidate_hash,
            "replacement_hash": self.replacement_hash,
            "explanation_hash": self.explanation_hash,
            "criterion_categories_json": self.criterion_categories_json,
            "judge_score": self.judge_score,
            "admission_status": self.admission_status,
            "admission_reason_code": self.admission_reason_code,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        """Return a log-safe representation containing only opaque identifiers."""
        return (
            "WritingDiagnosticRecord("
            f"diagnostic_record_id={self.diagnostic_record_id!r}, "
            f"diagnostic_identifier={self.diagnostic_identifier!r}, "
            f"admission_status={self.admission_status!r})"
        )


class DiagnosticFeedbackEvent(Base):
    """Idempotent user feedback linked to one admitted diagnostic record."""

    __tablename__ = "diagnostic_feedback_event"
    __table_args__ = (
        PrimaryKeyConstraint(
            "feedback_event_id",
            name="pk_diagnostic_feedback_event",
        ),
        ForeignKeyConstraint(
            ["diagnostic_record_id"],
            ["writing_diagnostic_record.diagnostic_record_id"],
            name="fk_diagnostic_feedback_event_diagnostic_record",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "owner_user_id",
            "owner_organization_id",
            "idempotency_key",
            name="uq_diagnostic_feedback_event_owner_idempotency",
        ),
        CheckConstraint(
            "feedback_action IN ("
            "'applied', 'ignored', 'dismissed', 'explanation_requested'"
            ")",
            name="ck_diagnostic_feedback_event_action_code",
        ),
        CheckConstraint(
            "feedback_action != 'applied' OR resulting_revision_digest IS NOT NULL",
            name="ck_diagnostic_feedback_event_apply_revision",
        ),
        CheckConstraint(
            "length(reviewed_revision_digest) = 64 "
            "AND (resulting_revision_digest IS NULL "
            "OR length(resulting_revision_digest) = 64)",
            name="ck_diagnostic_feedback_event_revision_digests",
        ),
        CheckConstraint(
            "length(idempotency_key) > 0",
            name="ck_diagnostic_feedback_event_idempotency_key",
        ),
        Index(
            "ix_diagnostic_feedback_event_owner_scope",
            "owner_user_id",
            "owner_organization_id",
            "event_time",
        ),
        Index(
            "ix_diagnostic_feedback_event_diagnostic_record",
            "diagnostic_record_id",
            "event_time",
        ),
    )

    feedback_event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        nullable=False,
    )
    diagnostic_record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_organization_id: Mapped[str] = mapped_column(String(255), nullable=False)
    feedback_action: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    resulting_revision_digest: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    conflict_reason_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    stale_reason_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

    diagnostic_record_entry: Mapped[WritingDiagnosticRecord] = relationship(
        WritingDiagnosticRecord,
        back_populates="diagnostic_feedback_events",
    )

    def to_evidence_dict(self) -> dict[str, Any]:
        """Serialize action, revision, and conflict codes without authored text."""
        return {
            "feedback_event_id": self.feedback_event_id,
            "diagnostic_record_id": self.diagnostic_record_id,
            "feedback_action": self.feedback_action,
            "reviewed_revision_digest": self.reviewed_revision_digest,
            "resulting_revision_digest": self.resulting_revision_digest,
            "conflict_reason_code": self.conflict_reason_code,
            "stale_reason_code": self.stale_reason_code,
            "event_time": self.event_time,
            "idempotency_key": self.idempotency_key,
        }

    def __repr__(self) -> str:
        """Return a log-safe representation containing no replacement content."""
        return (
            "DiagnosticFeedbackEvent("
            f"feedback_event_id={self.feedback_event_id!r}, "
            f"feedback_action={self.feedback_action!r})"
        )
