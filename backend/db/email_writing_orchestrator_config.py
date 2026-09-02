"""Tenant-scoped persistence for Naruon's email-writing orchestrator route.

This module keeps the inference credential encrypted at rest and exposes only a
privacy-minimized evidence surface. It deliberately reuses the repository's
canonical SQLAlchemy metadata so Alembic and the application retain one schema
registry while the email-writing aggregate remains independently testable.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base, EncryptedString


class EmailWritingOrchestratorConfig(Base):
    """One owner-scoped contextual-orchestrator configuration record."""

    __tablename__ = "email_writing_orchestrator_config"

    orchestrator_config_id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    organization_id: Mapped[str | None] = mapped_column(
        String,
        index=True,
        nullable=True,
    )
    orchestrator_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    orchestrator_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    model_profile_id: Mapped[str | None] = mapped_column(String, nullable=True)
    inference_credential: Mapped[str | None] = mapped_column(
        EncryptedString,
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

    def to_evidence_dict(self) -> dict[str, object]:
        """Return log-safe configuration evidence without the credential value."""
        return {
            "orchestrator_config_id": self.orchestrator_config_id,
            "owner_user_id": self.owner_user_id,
            "organization_id": self.organization_id,
            "orchestrator_enabled": self.orchestrator_enabled,
            "orchestrator_base_url": self.orchestrator_base_url,
            "model_profile_id": self.model_profile_id,
            "has_inference_credential": self.inference_credential is not None,
        }

    def __repr__(self) -> str:
        """Return a secret-free diagnostic representation."""
        return (
            "<EmailWritingOrchestratorConfig("
            f"orchestrator_config_id={self.orchestrator_config_id}, "
            f"owner_user_id={self.owner_user_id!r}, "
            f"organization_id={self.organization_id!r}, "
            f"orchestrator_enabled={self.orchestrator_enabled}, "
            f"orchestrator_base_url={self.orchestrator_base_url!r}, "
            f"model_profile_id={self.model_profile_id!r}, "
            f"has_inference_credential={self.inference_credential is not None})>"
        )


Index(
    "uq_email_writing_orchestrator_config_owner_scope",
    EmailWritingOrchestratorConfig.owner_user_id,
    func.coalesce(EmailWritingOrchestratorConfig.organization_id, ""),
    unique=True,
)
