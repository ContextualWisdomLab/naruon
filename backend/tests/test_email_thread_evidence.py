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
from db.models import Base, Email, EmailThreadEvidenceRecord
from services.email_import_service import (
    _acquire_owner_import_quota_lock,
    _find_existing_email,
    _import_single_eml,
    _release_owner_import_quota_lock,
)
from services.imap_worker import process_fetched_email
from services.threading_service import (
    assign_thread_id,
    detach_email_from_thread,
    email_thread_evidence,
)


@pytest.mark.asyncio
async def test_thread_view_resolves_late_parent_without_cross_owner_match():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEvidenceRecord.__table__.create(engine)
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

            owner_parent = message("owner", "<parent@ example.com>", "owner parent")
            owner_parent.thread_id = "root@example.com"
            session.add(owner_parent)
            session.commit()
            assert await assign_thread_id(
                AsyncAdapter(session),
                {"message_id": "<next@example.com>", "in_reply_to": "<parent@example.com>"},
                user_id="owner", organization_id="org",
            ) == "root@example.com"
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
            assert await _find_existing_email(
                AsyncAdapter(session),
                user_id="owner",
                organization_id="org",
                message_id="parent@example.com",
                fingerprint="unused",
            ) == owner_parent

            duplicate_parent = message("owner", "parent@example.com", "duplicate parent")
            duplicate_parent.thread_id = "unrelated@example.com"
            session.add(duplicate_parent)
            session.commit()
            duplicated_view = await get_email_thread(
                "parent@example.com", AsyncAdapter(session), auth
            )
            assert {item.id for item in duplicated_view["thread"]} == {reply.id}
            duplicate_evidence = next(
                item.thread_evidence[0]
                for item in duplicated_view["thread"]
                if item.id == reply.id
            )
            assert duplicate_evidence.state == "ambiguous"
            assert duplicate_evidence.target_email_id is None
            assert await _find_existing_email(
                AsyncAdapter(session),
                user_id="owner",
                organization_id="org",
                message_id="parent@example.com",
                fingerprint="unused",
            ) is not None
            assert await assign_thread_id(
                AsyncAdapter(session),
                {"message_id": "<later@example.com>", "in_reply_to": "<parent@example.com>"},
                user_id="owner", organization_id="org",
            ) == "later@example.com"
            root = message("owner", "root@example.com", "shared ancestor")
            root.thread_id = "root@example.com"
            session.add(root)
            session.commit()
            assert await assign_thread_id(
                AsyncAdapter(session),
                {
                    "message_id": "<ambiguous-root-reply@example.com>",
                    "in_reply_to": "<parent@example.com>",
                    "references": "<root@example.com> <parent@example.com>",
                },
                user_id="owner", organization_id="org",
            ) == "ambiguous-root-reply@example.com"

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
        EmailThreadEvidenceRecord.__table__.create(engine)

        class AsyncAdapter:
            def __init__(self, session: Session):
                self.session = session

            async def execute(self, statement):
                return self.session.execute(statement)

            def add(self, item):
                self.session.add(item)

            async def flush(self):
                self.session.flush()

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
                select(EmailThreadEvidenceRecord).where(
                    EmailThreadEvidenceRecord.source_email_id == reply.id
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
                    select(EmailThreadEvidenceRecord).where(
                        EmailThreadEvidenceRecord.source_email_id == reply.id
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


@pytest.mark.asyncio
async def test_late_ancestor_reconciles_previously_split_thread_keys():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEvidenceRecord.__table__.create(engine)

        class AsyncAdapter:
            def __init__(self, session: Session):
                self.session = session

            async def execute(self, statement, params=None):
                return self.session.execute(statement, params or {})

            def add(self, item):
                self.session.add(item)

            async def flush(self):
                self.session.flush()

            async def commit(self):
                self.session.commit()

        when = datetime.datetime(2026, 9, 28, tzinfo=datetime.timezone.utc)

        def message(message_id: str, parent: str, references: str):
            return {
                "message_id": f"<{message_id}>",
                "in_reply_to": f"<{parent}>",
                "references": references,
                "sender": "sender@example.com",
                "recipients": ["owner@example.com"],
                "subject": message_id,
                "body": message_id,
                "date": when,
            }

        with Session(engine) as session:
            adapter = AsyncAdapter(session)
            reply = await process_fetched_email(
                adapter,
                message(
                    "reply@example.com", "parent@example.com", "<parent@example.com>"
                ),
                "owner",
                "org",
            )
            await adapter.commit()
            child = await process_fetched_email(
                adapter,
                message(
                    "child@example.com",
                    "reply@example.com",
                    "<parent@example.com> <reply@example.com>",
                ),
                "owner",
                "org",
            )
            await adapter.commit()
            assert reply.thread_id == child.thread_id == "parent@example.com"

            grandchild = await process_fetched_email(
                adapter,
                message(
                    "grandchild@example.com",
                    "child@example.com",
                    "<parent@example.com> <reply@example.com> <child@example.com>",
                ),
                "owner",
                "org",
            )
            duplicate_child = Email(
                user_id="owner",
                organization_id="org",
                message_id="<child@ example.com>",
                thread_id="elsewhere@example.com",
                sender="sender@example.com",
                recipients="owner@example.com",
                subject="Duplicate Message-ID",
                body="other conversation",
                date=when,
            )
            session.add(duplicate_child)
            await adapter.commit()
            ambiguous_reply = await process_fetched_email(
                adapter,
                message(
                    "ambiguous-reply@example.com",
                    "child@example.com",
                    "<reply@example.com> <child@example.com>",
                ),
                "owner",
                "org",
            )
            await adapter.commit()
            assert ambiguous_reply.thread_id == "ambiguous-reply@example.com"

            conflicting = await process_fetched_email(
                adapter,
                message(
                    "conflict@example.com", "parent@example.com", "<other@example.com>"
                ),
                "owner",
                "org",
            )
            ambiguous = await process_fetched_email(
                adapter,
                message(
                    "ambiguous@example.com",
                    "parent@example.com",
                    "<parent@example.com>",
                )
                | {"in_reply_to": "<parent@example.com> <other@example.com>"},
                "owner",
                "org",
            )
            detached = await process_fetched_email(
                adapter,
                message(
                    "detached@example.com", "parent@example.com", "<parent@example.com>"
                ),
                "owner",
                "org",
            )
            await adapter.commit()
            assert (
                await detach_email_from_thread(
                    adapter,
                    email_id=detached.id,
                    user_id="owner",
                    organization_id="org",
                    reason="Manual correction",
                )
                == 1
            )

            parent = await process_fetched_email(
                adapter,
                message("parent@example.com", "root@example.com", "<root@example.com>"),
                "owner",
                "org",
            )
            await adapter.commit()
            assert parent.thread_id == "root@example.com"
            assert reply.thread_id == child.thread_id == "root@example.com"
            assert grandchild.thread_id == "parent@example.com"
            assert duplicate_child.thread_id == "elsewhere@example.com"
            assert conflicting.thread_id == "conflict@example.com"
            assert ambiguous.thread_id == "ambiguous@example.com"
            assert detached.thread_id == "detached@example.com"
            unrelated = Email(
                user_id="owner",
                organization_id="org",
                message_id="unrelated@example.com",
                thread_id="unrelated@example.com",
                sender="sender@example.com",
                recipients="owner@example.com",
                subject="Unrelated",
                body="unrelated",
                date=when,
            )
            session.add(unrelated)
            await adapter.commit()
            conflicting_existing = await process_fetched_email(
                adapter,
                message(
                    "conflicting-existing@example.com",
                    "parent@example.com",
                    "<unrelated@example.com>",
                ),
                "owner",
                "org",
            )
            multiple_existing = await process_fetched_email(
                adapter,
                message("multiple-existing@example.com", "parent@example.com", "")
                | {
                    "in_reply_to": "<parent@example.com> <unrelated@example.com>",
                    "references": None,
                },
                "owner",
                "org",
            )
            await adapter.commit()
            assert conflicting_existing.thread_id == "conflicting-existing@example.com"
            assert multiple_existing.thread_id == "multiple-existing@example.com"
            folded_parent = await process_fetched_email(
                adapter,
                message(
                    "folded@ example.com",
                    "folded-root@example.com",
                    "<folded-root@example.com>",
                ),
                "owner",
                "org",
            )
            await adapter.commit()
            folded_reply = await process_fetched_email(
                adapter,
                message("folded-reply@example.com", "folded@example.com", "")
                | {"references": None},
                "owner",
                "org",
            )
            await adapter.commit()
            assert folded_parent.message_id == "folded@example.com"
            assert folded_reply.thread_id == "folded-root@example.com"
            auth = AuthContext("owner", "member", "org", (), "workspace-owner")
            conflict_view = await get_email_thread(
                conflicting_existing.thread_id, adapter, auth
            )
            assert {
                edge.state for edge in conflict_view["thread"][0].thread_evidence
            } == {"conflicting"}
            view = await get_email_thread("root@example.com", adapter, auth)
            assert {item.id for item in view["thread"]} == {
                parent.id,
                reply.id,
                child.id,
            }
            unresolved_view = await get_email_thread(
                "parent@example.com", adapter, auth
            )
            grandchild_item = next(
                item for item in unresolved_view["thread"] if item.id == grandchild.id
            )
            assert "ambiguous" in {
                edge.state for edge in grandchild_item.thread_evidence
            }
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
            indexes = connection.execute(text("PRAGMA index_list(email_records)")).all()
            assert any(
                row[1] == "ix_email_records_owner_canonical_message_id"
                for row in indexes
            )
    finally:
        engine.dispose()


def test_reply_evidence_survives_a_real_local_database_round_trip():
    engine = create_engine("sqlite:///:memory:")
    try:
        Email.__table__.create(engine)
        EmailThreadEvidenceRecord.__table__.create(engine)
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
            stored = session.scalars(select(EmailThreadEvidenceRecord)).one()
            assert stored.source_message_id == "reply@example.com"
            assert stored.target_message_id == "parent@example.com"
            assert stored.user_id == "owner"
            assert stored.incomplete is False
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_reply_evidence_persists_before_parent_and_stays_owner_scoped(tmp_path):
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
            assert await _acquire_owner_import_quota_lock(
                session, user_id=owner, organization_id=organization
            )
            await _release_owner_import_quota_lock(
                session, user_id=owner, organization_id=organization
            )
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
                        select(EmailThreadEvidenceRecord)
                        .where(EmailThreadEvidenceRecord.source_email_id == reply.id)
                        .order_by(
                            EmailThreadEvidenceRecord.evidence_source,
                            EmailThreadEvidenceRecord.ordinal,
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

            split_reply = await process_fetched_email(
                session,
                {
                    "message_id": "<split-reply@example.com>",
                    "in_reply_to": "<late-parent@example.com>",
                    "references": "<late-parent@example.com>",
                    "sender": "sender@example.com",
                    "recipients": ["owner@example.com"],
                    "subject": "Split reply",
                    "body": "split reply",
                    "date": when,
                },
                owner,
                organization,
            )
            await session.commit()
            await process_fetched_email(
                session,
                {
                    "message_id": "<late-parent@example.com>",
                    "in_reply_to": "<late-root@example.com>",
                    "references": "<late-root@example.com>",
                    "sender": "sender@example.com",
                    "recipients": ["owner@example.com"],
                    "subject": "Late parent",
                    "body": "late parent",
                    "date": when,
                },
                owner,
                organization,
            )
            await session.commit()
            assert split_reply.thread_id == "late-root@example.com"

            eml_path = tmp_path / "file-reply.eml"
            eml_path.write_bytes(
                b"From: sender@example.com\r\n"
                b"To: owner@example.com\r\n"
                b"Date: Mon, 28 Sep 2026 00:00:00 +0000\r\n"
                b"Subject: File reply\r\n"
                b"Message-ID: <file-reply@example.com>\r\n"
                b"In-Reply-To: <late-parent@example.com>\r\n"
                b"References: <late-root@example.com> <late-parent@example.com>\r\n"
                b"\r\nfile reply body\r\n"
            )
            imported = await _import_single_eml(
                session,
                eml_path=eml_path,
                display_filename=eml_path.name,
                user_id=owner,
                organization_id=organization,
            )
            assert imported.status == "imported"
            file_reply = (
                await session.execute(
                    select(Email).where(
                        *Email.owner_filters(owner, organization),
                        Email.message_id == "file-reply@example.com",
                    )
                )
            ).scalar_one()
            assert file_reply.thread_id == "late-root@example.com"
            assert (
                await detach_email_from_thread(
                    session,
                    email_id=file_reply.id,
                    user_id=owner,
                    organization_id=organization,
                    reason="Incorrect relationship",
                )
                == 1
            )
            repeated = await _import_single_eml(
                session,
                eml_path=eml_path,
                display_filename=eml_path.name,
                user_id=owner,
                organization_id=organization,
            )
            assert repeated.status == "skipped_duplicate"
            assert file_reply.thread_id == "file-reply@example.com"
            file_edges = (
                (
                    await session.execute(
                        select(EmailThreadEvidenceRecord).where(
                            EmailThreadEvidenceRecord.source_email_id == file_reply.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(file_edges) == 3
            assert all(
                edge.detached_at is not None
                and edge.detached_by == owner
                and edge.detach_reason == "Incorrect relationship"
                for edge in file_edges
            )

            await session.delete(file_reply)
            await session.flush()
            await session.execute(
                delete(Email).where(Email.user_id.in_((owner, other)))
            )
            await session.commit()
    finally:
        await engine.dispose()
