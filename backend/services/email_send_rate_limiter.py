"""Shared, fail-closed email send throttling."""

from __future__ import annotations

import datetime
import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sqlalchemy import bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SecurityAuditEvent
from db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from api.auth import AuthContext

logger = logging.getLogger(__name__)

SEND_RATE_LIMIT_MAX_ATTEMPTS = 10
SEND_RATE_LIMIT_WINDOW_SECONDS = 60
SEND_RATE_LIMIT_NAMESPACE = "naruon-email-send-rate-limit"


class EmailSendRateLimitUnavailable(RuntimeError):
    """The shared rate-limit state cannot provide a trustworthy decision."""


@dataclass(frozen=True)
class EmailSendRateLimitDecision:
    """A non-sensitive rate-limit decision returned to the send endpoint."""

    allowed: bool
    reason: Literal["allowed", "quota_exhausted"]


def rate_limit_scope_hash(user_id: str, organization_id: str | None) -> str:
    """Return a non-reversible identifier for one authorized send scope."""
    organization_scope = organization_id or "<personal>"
    value = f"{SEND_RATE_LIMIT_NAMESPACE}\0{organization_scope}\0{user_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _lock_key(scope_hash: str) -> int:
    return int.from_bytes(bytes.fromhex(scope_hash[:16]), byteorder="big", signed=True)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _session_uses_postgresql(session: AsyncSession) -> bool:
    try:
        bind = session.get_bind()
    except Exception:
        return False
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


def _audit_event(
    auth_context: AuthContext,
    *,
    scope_hash: str,
    decision: EmailSendRateLimitDecision,
    observed_at: datetime.datetime,
) -> SecurityAuditEvent:
    return SecurityAuditEvent(
        actor_user_id=auth_context.user_id,
        actor_role=auth_context.role,
        organization_id=auth_context.organization_id,
        workspace_id=auth_context.workspace_id,
        event_action=f"email_send_rate_limit.{decision.reason}",
        resource_type="email_send_rate_limit",
        resource_uid=f"email_send_scope:{scope_hash}",
        evidence_source="services.email_send_rate_limiter",
        observed_at=observed_at,
        detail_text=(
            f"decision={decision.reason};"
            f"window_seconds={SEND_RATE_LIMIT_WINDOW_SECONDS};"
            f"max_attempts={SEND_RATE_LIMIT_MAX_ATTEMPTS}"
        ),
    )


async def enforce_send_email_rate_limit(
    auth_context: AuthContext,
    *,
    now: datetime.datetime | None = None,
) -> EmailSendRateLimitDecision:
    """Atomically reserve one send attempt in a rolling PostgreSQL window.

    A limiter-owned transaction prevents committing unrelated request work.
    PostgreSQL advisory locking serializes the count-and-record decision across
    workers; existing audit rows provide the exact rolling-window history.
    """
    observed_at = now or _utc_now()
    scope_hash = rate_limit_scope_hash(
        auth_context.user_id, auth_context.organization_id
    )
    async with AsyncSessionLocal() as session:
        if not _session_uses_postgresql(session):
            raise EmailSendRateLimitUnavailable
        try:
            await session.connection(
                execution_options={"isolation_level": "READ COMMITTED"}
            )
            await session.execute(
                select(func.pg_advisory_xact_lock(bindparam("lock_key"))),
                {"lock_key": _lock_key(scope_hash)},
            )
            window_started_at = observed_at - datetime.timedelta(
                seconds=SEND_RATE_LIMIT_WINDOW_SECONDS
            )
            result = await session.execute(
                select(func.count())
                .select_from(SecurityAuditEvent)
                .where(
                    SecurityAuditEvent.resource_uid
                    == f"email_send_scope:{scope_hash}",
                    SecurityAuditEvent.event_action
                    == "email_send_rate_limit.allowed",
                    SecurityAuditEvent.observed_at > window_started_at,
                )
            )
            allowed = result.scalar_one() < SEND_RATE_LIMIT_MAX_ATTEMPTS
            decision = EmailSendRateLimitDecision(
                allowed=allowed,
                reason="allowed" if allowed else "quota_exhausted",
            )
            record_decision = allowed
            if not allowed:
                denied_result = await session.execute(
                    select(func.count())
                    .select_from(SecurityAuditEvent)
                    .where(
                        SecurityAuditEvent.resource_uid
                        == f"email_send_scope:{scope_hash}",
                        SecurityAuditEvent.event_action
                        == "email_send_rate_limit.quota_exhausted",
                        SecurityAuditEvent.observed_at > window_started_at,
                    )
                )
                record_decision = denied_result.scalar_one() == 0
            if record_decision:
                session.add(
                    _audit_event(
                        auth_context,
                        scope_hash=scope_hash,
                        decision=decision,
                        observed_at=observed_at,
                    )
                )
            await session.commit()
            return decision
        except Exception as exc:
            try:
                await session.rollback()
            except Exception as rollback_exc:
                logger.warning(
                    "Email send rate limiter rollback failed; error_type=%s",
                    type(rollback_exc).__name__,
                )
            logger.warning(
                "Email send rate limiter decision unavailable; "
                "event_action=email_send_rate_limit.unavailable error_type=%s",
                type(exc).__name__,
            )
            raise EmailSendRateLimitUnavailable from exc
