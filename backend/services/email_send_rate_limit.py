"""Shared atomic rate limit for ``POST /api/emails/send``.

The previous process-local dictionary plus ``Lock`` gave each API worker its
own 10-per-60-second bucket. This module keeps one authoritative decision per
authorized ``(organization_id, owner_user_id)`` scope so concurrent requests
and horizontally scaled replicas cannot oversubscribe the window.

Limiter state stores only scope identifiers, attempt counts, and timestamps.
It never receives message bodies, recipients, subjects, or credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Protocol
from uuid import uuid4

from sqlalchemy import case, literal
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

from db.models import EmailSendLimitWindow

DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS = 10
DEFAULT_EMAIL_SEND_LIMIT_WINDOW_SECONDS = 60.0

_DECISION_ALLOWED = "allowed"
_DECISION_BLOCKED = "blocked"
_DECISION_UNAVAILABLE = "unavailable"


class EmailSendLimitStoreUnavailable(RuntimeError):
    """Raised when the shared limiter cannot make a trustworthy decision."""


@dataclass(frozen=True)
class EmailSendLimitWindowState:
    """Current persisted window for one authorized send scope."""

    organization_id: str
    owner_user_id: str
    window_started_at: datetime
    attempt_count: int


@dataclass(frozen=True)
class EmailSendLimitDecision:
    """Auditable, non-sensitive outcome of one reservation attempt."""

    decision_code: str
    error_code: str
    http_status_code: int
    user_message: str
    organization_scope: str
    owner_user_id: str
    attempt_count: int
    window_started_at: datetime | None


class EmailSendLimitStore(Protocol):
    """Durable or test-double store that atomically reserves one send slot."""

    async def reserve_attempt(
        self,
        *,
        organization_id: str | None,
        owner_user_id: str,
        observed_at: datetime,
        max_attempts: int,
        window_seconds: float,
    ) -> EmailSendLimitDecision:
        """Reserve one attempt or raise ``EmailSendLimitStoreUnavailable``."""


def normalize_organization_scope(organization_id: str | None) -> str:
    """Return the persisted organization key; missing org stays empty, not merged."""
    if organization_id is None:
        return ""
    return organization_id


def decide_email_send_limit(
    current_state: EmailSendLimitWindowState | None,
    *,
    observed_at: datetime,
    max_attempts: int,
    window_seconds: float,
) -> tuple[str, EmailSendLimitWindowState | None]:
    """Return ``allowed`` or ``blocked`` plus the next window state.

    The function is pure so SharedMemory and SQL stores apply the same clock
    and occupancy rules. ``observed_at`` must be injected by the caller.
    """
    cutoff = observed_at - timedelta(seconds=window_seconds)
    if current_state is None or current_state.window_started_at <= cutoff:
        if current_state is None:
            organization_id = ""
            owner_user_id = ""
        else:
            organization_id = current_state.organization_id
            owner_user_id = current_state.owner_user_id
        next_state = EmailSendLimitWindowState(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            window_started_at=observed_at,
            attempt_count=1,
        )
        return _DECISION_ALLOWED, next_state
    if current_state.attempt_count >= max_attempts:
        return _DECISION_BLOCKED, current_state
    next_state = EmailSendLimitWindowState(
        organization_id=current_state.organization_id,
        owner_user_id=current_state.owner_user_id,
        window_started_at=current_state.window_started_at,
        attempt_count=current_state.attempt_count + 1,
    )
    return _DECISION_ALLOWED, next_state


def _decision(
    *,
    decision_code: str,
    organization_scope: str,
    owner_user_id: str,
    attempt_count: int,
    window_started_at: datetime | None,
) -> EmailSendLimitDecision:
    if decision_code == _DECISION_BLOCKED:
        return EmailSendLimitDecision(
            decision_code=_DECISION_BLOCKED,
            error_code="email_send_limit_exceeded",
            http_status_code=429,
            user_message="Email send rate limit exceeded",
            organization_scope=organization_scope,
            owner_user_id=owner_user_id,
            attempt_count=attempt_count,
            window_started_at=window_started_at,
        )
    if decision_code == _DECISION_UNAVAILABLE:
        return EmailSendLimitDecision(
            decision_code=_DECISION_UNAVAILABLE,
            error_code="email_send_limit_unavailable",
            http_status_code=503,
            user_message="Email send rate limit unavailable",
            organization_scope=organization_scope,
            owner_user_id=owner_user_id,
            attempt_count=attempt_count,
            window_started_at=window_started_at,
        )
    return EmailSendLimitDecision(
        decision_code=_DECISION_ALLOWED,
        error_code="email_send_limit_allowed",
        http_status_code=200,
        user_message="Email send rate limit allowed",
        organization_scope=organization_scope,
        owner_user_id=owner_user_id,
        attempt_count=attempt_count,
        window_started_at=window_started_at,
    )


class SharedMemoryEmailSendLimitStore:
    """In-process store that multiple simulated workers can share.

    Production request paths must use ``SqlAlchemyEmailSendLimitStore``. This
    class exists so tests can prove shared occupancy without a live database
    and so API tests can inject a deterministic clock-backed bucket.
    """

    def __init__(
        self,
        windows: dict[tuple[str, str], EmailSendLimitWindowState] | None = None,
        lock: Lock | None = None,
    ) -> None:
        self._windows = windows if windows is not None else {}
        self._lock = lock if lock is not None else Lock()

    def persisted_state(self) -> dict[tuple[str, str], EmailSendLimitWindowState]:
        """Return the current window map for PII-absence assertions."""
        return dict(self._windows)

    async def reserve_attempt(
        self,
        *,
        organization_id: str | None,
        owner_user_id: str,
        observed_at: datetime,
        max_attempts: int,
        window_seconds: float,
    ) -> EmailSendLimitDecision:
        """Atomically reserve one send slot in the shared in-memory map."""
        organization_scope = normalize_organization_scope(organization_id)
        scope_key = (organization_scope, owner_user_id)
        with self._lock:
            current = self._windows.get(scope_key)
            decision_code, next_state = decide_email_send_limit(
                current,
                observed_at=observed_at,
                max_attempts=max_attempts,
                window_seconds=window_seconds,
            )
            if next_state is not None:
                stored = EmailSendLimitWindowState(
                    organization_id=organization_scope,
                    owner_user_id=owner_user_id,
                    window_started_at=next_state.window_started_at,
                    attempt_count=next_state.attempt_count,
                )
                if decision_code == _DECISION_ALLOWED:
                    self._windows[scope_key] = stored
            attempt_count = (
                next_state.attempt_count
                if next_state is not None
                else (current.attempt_count if current is not None else 0)
            )
            window_started_at = (
                next_state.window_started_at
                if next_state is not None
                else (current.window_started_at if current is not None else None)
            )
            return _decision(
                decision_code=decision_code,
                organization_scope=organization_scope,
                owner_user_id=owner_user_id,
                attempt_count=attempt_count,
                window_started_at=window_started_at,
            )


class SqlAlchemyEmailSendLimitStore:
    """PostgreSQL-backed store using one atomic ``INSERT ... ON CONFLICT``."""

    def __init__(self, session: object) -> None:
        self._session = session

    @staticmethod
    def reservation_statement(
        *,
        organization_id: str | None,
        owner_user_id: str,
        observed_at: datetime,
        max_attempts: int,
        window_seconds: float,
    ):
        """Build the atomic reservation statement without message fields."""
        organization_scope = normalize_organization_scope(organization_id)
        cutoff = observed_at - timedelta(seconds=window_seconds)
        insert_statement = postgresql_insert(EmailSendLimitWindow).values(
            window_uid=uuid4().hex,
            organization_id=organization_scope,
            owner_user_id=owner_user_id,
            window_started_at=observed_at,
            attempt_count=1,
            updated_at=observed_at,
        )
        expired = EmailSendLimitWindow.window_started_at <= cutoff
        occupied = EmailSendLimitWindow.attempt_count >= max_attempts
        update_statement = insert_statement.on_conflict_do_update(
            index_elements=["organization_id", "owner_user_id"],
            set_={
                "attempt_count": case(
                    (expired, literal(1)),
                    (occupied, EmailSendLimitWindow.attempt_count),
                    else_=EmailSendLimitWindow.attempt_count + 1,
                ),
                "window_started_at": case(
                    (expired, literal(observed_at)),
                    else_=EmailSendLimitWindow.window_started_at,
                ),
                "updated_at": observed_at,
            },
            where=(expired | ~occupied),
        )
        return update_statement.returning(
            EmailSendLimitWindow.attempt_count,
            EmailSendLimitWindow.window_started_at,
        )

    async def reserve_attempt(
        self,
        *,
        organization_id: str | None,
        owner_user_id: str,
        observed_at: datetime,
        max_attempts: int,
        window_seconds: float,
    ) -> EmailSendLimitDecision:
        """Reserve one send slot in PostgreSQL or fail closed."""
        organization_scope = normalize_organization_scope(organization_id)
        try:
            result = await self._session.execute(
                self.reservation_statement(
                    organization_id=organization_id,
                    owner_user_id=owner_user_id,
                    observed_at=observed_at,
                    max_attempts=max_attempts,
                    window_seconds=window_seconds,
                )
            )
            row = result.first()
        except EmailSendLimitStoreUnavailable:
            raise
        except Exception as exc:
            raise EmailSendLimitStoreUnavailable(
                "shared send-limit state unavailable"
            ) from exc
        if row is None:
            return _decision(
                decision_code=_DECISION_BLOCKED,
                organization_scope=organization_scope,
                owner_user_id=owner_user_id,
                attempt_count=max_attempts,
                window_started_at=observed_at,
            )
        return _decision(
            decision_code=_DECISION_ALLOWED,
            organization_scope=organization_scope,
            owner_user_id=owner_user_id,
            attempt_count=int(row[0]),
            window_started_at=row[1],
        )


async def reserve_email_send_attempt(
    store: EmailSendLimitStore,
    *,
    organization_id: str | None,
    owner_user_id: str,
    observed_at: datetime,
    max_attempts: int = DEFAULT_EMAIL_SEND_LIMIT_MAX_ATTEMPTS,
    window_seconds: float = DEFAULT_EMAIL_SEND_LIMIT_WINDOW_SECONDS,
) -> EmailSendLimitDecision:
    """Reserve one send attempt and convert store failures into ``unavailable``."""
    if not owner_user_id:
        return _decision(
            decision_code=_DECISION_UNAVAILABLE,
            organization_scope=normalize_organization_scope(organization_id),
            owner_user_id="",
            attempt_count=0,
            window_started_at=None,
        )
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    try:
        return await store.reserve_attempt(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            observed_at=observed_at,
            max_attempts=max_attempts,
            window_seconds=window_seconds,
        )
    except EmailSendLimitStoreUnavailable:
        return _decision(
            decision_code=_DECISION_UNAVAILABLE,
            organization_scope=normalize_organization_scope(organization_id),
            owner_user_id=owner_user_id,
            attempt_count=0,
            window_started_at=None,
        )
