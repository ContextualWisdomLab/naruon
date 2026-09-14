"""Real PostgreSQL acceptance for bounded Reply-SLA conflict recovery.

This suite complements the scheduler interleaving coverage by forcing the
fallback path through PostgreSQL's actual unique-constraint handling for every
allowed batch attempt. It verifies the retry budget and outer rollback on the
migrated schema rather than treating the SQLite unit-of-work bridge as
production acceptance.

Run ``scripts/migrate_db.py`` against the isolated PostgreSQL service before
this test. No metadata-created substitute schema or unavailable-database skip
is used.
"""

import datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Email, TicketTask
from services import reply_sla_escalation_service as service

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


async def test_exhausted_real_unique_conflicts_roll_back_without_partial_write(
    monkeypatch,
):
    """PostgreSQL uniqueness conflicts stay batch-bounded and all-or-nothing."""
    database_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=2,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    owner_key = f"reply_sla_budget_{uuid4().hex}"
    workspace_key = f"workspace_{uuid4().hex}"
    now = datetime.datetime.now(datetime.timezone.utc)
    fetch_calls = 0

    try:
        async with session_factory() as setup_session:
            source_email = Email(
                user_id=owner_key,
                organization_id=owner_key,
                workspace_id=workspace_key,
                message_id=f"<{uuid4().hex}@example.invalid>",
                sender="archive-author@example.invalid",
                recipients="archive-reader@example.invalid",
                subject="Observed conflict budget",
                date=now - datetime.timedelta(days=3),
                body="Archived message used only for transaction acceptance.",
            )
            setup_session.add(source_email)
            await setup_session.flush()
            source_email_id = source_email.id
            setup_session.add(
                TicketTask(
                    user_id=owner_key,
                    organization_id=owner_key,
                    title="Existing committed winner",
                    status="open",
                    priority="normal",
                    source_type=service.REPLY_SLA_SOURCE_TYPE,
                    related_email_id=source_email_id,
                    related_thread_id=None,
                )
            )
            await setup_session.commit()

        async def hide_committed_winner(*_args, **_kwargs):
            nonlocal fetch_calls
            fetch_calls += 1
            return {}

        monkeypatch.setattr(
            service,
            "_fetch_existing_tasks_by_email",
            hide_committed_winner,
        )

        async with session_factory() as worker_session:
            source_email = await worker_session.scalar(
                select(Email).where(
                    Email.id == source_email_id,
                    Email.user_id == owner_key,
                    Email.organization_id == owner_key,
                    Email.workspace_id == workspace_key,
                )
            )
            assert source_email is not None

            with pytest.raises(service.ReplySlaTaskConflict) as conflict_error:
                await service._process_fallback_escalation(
                    worker_session,
                    owner_key,
                    owner_key,
                    [source_email],
                    now,
                )

            assert conflict_error.value.error_code == "reply_sla_batch_retry_exhausted"
            assert fetch_calls == 1 + service.REPLY_SLA_MAX_BATCH_ATTEMPTS
            assert not worker_session.in_transaction()

        async with session_factory() as verification_session:
            persisted_tasks = (
                await verification_session.scalars(
                    select(TicketTask).where(
                        TicketTask.user_id == owner_key,
                        TicketTask.organization_id == owner_key,
                        TicketTask.source_type == service.REPLY_SLA_SOURCE_TYPE,
                        TicketTask.related_email_id == source_email_id,
                    )
                )
            ).all()
            assert len(persisted_tasks) == 1
            assert persisted_tasks[0].title == "Existing committed winner"
            assert persisted_tasks[0].status == "open"
            assert persisted_tasks[0].priority == "normal"
            assert (
                await verification_session.scalar(
                    select(func.count())
                    .select_from(Email)
                    .where(
                        Email.id == source_email_id,
                        Email.user_id == owner_key,
                        Email.organization_id == owner_key,
                        Email.workspace_id == workspace_key,
                    )
                )
            ) == 1
    finally:
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(TicketTask).where(
                    TicketTask.user_id == owner_key,
                    TicketTask.organization_id == owner_key,
                )
            )
            await cleanup_session.execute(
                delete(Email).where(
                    Email.user_id == owner_key,
                    Email.organization_id == owner_key,
                    Email.workspace_id == workspace_key,
                )
            )
            await cleanup_session.commit()
        await database_engine.dispose()
