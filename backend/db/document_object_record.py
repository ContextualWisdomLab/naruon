"""Normalized ORM metadata for raw workspace-document object storage."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models import Base

if TYPE_CHECKING:  # pragma: no cover - typing only
    from db.models import Document
    from db.object_storage_provider import ObjectStorageProvider


class DocumentObjectRecord(Base):
    """Integrity-bearing locator for one raw workspace document stored in S3.

    The owning ``workspace_documents`` row remains authoritative for tenant
    scope and workflow state. This table contains only the provider reference,
    opaque object locator, integrity metadata, and lifecycle timestamps; raw
    payload bytes never enter this row.
    """

    __tablename__ = "document_object_records"
    __table_args__ = (
        CheckConstraint(
            "storage_backend = 's3'",
            name="ck_document_object_records_backend",
        ),
        CheckConstraint(
            "storage_state IN ('active', 'consumed', 'deleted')",
            name="ck_document_object_records_state",
        ),
        CheckConstraint(
            "content_length >= 0",
            name="ck_document_object_records_content_length",
        ),
        CheckConstraint(
            "bucket_name IS NOT NULL AND object_key IS NOT NULL "
            "AND inline_payload IS NULL",
            name="ck_document_object_records_s3_locator",
        ),
        CheckConstraint(
            "(storage_state = 'active' AND consumed_at IS NULL "
            "AND deleted_at IS NULL) OR "
            "(storage_state = 'consumed' AND consumed_at IS NOT NULL "
            "AND deleted_at IS NULL) OR "
            "(storage_state = 'deleted' AND consumed_at IS NOT NULL "
            "AND deleted_at IS NOT NULL)",
            name="ck_document_object_records_lifecycle",
        ),
        UniqueConstraint(
            "document_id",
            name="uq_document_object_records_document",
        ),
        UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_document_object_records_locator",
        ),
        Index(
            "ix_document_object_records_state",
            "storage_backend",
            "storage_state",
        ),
        Index(
            "ix_document_object_records_checksum",
            "checksum_sha256",
        ),
        Index(
            "ix_document_object_records_provider",
            "object_storage_provider_id",
        ),
    )

    document_object_record_id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("workspace_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    object_storage_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "object_storage_providers.object_storage_provider_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    document: Mapped["Document"] = relationship("Document")
    object_storage_provider: Mapped["ObjectStorageProvider | None"] = relationship(
        "ObjectStorageProvider"
    )
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    inline_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    content_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_state: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )
    consumed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
