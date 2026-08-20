"""Durable retry records for S3 objects left after failed compensation."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models import Base


class ObjectStorageCleanupRecord(Base):
    """Persist one provider-bound orphan object that must be deleted safely."""

    __tablename__ = "object_storage_cleanup_records"
    __table_args__ = (
        CheckConstraint(
            "content_length >= 0",
            name="ck_object_storage_cleanup_records_content_length",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_object_storage_cleanup_records_attempt_count",
        ),
        CheckConstraint(
            "cleanup_status IN ('pending', 'completed', 'cancelled')",
            name="ck_object_storage_cleanup_records_status",
        ),
        UniqueConstraint(
            "object_storage_provider_id",
            "bucket_name",
            "object_key",
            name="uq_object_storage_cleanup_records_locator",
        ),
        Index(
            "ix_object_storage_cleanup_records_status_due",
            "cleanup_status",
            "next_attempt_at",
            "created_at",
        ),
    )

    object_storage_cleanup_record_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    object_storage_provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "object_storage_providers.object_storage_provider_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    bucket_name: Mapped[str] = mapped_column(String, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    content_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    cleanup_reason: Mapped[str] = mapped_column(String, nullable=False)
    cleanup_status: Mapped[str] = mapped_column(
        String,
        default="pending",
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=True,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    object_storage_provider = relationship(
        "ObjectStorageProvider",
        back_populates="cleanup_records",
    )
