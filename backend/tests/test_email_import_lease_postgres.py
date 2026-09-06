"""Real PostgreSQL lease lifecycle checks; run migrations before this module.

Scope identifiers and interruption controls are test instrumentation, not a
representative customer workload. No unavailable-database skip is permitted.
"""

import asyncio
import hashlib
from email import message_from_bytes, policy
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from alembic.script import ScriptDirectory
from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings
from db.models import Email
from db.session import get_db
from main import app
from scripts.migrate_db import alembic_config
from services import email_import_service
from services.llm_provider_selection import resolve_runtime_llm_provider
from tests.test_auth_real import _signed_session_token, _valid_session_payload

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def lease_database(monkeypatch, request):
    """Isolate the holder pool from the replica used to observe its real locks."""
    holder_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=getattr(request, "param", 1),
        max_overflow=0,
        pool_timeout=1,
    )
    observer_engine = create_async_engine(
        settings.DATABASE_URL, pool_size=1, max_overflow=0
    )
    owner_key = f"import_scope_{uuid4().hex}"
    captured_connections = []
    monkeypatch.setattr(email_import_service, "engine", holder_engine)
    try:
        async with observer_engine.connect() as observer_connection:
            assert (
                await observer_connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
                == ScriptDirectory.from_config(alembic_config()).get_current_head()
            )
        yield holder_engine, observer_engine, owner_key, captured_connections
    finally:
        # A RED test may intentionally expose a checked-out or pooled lease.
        for holder_connection in captured_connections:
            if not holder_connection.closed:
                await holder_connection.invalidate()
                await holder_connection.close()
        await holder_engine.dispose()
        await observer_engine.dispose()


@pytest.mark.parametrize("lease_database", [1, 2], indirect=True)
@pytest.mark.parametrize("provider_lookup_first", [False, True])
async def test_full_import_preserves_observed_mail_on_supported_pools(
    lease_database, provider_lookup_first
):
    """Run parsing, writes and duplicate detection without substituting import work."""
    holder_engine, observer_engine, owner_key, _ = lease_database
    constraint_failures = []

    def record_constraint_failure(exception_context):
        """Retain the constraint name, never SQL parameters or source contents."""
        original_error = exception_context.original_exception
        constraint_failures.append(
            getattr(
                original_error.__cause__,
                "constraint_name",
                type(original_error).__name__,
            )
        )

    event.listen(holder_engine.sync_engine, "handle_error", record_constraint_failure)
    source_bytes = (
        Path(__file__).parent / "fixtures" / "observed_queue_question.eml"
    ).read_bytes()
    source_message = message_from_bytes(source_bytes, policy=policy.default)
    upload_records = [
        email_import_service.EmailImportUpload(
            filename="observed_queue_question.eml", content=source_bytes
        )
    ]
    async with async_sessionmaker(
        holder_engine, expire_on_commit=False
    )() as database_session:
        if provider_lookup_first:
            assert (
                await resolve_runtime_llm_provider(
                    database_session, user_id=owner_key, organization_id=owner_key
                )
                is None
            )
        for expected_imports, expected_duplicates in ((1, 0), (0, 1)):
            import_result = await email_import_service.import_email_uploads(
                database_session,
                uploads=upload_records,
                user_id=owner_key,
                organization_id=owner_key,
            )
            assert import_result.failed_count == 0, constraint_failures
            assert import_result.imported_count == expected_imports
            assert import_result.skipped_count == expected_duplicates
    async with observer_engine.connect() as observer_connection:
        persisted_records = (
            await observer_connection.execute(
                select(Email.body, Email.is_read, Email.message_id).where(
                    *Email.owner_filters(owner_key, owner_key)
                )
            )
        ).all()
    assert len(persisted_records) == 1
    persisted_record = persisted_records[0]
    assert persisted_record.body.strip() == source_message.get_content().strip()
    assert persisted_record.is_read is True
    assert persisted_record.message_id == source_message["Message-ID"].strip("<>")
    assert await _replica_can_import(observer_engine, owner_key) is True
    assert holder_engine.pool.checkedout() == 0


