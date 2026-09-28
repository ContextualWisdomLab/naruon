import datetime
import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from asyncpg.exceptions import (
    InvalidAuthorizationSpecificationError,
    InvalidPasswordError,
)
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from core.config import settings
from api.auth import AuthContext
from api.emails import get_email_thread
from db.models import Base, Email, EmailThreadEdge
from services.imap_worker import process_fetched_email
from services.threading_service import detach_email_from_thread, email_thread_evidence


@pytest.mark.asyncio
async def test_thread_view_resolves_late_parent_without_cross_owner_match():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEdge.__table__.create(engine)
        when = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)

        def message(owner: str, message_id: str, body: str) -> Email:
            return Email(
                user_id=owner,
                organization_id="org",
                message_id=message_id,
                thread_id="parent@example.com",
                sender=f"{owner}@example.com",
                recipients=f"{owner}@example.com",
                subject="Thread",
                body=body,
                date=when,
            )

        class AsyncAdapter:
            def __init__(self, session: Session):
                self.session = session

            async def execute(self, statement):
                return self.session.execute(statement)

        auth = AuthContext("owner", "member", "org", (), "workspace-owner")
        with Session(engine) as session:
            other_parent = message("other", "<parent@example.com>", "other parent")
            reply = message("owner", "<reply@example.com>", "reply")
            reply.in_reply_to = "<parent@example.com>"
            session.add_all([other_parent, reply])
            session.add_all(email_thread_evidence(reply))
            session.commit()

            initial = await get_email_thread(
                "parent@example.com", AsyncAdapter(session), auth
            )
            assert len(initial["thread"]) == 1
            assert initial["thread"][0].thread_evidence[0].state == "unresolved"

            owner_parent = message("owner", "<parent@example.com>", "owner parent")
            session.add(owner_parent)
            session.commit()
            updated = await get_email_thread(
                "parent@example.com", AsyncAdapter(session), auth
            )
            assert len(updated["thread"]) == 2
            evidence = next(
                item.thread_evidence[0]
                for item in updated["thread"]
                if item.id == reply.id
            )
            assert evidence.state == "resolved"
            assert evidence.target_email_id == owner_parent.id

            ambiguous = message("owner", "<ambiguous@example.com>", "ambiguous reply")
            ambiguous.in_reply_to = "<parent@example.com> <other@example.com>"
            session.add(ambiguous)
            session.add_all(email_thread_evidence(ambiguous))
            session.commit()
            view = await get_email_thread(
                "parent@example.com", AsyncAdapter(session), auth
            )
            ambiguous_states = [
                edge.state
                for item in view["thread"]
                if item.id == ambiguous.id
                for edge in item.thread_evidence
            ]
            assert ambiguous_states == ["conflicting", "conflicting"]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_detach_correction_moves_reply_subtree_and_survives_reimport():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEdge.__table__.create(engine)

        class AsyncAdapter:
            def __init__(self, session: Session):
                self.session = session

            async def execute(self, statement):
                return self.session.execute(statement)

            def add(self, item):
                self.session.add(item)

            async def commit(self):
                self.session.commit()

        when = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)

        def message(message_id: str, body: str, parent: str | None = None):
            return {
                "message_id": f"<{message_id}>",
                "in_reply_to": f"<{parent}>" if parent else None,
                "references": f"<{parent}>" if parent else None,
                "sender": "sender@example.com",
                "recipients": ["owner@example.com"],
                "subject": body,
                "body": body,
                "date": when,
            }

        with Session(engine) as session:
            adapter = AsyncAdapter(session)
            parent = await process_fetched_email(
                adapter, message("parent@example.com", "parent"), "owner", "org"
            )
            await adapter.commit()
            reply_message = message("reply@example.com", "reply", "parent@example.com")
            reply = await process_fetched_email(adapter, reply_message, "owner", "org")
            await adapter.commit()
            grandchild = await process_fetched_email(
                adapter,
                message("child@example.com", "child", "reply@example.com"),
                "owner",
                "org",
            )
            await adapter.commit()

            assert (
                await detach_email_from_thread(
                    adapter,
                    email_id=reply.id,
                    user_id="other",
                    organization_id="org",
                    reason="wrong conversation",
                )
                is None
            )
            assert (
                await detach_email_from_thread(
                    adapter,
                    email_id=reply.id,
                    user_id="owner",
                    organization_id="org",
                    reason="wrong conversation",
                )
                == 2
            )
            assert parent.thread_id == "parent@example.com"
            assert reply.thread_id == "reply@example.com"
            assert grandchild.thread_id == "reply@example.com"
            edges = session.scalars(
                select(EmailThreadEdge).where(
                    EmailThreadEdge.source_email_id == reply.id
                )
            ).all()
            assert edges and all(
                edge.detached_by == "owner"
                and edge.detach_reason == "wrong conversation"
                and edge.detached_at is not None
                for edge in edges
            )

            reimported = await process_fetched_email(
                adapter, reply_message, "owner", "org"
            )
            assert reimported.id == reply.id
            assert (
                session.scalars(
                    select(EmailThreadEdge).where(
                        EmailThreadEdge.source_email_id == reply.id
                    )
                ).all()
                == edges
            )
            auth = AuthContext("owner", "member", "org", (), "workspace-owner")
            old_view = await get_email_thread("parent@example.com", adapter, auth)
            new_view = await get_email_thread("reply@example.com", adapter, auth)
            assert [item.id for item in old_view["thread"]] == [parent.id]
            assert {item.id for item in new_view["thread"]} == {reply.id, grandchild.id}
            assert (
                next(item for item in new_view["thread"] if item.id == reply.id)
                .thread_evidence[0]
                .state
                == "detached"
            )
    finally:
        engine.dispose()


