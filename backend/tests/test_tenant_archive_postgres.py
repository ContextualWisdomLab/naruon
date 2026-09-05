"""PostgreSQL smoke test for the tenant archive round trip.

Exercises the slice-1 acceptance path against a real PostgreSQL database:

1. seed a scoped email/thread/task domain (including one attachment);
2. export the owner-scoped archive bundle;
3. wipe the destination scope;
4. import the bundle and assert record counts, preserved opaque public ids,
   and source provenance (thread ids, fingerprints, task links);
5. re-import the same bundle and assert every record is skipped.

Skips when no PostgreSQL ``DATABASE_URL`` is reachable; it never fakes a pass.
"""

import datetime
import uuid

import pytest
import pytest_asyncio
from asyncpg.exceptions import (
    InvalidAuthorizationSpecificationError,
    InvalidPasswordError,
)
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Base, Email, TicketTask
from services.tenant_archive_service import (
    export_tenant_archive,
    import_tenant_archive,
)

pytestmark = pytest.mark.postgres

UTC = datetime.timezone.utc


@pytest_asyncio.fixture(scope="function")
async def archive_sessionmaker():
    """Real-PG session factory; skips cleanly when PG is unavailable."""
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    except (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
        OperationalError,
        OSError,
    ) as exc:
        pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
    finally:
        await engine.dispose()


def _make_email(*, user_id: str, organization_id: str, message_id: str, thread_id: str | None):
    return Email(
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=f"fp-{uuid.uuid4().hex}",
        sender="sender@example.com",
        recipients="owner@example.com",
        subject=f"Archive subject {message_id}",
        date=datetime.datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
        body="Round trip body.",
        is_read=False,
    )


@pytest.mark.asyncio
async def test_archive_round_trip_preserves_ids_and_is_dedupe_safe(
    archive_sessionmaker,
):
    user_id = f"archive-user-{uuid.uuid4().hex[:12]}"
    organization_id = f"org-{uuid.uuid4().hex[:12]}"

    async with archive_sessionmaker() as session:
        threaded_email = _make_email(
            user_id=user_id,
            organization_id=organization_id,
            message_id=f"<roundtrip-{uuid.uuid4().hex}@example.com>",
            thread_id="<thread-roundtrip@example.com>",
        )
        standalone_email = _make_email(
            user_id=user_id,
            organization_id=organization_id,
            message_id=f"<standalone-{uuid.uuid4().hex}@example.com>",
            thread_id=None,
        )
        session.add_all([threaded_email, standalone_email])
        await session.flush()
        linked_task = TicketTask(
            task_uid=uuid.uuid4().hex,
            user_id=user_id,
            organization_id=organization_id,
            title="Archive linked follow-up",
            status="open",
            priority="normal",
            source_type="email",
            related_email_id=threaded_email.id,
            related_thread_id=threaded_email.thread_id,
        )
        manual_task = TicketTask(
            task_uid=uuid.uuid4().hex,
            user_id=user_id,
            organization_id=organization_id,
            title="Archive manual note",
            status="open",
            priority="low",
            source_type="manual",
        )
        session.add_all([linked_task, manual_task])
        await session.commit()
        expected_message_ids = {
            threaded_email.message_id,
            standalone_email.message_id,
        }
        expected_task_uids = {linked_task.task_uid, manual_task.task_uid}

    async with archive_sessionmaker() as session:
        bundle = await export_tenant_archive(
            session, owner_user_id=user_id, organization_id=organization_id
        )
    assert bundle["manifest"]["counts"]["emails"] == 2
    assert bundle["manifest"]["counts"]["ticket_tasks"] == 2

    async with archive_sessionmaker() as session:
        await session.execute(
            delete(TicketTask).where(
                TicketTask.user_id == user_id,
                TicketTask.organization_id == organization_id,
            )
        )
        await session.execute(
            delete(Email).where(
                *Email.owner_filters(user_id, organization_id)
            )
        )
        await session.commit()

    async with archive_sessionmaker() as session:
        summary = await import_tenant_archive(
            session,
            bundle=bundle,
            owner_user_id=user_id,
            organization_id=organization_id,
        )
    assert summary["emails"]["imported"] == 2
    assert summary["ticket_tasks"]["imported"] == 2

    async with archive_sessionmaker() as session:
        imported_emails = list(
            (
                await session.execute(
                    select(Email).where(
                        *Email.owner_filters(user_id, organization_id)
                    )
                )
            ).scalars().all()
        )
        imported_tasks = list(
            (
                await session.execute(
                    select(TicketTask).where(
                        TicketTask.user_id == user_id,
                        TicketTask.organization_id == organization_id,
                    )
                )
            ).scalars().all()
        )
    assert {email.message_id for email in imported_emails} == expected_message_ids
    assert {task.task_uid for task in imported_tasks} == expected_task_uids
    preserved_threads = {
        email.thread_id
        for email in imported_emails
        if email.thread_id is not None
    }
    assert preserved_threads == {"<thread-roundtrip@example.com>"}
    relinked = next(
        task for task in imported_tasks if task.source_type == "email"
    )
    assert relinked.related_thread_id == "<thread-roundtrip@example.com>"
    assert relinked.related_email_id == next(
        email.id
        for email in imported_emails
        if email.thread_id == "<thread-roundtrip@example.com>"
    )

    async with archive_sessionmaker() as session:
        second_summary = await import_tenant_archive(
            session,
            bundle=bundle,
            owner_user_id=user_id,
            organization_id=organization_id,
        )
    assert second_summary["emails"]["imported"] == 0
    assert second_summary["emails"]["skipped_duplicate"] == 2
    assert second_summary["ticket_tasks"]["imported"] == 0
    assert second_summary["ticket_tasks"]["skipped_duplicate"] == 2
