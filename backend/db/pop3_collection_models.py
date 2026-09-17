import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class Pop3ObservedMessage(Base):
    """Durable provider identity for one POP3 message observed by an account.

    POP3 message numbers are session-local positions. ``provider_uidl`` stores
    the RFC 1939 unique-id instead so bounded polling can make progress across
    reconnects and message-number renumbering without redefining Naruon's email
    Message-ID or source-fingerprint identity.
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
    )

    observed_message_id: Mapped[int] = mapped_column(primary_key=True)
    tenant_config_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_uidl: Mapped[str] = mapped_column(String(70), nullable=False)
    observed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
