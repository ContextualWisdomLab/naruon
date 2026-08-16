"""Encrypted organization-scoped object-storage provider configuration."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base, EncryptedString


class ObjectStorageProvider(Base):
    """Store one organization-owned S3-compatible provider revision.

    PostgreSQL holds immutable storage-topology metadata and Fernet-encrypted
    credentials. The process environment selects only the broad storage mode and
    trusted custom endpoint hosts; runtime object requests resolve the active
    organization row through a signed, scoped database session. A provider row
    is a retained revision: create a new row to change bucket, region, endpoint,
    addressing, encryption, KMS key, or expected bucket owner.
    """

    __tablename__ = "object_storage_providers"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider_name",
            name="uq_object_storage_providers_org_name",
        ),
        Index(
            "ix_object_storage_providers_org_active",
            "organization_id",
            "is_active",
            "updated_at",
        ),
    )

    object_storage_provider_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    organization_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String,
        default="s3",
        nullable=False,
    )
    bucket_name: Mapped[str] = mapped_column(String, nullable=False)
    region_name: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String, nullable=True)
    addressing_style: Mapped[str] = mapped_column(
        String,
        default="virtual",
        nullable=False,
    )
    access_key_id: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    secret_access_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    session_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    server_side_encryption: Mapped[str] = mapped_column(
        String,
        default="AES256",
        nullable=False,
    )
    kms_key_id: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    expected_bucket_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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


Index(
    "uq_object_storage_providers_active_org",
    ObjectStorageProvider.organization_id,
    unique=True,
    postgresql_where=ObjectStorageProvider.is_active.is_(True),
)