async def test_signed_import_route_persists_observed_source(lease_database, monkeypatch):
    """Exercise real backend signature verification, provider lookup and SQL writes."""
    holder_engine, observer_engine, owner_key, _ = lease_database
    from api.auth import get_auth_context, get_current_user

    assert get_auth_context not in app.dependency_overrides
    assert get_current_user not in app.dependency_overrides

    async def isolated_database_session():
        """Replace only the database location, retaining a real one-slot session."""
        async with async_sessionmaker(
            holder_engine, expire_on_commit=False
        )() as database_session:
            yield database_session

    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_database_session)
    source_bytes = (
        Path(__file__).parent / "fixtures" / "observed_queue_question.eml"
    ).read_bytes()
    session_token = _signed_session_token(
        _valid_session_payload(sub=owner_key, org=owner_key, workspace=owner_key)
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        unsigned_response = await api_client.post(
            "/api/emails/import-files",
            files={"files": ("observed_queue_question.eml", source_bytes, "message/rfc822")},
        )
        assert unsigned_response.status_code == 401
        for imported_count, skipped_count in ((1, 0), (0, 1)):
            signed_response = await api_client.post(
                "/api/emails/import-files",
                headers={"Authorization": f"Bearer {session_token}"},
                files={
                    "files": ("observed_queue_question.eml", source_bytes, "message/rfc822")
                },
            )
            assert signed_response.status_code == 200
            response_data = signed_response.json()
            assert response_data["imported_count"] == imported_count
            assert response_data["skipped_count"] == skipped_count
            assert response_data["failed_count"] == 0
            assert response_data["provider_write_executed"] is False
    async with observer_engine.connect() as observer_connection:
        stored_bodies = (
            await observer_connection.execute(
                select(Email.body).where(
                    Email.user_id == owner_key, Email.organization_id == owner_key
                )
            )
        ).scalars().all()
    assert stored_bodies == [
        message_from_bytes(source_bytes, policy=policy.default).get_content().strip()
    ]
    assert await _replica_can_import(observer_engine, owner_key) is True
    assert holder_engine.pool.checkedout() == 0


@pytest.mark.parametrize("lease_database", [2], indirect=True)
@pytest.mark.parametrize("scope_relation", ["same_owner", "other_user", "other_org"])
async def test_concurrent_imports_preserve_scope_after_provider_lookup(
    lease_database, scope_relation
):
    """Both requests retain a lookup transaction; neither needs a third pool slot."""
    holder_engine, observer_engine, owner_key, _ = lease_database
    owner_scopes = [
        (owner_key, owner_key),
        (
            owner_key + "_other" if scope_relation == "other_user" else owner_key,
            owner_key + "_other" if scope_relation == "other_org" else owner_key,
        ),
    ]
    source_bytes = (
        Path(__file__).parent / "fixtures" / "observed_queue_question.eml"
    ).read_bytes()
    lookup_barrier = asyncio.Barrier(2)

    async def import_for_scope(user_key, organization_key):
        """Use the actual API's provider lookup before competing for the lease."""
        async with async_sessionmaker(
            holder_engine, expire_on_commit=False
        )() as database_session:
            assert (
                await resolve_runtime_llm_provider(
                    database_session,
                    user_id=user_key,
                    organization_id=organization_key,
                )
                is None
            )
            await lookup_barrier.wait()
            return await email_import_service.import_email_uploads(
                database_session,
                uploads=[
                    email_import_service.EmailImportUpload(
                        filename="observed_queue_question.eml", content=source_bytes
                    )
                ],
                user_id=user_key,
                organization_id=organization_key,
            )

    import_tasks = [
        asyncio.create_task(import_for_scope(*owner_scope)) for owner_scope in owner_scopes
    ]
    try:
        import_results = await asyncio.wait_for(asyncio.gather(*import_tasks), 15)
        observed_counts = sorted(
            (result.imported_count, result.skipped_count, result.failed_count)
            for result in import_results
        )
        assert observed_counts == (
            [(0, 1, 0), (1, 0, 0)]
            if scope_relation == "same_owner"
            else [(1, 0, 0), (1, 0, 0)]
        )
    finally:
        for import_task in import_tasks:
            import_task.cancel()
        await asyncio.gather(*import_tasks, return_exceptions=True)

    for user_key, organization_key in set(owner_scopes):
        async with observer_engine.connect() as observer_connection:
            stored_bodies = (
                await observer_connection.execute(
                    select(Email.body).where(
                        Email.user_id == user_key,
                        Email.organization_id == organization_key,
                    )
                )
            ).scalars().all()
        assert len(stored_bodies) == 1
        assert stored_bodies[0].strip() == message_from_bytes(
            source_bytes, policy=policy.default
        ).get_content().strip()
        assert await _replica_can_import(
            observer_engine, user_key, organization_key
        ) is True
    assert holder_engine.pool.checkedout() == 0


async def _replica_can_import(observer_engine, owner_key, organization_key=None):
    """Try the externally specified owner key, then undo only our own probe."""
    lock_parameters = {
        "namespace_key": "naruon-email-import-quota",
        "owner_key": hashlib.sha256(
            owner_key.encode()
            + b"\x00"
            + (organization_key if organization_key is not None else owner_key).encode()
        ).hexdigest(),
    }
    async with observer_engine.connect() as observer_connection:
        acquired_lock = await observer_connection.scalar(
            text(
                "SELECT pg_try_advisory_lock(hashtext(:namespace_key), hashtext(:owner_key))"
            ),
            lock_parameters,
        )
        if acquired_lock:
            assert (
                await observer_connection.scalar(
                    text(
                        "SELECT pg_advisory_unlock(hashtext(:namespace_key), hashtext(:owner_key))"
                    ),
                    lock_parameters,
                )
                is True
            )
        return acquired_lock


@pytest.mark.parametrize(
    "interruption_kind", ["cancel_after_commit", "connection_loss"]
)
async def test_committed_import_keeps_source_but_stops_after_interruption(
    lease_database, monkeypatch, interruption_kind
):
    """Cancel real work or terminate its backend; no unleased query may follow."""
    holder_engine, observer_engine, owner_key, _ = lease_database
    source_bytes = (
        Path(__file__).parent / "fixtures" / "observed_queue_question.eml"
    ).read_bytes()
    upload_record = email_import_service.EmailImportUpload(
        filename="observed_queue_question.eml", content=source_bytes
    )
    item_committed = asyncio.Event()
    finish_projection = asyncio.Event()
    disconnected_queries = []
    project_import = email_import_service._persist_project_graph_projection

    async def interrupt_projection(
        database_session, *projection_args, **projection_kwargs
    ):
        """Run the real post-commit hook, then interrupt only this test's backend."""
        await project_import(database_session, *projection_args, **projection_kwargs)
        if interruption_kind == "connection_loss":
            holder_connection = database_session.bind
            backend_pid = await database_session.scalar(text("SELECT pg_backend_pid()"))
            async with observer_engine.connect() as observer_connection:
                assert (
                    await observer_connection.scalar(
                        text("SELECT pg_terminate_backend(:backend_pid)"),
                        {"backend_pid": backend_pid},
                    )
                    is True
                )
            with pytest.raises(DBAPIError):
                await database_session.scalar(text("SELECT 1"))
            await database_session.rollback()
            assert holder_connection.invalidated

            def record_disconnected_query(*query_args):
                """Count SQL attempts without storing source contents or parameters."""
                disconnected_queries.append(True)

            event.listen(
                holder_connection.sync_connection,
                "before_cursor_execute",
                record_disconnected_query,
            )
        item_committed.set()
        await finish_projection.wait()

    monkeypatch.setattr(
        email_import_service, "_persist_project_graph_projection", interrupt_projection
    )
    async with async_sessionmaker(
        holder_engine, expire_on_commit=False
    )() as database_session:
        import_task = asyncio.create_task(
            email_import_service.import_email_uploads(
                database_session,
                uploads=[upload_record, upload_record],
                user_id=owner_key,
                organization_id=owner_key,
            )
        )
        try:
            await asyncio.wait_for(item_committed.wait(), 5)
            if interruption_kind == "cancel_after_commit":
                assert await _replica_can_import(observer_engine, owner_key) is False
                import_task.cancel()
                expected_error = asyncio.CancelledError
            else:
                assert await _replica_can_import(observer_engine, owner_key) is True
                finish_projection.set()
                expected_error = RuntimeError
            with pytest.raises(expected_error):
                await import_task
            assert disconnected_queries == []
            assert await _replica_can_import(observer_engine, owner_key) is True
            assert holder_engine.pool.checkedout() == 0
        finally:
            import_task.cancel()
            await asyncio.gather(import_task, return_exceptions=True)
    async with observer_engine.connect() as observer_connection:
        retained_body = await observer_connection.scalar(
            select(Email.body).where(*Email.owner_filters(owner_key, owner_key))
        )
    assert (
        retained_body.strip()
        == message_from_bytes(source_bytes, policy=policy.default).get_content().strip()
    )


async def test_acquisition_cancellation_does_not_strand_holder(
    lease_database, monkeypatch
):
    """Cancellation after server acquisition must release the pool slot and lease."""
    holder_engine, observer_engine, owner_key, captured_connections = lease_database
    lease_acquired = asyncio.Event()
    acknowledge_lease = asyncio.Event()
    execute_query = AsyncConnection.execute

    async def pause_after_acquisition(
        database_connection, statement, *query_args, **query_kwargs
    ):
        """Keep the real lock query, pause only before acknowledging its result."""
        query_result = await execute_query(
            database_connection, statement, *query_args, **query_kwargs
        )
        if "pg_advisory_lock(" in str(statement):
            captured_connections.append(database_connection)
            lease_acquired.set()
            await acknowledge_lease.wait()
        return query_result

    monkeypatch.setattr(AsyncConnection, "execute", pause_after_acquisition)
    async with async_sessionmaker(holder_engine)() as database_session:
        acquire_task = asyncio.create_task(
            email_import_service._acquire_owner_import_quota_lock(
                database_session, user_id=owner_key, organization_id=owner_key
            )
        )
        try:
            await asyncio.wait_for(lease_acquired.wait(), 5)
            assert await _replica_can_import(observer_engine, owner_key) is False
            acquire_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await acquire_task
            assert await _replica_can_import(observer_engine, owner_key) is True
            assert holder_engine.pool.checkedout() == 0
        finally:
            acquire_task.cancel()
            await asyncio.gather(acquire_task, return_exceptions=True)


@pytest.mark.parametrize(
    "release_case",
    ["query_failure", "query_cancel", "repeated_cancel", "unconfirmed_unlock"],
)
async def test_uncertain_release_discards_physical_holder(
    lease_database, monkeypatch, release_case
):
    """A failed, interrupted or false unlock cannot return a leased socket to the pool."""
    holder_engine, observer_engine, owner_key, captured_connections = lease_database
    release_entered = asyncio.Event()
    allow_release = asyncio.Event()
    invalidation_entered = asyncio.Event()
    allow_invalidation = asyncio.Event()
    execute_query = AsyncConnection.execute
    invalidate_connection = AsyncConnection.invalidate
    async with async_sessionmaker(holder_engine)() as database_session:
        holder_connection = await email_import_service._acquire_owner_import_quota_lock(
            database_session, user_id=owner_key, organization_id=owner_key
        )
        captured_connections.append(holder_connection)
        assert await _replica_can_import(observer_engine, owner_key) is False

        async def interrupt_release(
            database_connection, statement, *query_args, **query_kwargs
        ):
            """Inject failure before only this holder's real release query."""
            if (
                database_connection is holder_connection
                and "pg_advisory_unlock(" in str(statement)
            ):
                if release_case == "query_failure":
                    raise RuntimeError("injected release failure")
                if release_case in {"query_cancel", "repeated_cancel"}:
                    release_entered.set()
                    await allow_release.wait()
            return await execute_query(
                database_connection, statement, *query_args, **query_kwargs
            )

        async def pause_invalidation(
            database_connection, *connection_args, **connection_kwargs
        ):
            """Expose a second actual cancellation while the holder is being discarded."""
            if (
                database_connection is holder_connection
                and release_case == "repeated_cancel"
            ):
                invalidation_entered.set()
                await allow_invalidation.wait()
            return await invalidate_connection(
                database_connection, *connection_args, **connection_kwargs
            )

        monkeypatch.setattr(AsyncConnection, "execute", interrupt_release)
        monkeypatch.setattr(AsyncConnection, "invalidate", pause_invalidation)
        release_task = asyncio.create_task(
            email_import_service._release_owner_import_quota_lock(
                database_session,
                user_id=owner_key,
                organization_id=owner_key + "_other"
                if release_case == "unconfirmed_unlock"
                else owner_key,
                lock=holder_connection,
            )
        )
        try:
            if release_case in {"query_cancel", "repeated_cancel"}:
                await asyncio.wait_for(release_entered.wait(), 5)
                release_task.cancel()
            if release_case == "repeated_cancel":
                await asyncio.wait_for(invalidation_entered.wait(), 5)
                release_task.cancel()
                allow_invalidation.set()
            expected_error = (
                asyncio.CancelledError
                if release_case in {"query_cancel", "repeated_cancel"}
                else RuntimeError
            )
            with pytest.raises(expected_error):
                await release_task
            assert await _replica_can_import(observer_engine, owner_key) is True
            assert holder_engine.pool.checkedout() == 0
        finally:
            allow_invalidation.set()
            release_task.cancel()
            await asyncio.gather(release_task, return_exceptions=True)
