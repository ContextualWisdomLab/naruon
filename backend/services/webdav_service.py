from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Email, ProjectFolder, TicketTask, WebdavAccount
from services.knowledge_extractor import SELF_SENT_KNOWLEDGE_SOURCE


def safe_webdav_source_label(source_id: str | None) -> str:
    """Return an operator-safe label that exposes only the opaque source ID."""
    if not source_id:
        return "WebDAV source"
    return f"WebDAV source {source_id}"


class WebDavService:
    """Resolve tenant-scoped WebDAV discovery and signed writeback intents."""

    async def get_connected_accounts_from_db(
        self,
        session: AsyncSession,
        user_id: str,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Return database-authoritative WebDAV account capabilities for a scope."""
        scope_filters = [
            WebdavAccount.user_id == user_id,
            WebdavAccount.organization_id == organization_id
            if organization_id is not None
            else WebdavAccount.organization_id.is_(None),
        ]
        if workspace_id is not None:
            scope_filters.append(WebdavAccount.workspace_id == workspace_id)
        stmt = select(
            WebdavAccount.source_uid,
            WebdavAccount.writeback_enabled,
            WebdavAccount.etag_value,
        ).where(*scope_filters)
        result = await session.execute(stmt)
        return [
            {
                "source_id": source_uid,
                "display_label": safe_webdav_source_label(source_uid),
                "writeback_enabled": bool(writeback_enabled),
                "etag": etag_value,
            }
            for source_uid, writeback_enabled, etag_value in result.all()
        ]

    async def get_project_folders_from_db(
        self,
        session: AsyncSession,
        user_id: str,
        organization_id: str | None,
        folder_uid: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Return tenant-scoped project folders from the persisted registry."""
        stmt = select(ProjectFolder).where(
            ProjectFolder.user_id == user_id,
            ProjectFolder.organization_id == organization_id
            if organization_id is not None
            else ProjectFolder.organization_id.is_(None),
        )
        if folder_uid is not None:
            stmt = stmt.where(ProjectFolder.folder_uid == folder_uid)
        result = await session.execute(stmt)
        return [
            {
                "folder_uid": folder.folder_uid,
                "project_name": folder.project_name,
                "webdav_path": folder.webdav_path,
                "owner_user_id": folder.user_id,
                "organization_id": folder.organization_id,
            }
            for folder in result.scalars().all()
        ]

    async def determine_webdav_writeback_intent_from_db(
        self,
        session: AsyncSession,
        user_id: str,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        target_source_id: str | None = None,
    ) -> Dict[str, Any]:
        """Select a writable persisted account without executing provider writes."""
        accounts = await self.get_connected_accounts_from_db(
            session, user_id, organization_id, workspace_id
        )
        return self.determine_webdav_writeback_intent_from_accounts(
            accounts,
            target_source_id=target_source_id,
        )

    async def determine_knowledge_materialization_intent_from_db(
        self,
        session: AsyncSession,
        user_id: str,
        organization_id: str | None,
        workspace_id: str | None,
        source_task_id: str,
        target_source_id: str | None = None,
    ) -> Dict[str, Any]:
        """Create a provenance-bound intent for materializing self-sent knowledge."""
        task_result = await session.execute(
            select(TicketTask, Email.message_id)
            .outerjoin(
                Email,
                (TicketTask.related_email_id == Email.id)
                & (Email.user_id == user_id)
                & (Email.organization_id == organization_id),
            )
            .where(
                TicketTask.task_uid == source_task_id,
                TicketTask.user_id == user_id,
                TicketTask.organization_id == organization_id,
            )
        )
        row = task_result.one_or_none()
        if row is None:
            return {
                "status": "error",
                "error_code": "not_found",
                "message": "Self-sent knowledge task was not found.",
            }

        task, source_email_id = row
        if task.source_type != SELF_SENT_KNOWLEDGE_SOURCE:
            return {
                "status": "error",
                "error_code": "validation_error",
                "message": "Task is not self-sent knowledge.",
            }
        if source_email_id is None:
            return {
                "status": "error",
                "error_code": "missing_provenance",
                "message": "Self-sent knowledge task missing source email provenance.",
            }

        result = await self.determine_webdav_writeback_intent_from_db(
            session,
            user_id,
            organization_id,
            workspace_id,
            target_source_id=target_source_id,
        )
        if result.get("status") == "error":
            return result

        return {
            "intent": "knowledge_materialization",
            "status": "intent_ready",
            "task_id": task.task_uid,
            "source_type": SELF_SENT_KNOWLEDGE_SOURCE,
            "source_email_id": source_email_id,
            "source_thread_id": task.related_thread_id,
            "source_id": result["source_id"],
            "target_label": result["target_label"],
            "target_path": f"/Naruon/Notes/{task.task_uid}.md",
            "requires_if_match": result["requires_if_match"],
            "if_match": result.get("if_match"),
            "provenance": result["provenance"],
            "provider_write_executed": False,
            "audit_event": "webdav.self_sent_knowledge_intent.created",
        }

    def determine_webdav_writeback_intent_from_accounts(
        self,
        accounts: List[Dict[str, Any]],
        target_source_id: str | None = None,
    ) -> Dict[str, Any]:
        """Select one write-enabled account from a server-authoritative inventory."""
        writable_accounts = {
            account["source_id"]: account
            for account in accounts
            if account.get("writeback_enabled", False)
        }
        if not writable_accounts:
            return {
                "status": "error",
                "error_code": "no_webdav_account",
                "message": "No connected WebDAV accounts found.",
            }

        if target_source_id is not None:
            selected_account = writable_accounts.get(target_source_id)
            if selected_account is None:
                return {
                    "status": "error",
                    "error_code": "webdav_account_not_found",
                    "message": "Requested WebDAV account was not found.",
                }
        else:
            selected_account = next(iter(writable_accounts.values()))

        return {
            "intent": "writeback",
            "source_id": selected_account["source_id"],
            "target_label": selected_account.get("display_label")
            or safe_webdav_source_label(selected_account["source_id"]),
            "requires_if_match": True,
            "if_match": selected_account.get("etag")
            or selected_account.get("etag_value"),
            "provenance": "server-authoritative",
        }


webdav_service = WebDavService()
