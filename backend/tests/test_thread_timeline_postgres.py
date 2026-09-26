"""Exercise owner isolation for email thread tasks against PostgreSQL."""

import datetime
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.emails import get_email_thread
from api.tasks import UpdateTicketTaskRequest, update_ticket_task
from core.config import settings
from db.models import Base, Email, TicketTask


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_thread_tasks_stay_with_their_email_owner():
    schema = f"e1_timeline_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    now = datetime.datetime(2026, 9, 27, tzinfo=datetime.timezone.utc)
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)

        sessions = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with sessions() as session:
            owned = Email(
                user_id="owner-a",
                organization_id="org-1",
                message_id="owned@example.com",
                thread_id="shared-thread",
                sender="sender@example.com",
                date=now,
                body="Owned message",
            )
            foreign = Email(
                user_id="owner-b",
                organization_id="org-1",
                message_id="foreign@example.com",
                thread_id="shared-thread",
                sender="sender@example.com",
                date=now,
                body="Foreign message",
            )
            session.add_all([owned, foreign])
            await session.flush()
            session.add_all(
                [
                    TicketTask(
                        task_uid="owned-task",
                        user_id="owner-a",
                        organization_id="org-1",
                        title="Owned task",
                        related_email_id=owned.id,
                        related_thread_id="shared-thread",
                        created_at=now,
                    ),
                    TicketTask(
                        task_uid="thread-task",
                        user_id="owner-a",
                        organization_id="org-1",
                        title="Thread task",
                        related_thread_id="shared-thread",
                        created_at=now,
                    ),
                    TicketTask(
                        task_uid="foreign-task",
                        user_id="owner-b",
                        organization_id="org-1",
                        title="Foreign task",
                        related_email_id=foreign.id,
                        related_thread_id="shared-thread",
                        created_at=now,
                    ),
                    TicketTask(
                        task_uid="wrong-email-task",
                        user_id="owner-a",
                        organization_id="org-1",
                        title="Wrong email task",
                        related_email_id=foreign.id,
                        related_thread_id="shared-thread",
                        created_at=now,
                    ),
                ]
            )
            await session.commit()

        async with sessions() as session:
            result = await get_email_thread(
                "shared-thread",
                db=session,
                auth_context=AuthContext(
                    user_id="owner-a",
                    role="member",
                    organization_id="org-1",
                    group_ids=(),
                    workspace_id="workspace-org-1",
                ),
            )
        assert [email.message_id for email in result.thread] == ["owned@example.com"]
        assert {task.id for task in result.tasks} == {"owned-task", "thread-task"}
        assert {task.id: task.link_confidence for task in result.tasks} == {
            "owned-task": 1.0,
            "thread-task": None,
        }

        owner_auth = AuthContext(
            user_id="owner-a",
            role="member",
            organization_id="org-1",
            group_ids=(),
            workspace_id="workspace-org-1",
        )
        async with sessions() as session:
            for task_uid, expected_status in (
                ("foreign-task", 404),
                ("owned-task", 409),
            ):
                with pytest.raises(HTTPException) as error:
                    await update_ticket_task(
                        task_uid,
                        UpdateTicketTaskRequest(detach_thread_id="shared-thread"),
                        db=session,
                        auth_context=owner_auth,
                    )
                assert error.value.status_code == expected_status
            with pytest.raises(HTTPException) as error:
                await update_ticket_task(
                    "thread-task",
                    UpdateTicketTaskRequest(detach_thread_id="stale-thread"),
                    db=session,
                    auth_context=owner_auth,
                )
            assert error.value.status_code == 409

            detached = await update_ticket_task(
                "thread-task",
                UpdateTicketTaskRequest(detach_thread_id="shared-thread"),
                db=session,
                auth_context=owner_auth,
            )
            assert detached.related_thread_id is None
            after = await get_email_thread(
                "shared-thread", db=session, auth_context=owner_auth
            )
            assert [task.id for task in after.tasks] == ["owned-task"]
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
