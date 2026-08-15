"""Normalized persistence model for user-scoped outbound email signatures."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class EmailSignatureProfile(Base):
    """Store one plain-text outbound signature per authenticated mailbox scope."""

    __tablename__ = "email_signature_profiles"

    email_signature_profile_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    organization_id: Mapped[str | None] = mapped_column(
        String,
        index=True,
        nullable=True,
    )
    signature_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
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
    "uq_email_signature_profiles_owner_scope",
    EmailSignatureProfile.user_id,
    func.coalesce(EmailSignatureProfile.organization_id, ""),
    unique=True,
)
