import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class Pop3ObservedMessage(Base):
    """Durable provider progress for one POP3 UIDL within an account.

    POP3 message numbers are session-local positions. ``provider_uidl`` stores
    RFC 1939 provider identity so bounded polling can make progress across
    reconnects and renumbering. ``collection_disposition`` distinguishes
    successfully observed messages from retryable collection failures; neither
    state redefines Naruon's Message-ID or source-fingerprint identity.
    """

    __tablename__ = "pop3_observed_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_config_id",
            "provider_uidl",
            name="uq_pop3_observed_messages_account_uidl",
        ),
        Index(
            "ix_pop3_observed_messages_account_observed",
            "tenant_config_id",
            "observed_at",
        ),
        Index(
            "ix_pop3_observed_messages_account_retry",
            "tenant_config_id",
            "collection_disposition",
            "retry_after",
        ),
    )

    observed_message_id: Mapped[int] = mapped_column(primary_key=True)
    tenant_config_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_uidl: Mapped[str] = mapped_column(String(70), nullable=False)
    collection_disposition: Mapped[str] = mapped_column(
        String(16),
        default="observed",
        nullable=False,
    )
    retry_after: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    observed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=True,
    )
