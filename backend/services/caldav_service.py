import logging
from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


def _log_safe_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))

async def sync_caldav_accounts(session, user_id: str):
    """
    Report configured CalDAV accounts without pretending import succeeded.

    Inbound CalDAV event import needs a provider-specific parser and sync
    cursor before it can safely mutate local state. Until that adapter exists,
    callers get a false return value and the logs explain the skipped work.
    """
    from db.models import CaldavAccount
    from sqlalchemy import select

    logger.info(f"Syncing CalDAV accounts for user {user_id}")
    stmt = select(CaldavAccount).where(CaldavAccount.user_id == user_id)
    result = await session.execute(stmt)
    accounts = result.scalars().all()

    if not accounts:
        logger.info("No CalDAV accounts configured for user %s", user_id)
        return False

    for account in accounts:
        logger.warning(
            "CalDAV sync skipped for account %s at %s: inbound CalDAV import "
            "adapter is not configured",
            account.id,
            _log_safe_url(account.server_url),
        )

    return False

class CalDavService:
    def determine_writeback_target(
        self,
        task_context: Dict[str, Any],
        connected_accounts: list,
    ) -> str | None:
        """
        Determine the opaque customer-owned CalDAV source to write back to.
        """
        eligible_sources = [
            account
            for account in connected_accounts
            if account.get("writeback_enabled") is True
            and isinstance(account.get("source_id"), str)
            and account.get("source_id")
        ]
        source_email = task_context.get("source_email", "")
        if isinstance(source_email, str) and "@" in source_email:
            source_domain = source_email.strip().lower().rsplit("@", 1)[-1]
            for account in eligible_sources:
                account_domain = str(account.get("domain", "")).lower().strip()
                if account_domain and source_domain == account_domain:
                    return account["source_id"]
                
        if eligible_sources:
            return eligible_sources[0]["source_id"]
        return None

caldav_service = CalDavService()