def test_thread_evidence_migration_backfills_existing_headers():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0018_email_thread_evidence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "email_thread_evidence_migration", path
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE email_records (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, "
                    "organization_id TEXT, message_id TEXT NOT NULL, "
                    'in_reply_to TEXT, "references" TEXT)'
                )
            )
            connection.execute(
                text(
                    "INSERT INTO email_records VALUES "
                    "(1, 'owner', 'org', 'reply@example.com', '<parent@example.com>', "
                    "'<root@example.com> <parent@example.com>')"
                )
            )
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            rows = connection.execute(
                text(
                    "SELECT evidence_source, target_message_id, incomplete "
                    "FROM email_thread_evidence ORDER BY evidence_source, ordinal"
                )
            ).all()
            assert rows == [
                ("in_reply_to", "parent@example.com", 0),
                ("references", "root@example.com", 0),
                ("references", "parent@example.com", 0),
            ]
    finally:
        engine.dispose()


def test_reply_evidence_survives_a_real_local_database_round_trip():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEdge.__table__.create(engine)
        with Session(engine) as session:
            email = Email(
                user_id="owner",
                organization_id="org",
                message_id="reply@example.com",
                thread_id="parent@example.com",
                sender="sender@example.com",
                recipients="owner@example.com",
                subject="Reply",
                body="body",
                date=datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc),
                in_reply_to="<parent@example.com>",
            )
            session.add(email)
            session.add_all(email_thread_evidence(email))
            session.commit()
            session.expire_all()
            stored = session.scalars(select(EmailThreadEdge)).one()
            assert stored.source_message_id == "reply@example.com"
            assert stored.target_message_id == "parent@example.com"
            assert stored.user_id == "owner"
            assert stored.incomplete is False
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_reply_evidence_persists_before_parent_and_stays_owner_scoped():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SELECT 1"))
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await connection.run_sync(Base.metadata.create_all)
        except (
            InvalidAuthorizationSpecificationError,
            InvalidPasswordError,
            OperationalError,
            OSError,
        ) as exc:
            pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
        except DBAPIError as exc:
            if 'extension "vector" is not available' in str(exc):
                pytest.skip("PostgreSQL pgvector extension unavailable")
            raise

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        owner = f"thread-owner-{uuid.uuid4().hex}"
        other = f"thread-other-{uuid.uuid4().hex}"
        organization = f"org-{uuid.uuid4().hex}"
        when = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)
        async with sessions() as session:
            await process_fetched_email(
                session,
                {
                    "message_id": "<parent@example.com>",
                    "sender": "other@example.com",
                    "recipients": ["other@example.com"],
                    "subject": "Other owner's parent",
                    "body": "unrelated",
                    "date": when,
                },
                other,
                organization,
            )
            reply = await process_fetched_email(
                session,
                {
                    "message_id": "<reply@example.com>",
                    "in_reply_to": "<parent@example.com>",
                    "references": "<root@example.com> <parent@example.com>",
                    "sender": "sender@example.com",
                    "recipients": ["owner@example.com"],
                    "subject": "Reply",
                    "body": "reply body",
                    "date": when,
                },
                owner,
                organization,
            )
            await session.commit()
            assert reply.thread_id == "root@example.com"

            evidence = (
                (
                    await session.execute(
                        select(EmailThreadEdge)
                        .where(EmailThreadEdge.source_email_id == reply.id)
                        .order_by(
                            EmailThreadEdge.evidence_source, EmailThreadEdge.ordinal
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert [
                (edge.evidence_source, edge.target_message_id) for edge in evidence
            ] == [
                ("in_reply_to", "parent@example.com"),
                ("references", "root@example.com"),
                ("references", "parent@example.com"),
            ]
            assert all(
                edge.user_id == owner and edge.organization_id == organization
                for edge in evidence
            )

            parents = (
                (
                    await session.execute(
                        select(Email).where(
                            *Email.owner_filters(owner, organization),
                            Email.message_id.in_(
                                ("parent@example.com", "<parent@example.com>")
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert parents == []

            await process_fetched_email(
                session,
                {
                    "message_id": "<parent@example.com>",
                    "sender": "owner@example.com",
                    "recipients": ["owner@example.com"],
                    "subject": "Owner's parent",
                    "body": "parent body",
                    "date": when,
                },
                owner,
                organization,
            )
            await session.commit()
            parents = (
                (
                    await session.execute(
                        select(Email).where(
                            *Email.owner_filters(owner, organization),
                            Email.message_id.in_(
                                ("parent@example.com", "<parent@example.com>")
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(parents) == 1
            assert evidence[0].target_message_id == "parent@example.com"

            await session.execute(
                delete(Email).where(Email.user_id.in_((owner, other)))
            )
            await session.commit()
    finally:
        await engine.dispose()
