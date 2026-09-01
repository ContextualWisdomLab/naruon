"""Add privacy-minimized email-writing review evidence tables.

Revision ID: 20260812_email_writing_evidence
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-12 15:05:00.000000

The revision stores ownership, immutable revision identifiers, bounded runtime
buckets, diagnostic hashes, Judge outcomes, and idempotent feedback codes. It
deliberately excludes authored mail or draft content, model payloads, credentials,
and complete execution traces.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260812_email_writing_evidence"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_SESSION_TABLE = "email_review_session"
_DIAGNOSTIC_TABLE = "writing_diagnostic_record"
_FEEDBACK_TABLE = "diagnostic_feedback_event"
_NEW_TABLE_NAMES = (_SESSION_TABLE, _DIAGNOSTIC_TABLE, _FEEDBACK_TABLE)


def _review_evidence_metadata() -> sa.MetaData:
    """Build dialect-neutral table metadata for SQLite and PostgreSQL."""
    metadata = sa.MetaData()
    sa.Table(
        "email_records",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    review_session = sa.Table(
        _SESSION_TABLE,
        metadata,
        sa.Column("review_session_id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=False),
        sa.Column("owner_organization_id", sa.String(length=255), nullable=False),
        sa.Column("source_email_id", sa.Integer(), nullable=False),
        sa.Column("revision_algorithm", sa.String(length=16), nullable=False),
        sa.Column("revision_digest", sa.String(length=64), nullable=False),
        sa.Column("revision_entity_tag", sa.String(length=96), nullable=False),
        sa.Column("projection_name", sa.String(length=128), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("review_mode", sa.String(length=32), nullable=False),
        sa.Column("language_profile", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("workflow_identifier", sa.String(length=128), nullable=False),
        sa.Column("workflow_version", sa.String(length=128), nullable=False),
        sa.Column("model_profile_id", sa.String(length=128), nullable=False),
        sa.Column("rubric_version", sa.String(length=128), nullable=False),
        sa.Column("judge_policy_version", sa.String(length=128), nullable=False),
        sa.Column("orchestration_mode", sa.String(length=32), nullable=False),
        sa.Column("prompt_hash", sa.String(length=71), nullable=False),
        sa.Column("latency_bucket_ms", sa.Integer(), nullable=False),
        sa.Column("cost_bucket_micro_usd", sa.Integer(), nullable=False),
        sa.Column("prompt_token_bucket", sa.Integer(), nullable=False),
        sa.Column("completion_token_bucket", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "review_session_id",
            name="pk_email_review_session",
        ),
        sa.ForeignKeyConstraint(
            ["source_email_id"],
            ["email_records.id"],
            name="fk_email_review_session_source_email",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "revision_algorithm = 'SHA-256'",
            name="ck_email_review_session_revision_algorithm",
        ),
        sa.CheckConstraint(
            "length(revision_digest) = 64",
            name="ck_email_review_session_revision_digest",
        ),
        sa.CheckConstraint(
            "length(revision_entity_tag) >= 73",
            name="ck_email_review_session_revision_entity_tag",
        ),
        sa.CheckConstraint(
            "projection_version > 0",
            name="ck_email_review_session_projection_version",
        ),
        sa.CheckConstraint(
            "review_mode IN ('incremental', 'deep')",
            name="ck_email_review_session_review_mode",
        ),
        sa.CheckConstraint(
            "review_status IN ("
            "'pending', 'completed', 'abstained', 'unavailable', 'stale', "
            "'rejected', 'context_insufficient', 'judge_disagreement'"
            ")",
            name="ck_email_review_session_review_status",
        ),
        sa.CheckConstraint(
            "orchestration_mode IN ('route', 'conduct')",
            name="ck_email_review_session_orchestration_mode",
        ),
        sa.CheckConstraint(
            "prompt_hash LIKE 'sha256:%' AND length(prompt_hash) = 71",
            name="ck_email_review_session_prompt_hash",
        ),
        sa.CheckConstraint(
            "latency_bucket_ms >= 0 AND cost_bucket_micro_usd >= 0 "
            "AND prompt_token_bucket >= 0 AND completion_token_bucket >= 0",
            name="ck_email_review_session_nonnegative_buckets",
        ),
        sa.CheckConstraint(
            "evidence_expires_at > created_at",
            name="ck_email_review_session_retention_window",
        ),
    )
    sa.Index(
        "ix_email_review_session_owner_scope",
        review_session.c.owner_user_id,
        review_session.c.owner_organization_id,
        review_session.c.created_at,
    )
    sa.Index(
        "ix_email_review_session_expiry_status",
        review_session.c.evidence_expires_at,
        review_session.c.review_status,
    )
    sa.Index(
        "ix_email_review_session_source_email",
        review_session.c.source_email_id,
    )

    diagnostic_record = sa.Table(
        _DIAGNOSTIC_TABLE,
        metadata,
        sa.Column("diagnostic_record_id", sa.String(length=36), nullable=False),
        sa.Column("review_session_id", sa.String(length=36), nullable=False),
        sa.Column("diagnostic_identifier", sa.String(length=128), nullable=False),
        sa.Column("diagnostic_category", sa.String(length=128), nullable=False),
        sa.Column("diagnostic_priority", sa.String(length=32), nullable=False),
        sa.Column("selector_start", sa.Integer(), nullable=False),
        sa.Column("selector_end", sa.Integer(), nullable=False),
        sa.Column("candidate_hash", sa.String(length=71), nullable=False),
        sa.Column("replacement_hash", sa.String(length=71), nullable=True),
        sa.Column("explanation_hash", sa.String(length=71), nullable=False),
        sa.Column("criterion_categories_json", sa.JSON(), nullable=False),
        sa.Column("judge_score", sa.Float(), nullable=False),
        sa.Column("admission_status", sa.String(length=32), nullable=False),
        sa.Column("admission_reason_code", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "diagnostic_record_id",
            name="pk_writing_diagnostic_record",
        ),
        sa.ForeignKeyConstraint(
            ["review_session_id"],
            ["email_review_session.review_session_id"],
            name="fk_writing_diagnostic_record_review_session",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "review_session_id",
            "diagnostic_identifier",
            name="uq_writing_diagnostic_record_session_identifier",
        ),
        sa.CheckConstraint(
            "selector_start >= 0 AND selector_end > selector_start",
            name="ck_writing_diagnostic_record_selector_order",
        ),
        sa.CheckConstraint(
            "diagnostic_priority IN ('critical', 'important', 'advisory')",
            name="ck_writing_diagnostic_record_priority_code",
        ),
        sa.CheckConstraint(
            "judge_score >= 0 AND judge_score <= 1",
            name="ck_writing_diagnostic_record_judge_score",
        ),
        sa.CheckConstraint(
            "admission_status IN ('admitted', 'rejected', 'abstained')",
            name="ck_writing_diagnostic_record_admission_status",
        ),
        sa.CheckConstraint(
            "candidate_hash LIKE 'sha256:%' AND length(candidate_hash) = 71 "
            "AND explanation_hash LIKE 'sha256:%' "
            "AND length(explanation_hash) = 71 "
            "AND (replacement_hash IS NULL OR ("
            "replacement_hash LIKE 'sha256:%' "
            "AND length(replacement_hash) = 71))",
            name="ck_writing_diagnostic_record_hash_shapes",
        ),
    )
    sa.Index(
        "ix_writing_diagnostic_record_session_status",
        diagnostic_record.c.review_session_id,
        diagnostic_record.c.admission_status,
    )

    feedback_event = sa.Table(
        _FEEDBACK_TABLE,
        metadata,
        sa.Column("feedback_event_id", sa.String(length=36), nullable=False),
        sa.Column("diagnostic_record_id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=False),
        sa.Column("owner_organization_id", sa.String(length=255), nullable=False),
        sa.Column("feedback_action", sa.String(length=32), nullable=False),
        sa.Column("reviewed_revision_digest", sa.String(length=64), nullable=False),
        sa.Column("resulting_revision_digest", sa.String(length=64), nullable=True),
        sa.Column("conflict_reason_code", sa.String(length=128), nullable=True),
        sa.Column("stale_reason_code", sa.String(length=128), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint(
            "feedback_event_id",
            name="pk_diagnostic_feedback_event",
        ),
        sa.ForeignKeyConstraint(
            ["diagnostic_record_id"],
            ["writing_diagnostic_record.diagnostic_record_id"],
            name="fk_diagnostic_feedback_event_diagnostic_record",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "owner_organization_id",
            "idempotency_key",
            name="uq_diagnostic_feedback_event_owner_idempotency",
        ),
        sa.CheckConstraint(
            "feedback_action IN ("
            "'applied', 'ignored', 'dismissed', 'explanation_requested'"
            ")",
            name="ck_diagnostic_feedback_event_action_code",
        ),
        sa.CheckConstraint(
            "feedback_action != 'applied' OR resulting_revision_digest IS NOT NULL",
            name="ck_diagnostic_feedback_event_apply_revision",
        ),
        sa.CheckConstraint(
            "length(reviewed_revision_digest) = 64 "
            "AND (resulting_revision_digest IS NULL "
            "OR length(resulting_revision_digest) = 64)",
            name="ck_diagnostic_feedback_event_revision_digests",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) > 0",
            name="ck_diagnostic_feedback_event_idempotency_key",
        ),
    )
    sa.Index(
        "ix_diagnostic_feedback_event_owner_scope",
        feedback_event.c.owner_user_id,
        feedback_event.c.owner_organization_id,
        feedback_event.c.event_time,
    )
    sa.Index(
        "ix_diagnostic_feedback_event_diagnostic_record",
        feedback_event.c.diagnostic_record_id,
        feedback_event.c.event_time,
    )
    return metadata


def upgrade() -> None:
    """Create the evidence tables and indexes without touching raw mail data."""
    connection = op.get_bind()
    metadata = _review_evidence_metadata()
    for table_name in _NEW_TABLE_NAMES:
        metadata.tables[table_name].create(connection, checkfirst=True)


def downgrade() -> None:
    """Drop only this revision's evidence objects in dependency-safe order."""
    connection = op.get_bind()
    metadata = _review_evidence_metadata()
    for table_name in reversed(_NEW_TABLE_NAMES):
        metadata.tables[table_name].drop(connection, checkfirst=True)
