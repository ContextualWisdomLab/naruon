"""Exercise owner isolation for email thread tasks against PostgreSQL."""

import datetime
import uuid
from unittest.mock import patch

import pytest
from asyncpg.exceptions import (
    InvalidAuthorizationSpecificationError,
    InvalidPasswordError,
)
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.emails import get_email_thread
from api.tasks import UpdateTicketTaskRequest, update_ticket_task
from core.config import settings
from db.models import Base, Email, TicketTask, TicketTaskThreadDismissal


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
    schema_created = False
    try:
        try:
            async with root_engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True
        except (
            InvalidAuthorizationSpecificationError,
            InvalidPasswordError,
            OperationalError,
            OSError,
        ) as exc:
            pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
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
        task_query = select(TicketTask).where(TicketTask.task_uid == "thread-task")
        async with sessions() as stale_session:
            stale_task = (await stale_session.execute(task_query)).scalar_one()
            assert stale_task.related_thread_id == "shared-thread"
            async with sessions() as writer:
                changed_task = (await writer.execute(task_query)).scalar_one()
                changed_task.related_thread_id = "changed-thread"
                await writer.commit()
            with pytest.raises(HTTPException) as error:
                await update_ticket_task(
                    "thread-task",
                    UpdateTicketTaskRequest(detach_thread_id="shared-thread"),
                    db=stale_session,
                    auth_context=owner_auth,
                )
            assert error.value.status_code == 409

        async with sessions() as writer:
            changed_task = (await writer.execute(task_query)).scalar_one()
            assert changed_task.related_thread_id == "changed-thread"
            changed_task.related_thread_id = "shared-thread"
            await writer.commit()

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

            with patch.object(session, "execute", wraps=session.execute) as execute:
                detached = await update_ticket_task(
                    "thread-task",
                    UpdateTicketTaskRequest(detach_thread_id="shared-thread"),
                    db=session,
                    auth_context=owner_auth,
                )
            assert any(
                "FOR UPDATE OF ticket_tasks"
                in str(call.args[0].compile(dialect=postgresql.dialect()))
                for call in execute.call_args_list
            )
            assert detached.id == "thread-task"
            assert (
                await session.execute(task_query)
            ).scalar_one().related_thread_id == "shared-thread"
            dismissal = (
                await session.execute(select(TicketTaskThreadDismissal))
            ).scalar_one()
            assert dismissal.thread_key == "shared-thread"
            assert dismissal.actor_user_id == "owner-a"
            repeated = await update_ticket_task(
                "thread-task",
                UpdateTicketTaskRequest(detach_thread_id="shared-thread"),
                db=session,
                auth_context=owner_auth,
            )
            assert repeated.id == "thread-task"
            assert (
                len((await session.execute(select(TicketTaskThreadDismissal))).all())
                == 1
            )
            after = await get_email_thread(
                "shared-thread", db=session, auth_context=owner_auth
            )
            assert [task.id for task in after.tasks] == ["owned-task"]
    finally:
        await scoped_engine.dispose()
        if schema_created:
            async with root_engine.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        await root_engine.dispose()
