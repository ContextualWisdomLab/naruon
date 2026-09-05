"""PostgreSQL regression coverage for read-state and search-storage repairs.

String-matching the revision file's source (test_alembic_migrations.py)
cannot detect a destructive downgrade or prove the upgrade is actually
idempotent -- both require running the real migration against a real
database in each of the shapes it must handle.
"""

import hashlib
import secrets
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest
from asyncpg.exceptions import InvalidAuthorizationSpecificationError, InvalidPasswordError
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    ProjectGraphObjectRecord,
    ProvenanceIdentityMapping,
)

pytestmark = pytest.mark.postgres

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PRE_READ_STATE_REVISION = "0009_project_graph_projection"


def _run_migrations(database_url: str, revision: str = "head") -> None:
    result = subprocess.run(
        [sys.executable, str(_BACKEND_ROOT / "scripts" / "migrate_db.py"), revision],
        cwd=_BACKEND_ROOT,
        env={
            "DATABASE_URL": database_url,
            "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
        },
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"scripts/migrate_db.py {revision} failed "
        f"(exit {result.returncode}):\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not any(
        status in result.stdout + result.stderr
        for status in ("Timeout", "Fatal", "Warn", "Denied")
    )


def _run_downgrade(database_url: str, revision: str) -> None:
    # scripts/migrate_db.py only wraps alembic's upgrade command; reuse its
    # alembic_config() but call command.downgrade() directly for this test.
    script = (
        "from scripts.migrate_db import alembic_config\n"
        "from alembic import command\n"
        f"command.downgrade(alembic_config(), {revision!r})\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_BACKEND_ROOT,
        env={
            "DATABASE_URL": database_url,
            "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
        },
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"alembic downgrade {revision} failed "
        f"(exit {result.returncode}):\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not any(
        status in result.stdout + result.stderr
        for status in ("Timeout", "Fatal", "Warn", "Denied")
    )


@pytest.fixture
def fresh_database_url():
    base_url = make_url(settings.DATABASE_URL)
    database_name = f"test_email_read_state_{uuid.uuid4().hex[:12]}"

    async def admin(sql: str) -> None:
        connection = await asyncpg.connect(
            host=base_url.host,
            port=base_url.port,
            user=base_url.username,
            password=base_url.password,
            database="postgres",
        )
        try:
            await connection.execute(sql)
        finally:
            await connection.close()

    import asyncio

    try:
        asyncio.run(admin(f'CREATE DATABASE "{database_name}"'))
    except (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
        OSError,
        ConnectionError,
    ) as exc:
        pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")

    try:
        yield base_url.set(database=database_name).render_as_string(hide_password=False)
    finally:
        asyncio.run(admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))


async def _column_exists(database_url: str, table_name: str, column_name: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :table_name AND column_name = :column_name"
                ),
                {"table_name": table_name, "column_name": column_name},
            )
            return result.first() is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_adds_is_read_to_a_historical_email_records_table(
    fresh_database_url,
):
    """A database whose own 0001 ran before is_read existed in the Email
    model has email_records without the column; upgrading to head must add
    it, not silently leave it missing."""
    _run_migrations(fresh_database_url, revision=_PRE_READ_STATE_REVISION)

    engine = create_async_engine(fresh_database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE email_records DROP COLUMN IF EXISTS is_read")
            )
    finally:
        await engine.dispose()

    assert await _column_exists(fresh_database_url, "email_records", "is_read") is False

    _run_migrations(fresh_database_url)

    assert await _column_exists(fresh_database_url, "email_records", "is_read") is True


@pytest.mark.parametrize(
    "starting_revision",
    [
        "base",
        "0017_merge_newsdom_carddav_heads",
        "0018_provenance_identity",
        "0019_email_read_state_repair",
    ],
)
@pytest.mark.asyncio
async def test_provenance_upgrade_and_rollback_preserve_portable_identity(
    fresh_database_url, starting_revision
):
    """Catch ambiguous heads, skipped table creation, and destructive rollback."""
    mapping_table = ProvenanceIdentityMapping.__table__
    engine = create_async_engine(fresh_database_url)
    try:
        if starting_revision != "base":
            _run_migrations(fresh_database_url, starting_revision)
            if starting_revision != "0018_provenance_identity":
                # Historical bootstrap predates this model. Force the incremental
                # create-table path, not a pass from today's Base.create_all().
                async with engine.begin() as connection:
                    await connection.run_sync(
                        lambda sync_conn: mapping_table.drop(sync_conn, checkfirst=True)
                    )

        _run_migrations(fresh_database_url)
        async with engine.begin() as connection:
            assert list(
                await connection.scalars(text("SELECT version_num FROM alembic_version"))
            ) == ["0021_merge_provenance_workspace"]
            await connection.execute(
                mapping_table.insert().values(
                    target_user_id="restore_target_user",
                    target_organization_id="restore_target_org",
                    target_workspace_id="restore_target_workspace",
                    source_user_uid="0" * 64,
                    source_organization_uid="restore_source_org",
                    source_workspace_uid="restore_source_workspace",
                    entity_kind="project_objects",
                    portable_uid="restore_source_object",
                    target_database_uid="restore_target_object",
                )
            )

        _run_migrations(fresh_database_url)
        _run_downgrade(fresh_database_url, "0017_merge_newsdom_carddav_heads")
        async with engine.connect() as connection:
            assert await connection.run_sync(
                lambda sync_conn: inspect(sync_conn).has_table(mapping_table.name)
            ), "rollback destroyed imported portable-identity mappings"
            assert (
                await connection.execute(
                    select(mapping_table.c.portable_uid, mapping_table.c.target_database_uid)
                )
            ).all() == [("restore_source_object", "restore_target_object")]

        _run_migrations(fresh_database_url)
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    select(mapping_table.c.portable_uid, mapping_table.c.target_database_uid)
                )
            ).all() == [("restore_source_object", "restore_target_object")]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_is_idempotent_against_a_legacy_emails_table_with_is_read(
    fresh_database_url,
):
    """A legacy "emails" table that already has is_read (e.g. from a partial
    earlier application) must not make upgrade() crash with a
    duplicate-column error."""
    _run_migrations(fresh_database_url, revision=_PRE_READ_STATE_REVISION)

    engine = create_async_engine(fresh_database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE emails "
                    "(id serial primary key, is_read boolean not null default true)"
                )
            )
    finally:
        await engine.dispose()

    _run_migrations(fresh_database_url)


@pytest.mark.asyncio
async def test_downgrade_does_not_destroy_read_state_on_a_fresh_database(
    fresh_database_url,
):
    """A fresh database's email_records.is_read comes from 0001's live
    create_all, not from 0011_email_read_state -- downgrading past 0011 must
    not drop it (and, if it did, would destroy real per-message read/unread
    state along with it)."""
    _run_migrations(fresh_database_url)
    assert await _column_exists(fresh_database_url, "email_records", "is_read") is True

    _run_downgrade(fresh_database_url, _PRE_READ_STATE_REVISION)

    assert await _column_exists(fresh_database_url, "email_records", "is_read") is True


@pytest.mark.asyncio
async def test_upgrade_head_repairs_a_database_already_stamped_past_0011(
    fresh_database_url,
):
    """Alembic never re-runs a revision's upgrade() once that revision id is
    recorded as applied -- editing 0011_email_read_state.py cannot repair a
    database whose alembic_version history already includes it but is
    missing is_read regardless (e.g. an earlier broken version of that
    revision, a partial apply, manual intervention). 0019_email_read_state_
    repair is the real fix: it must add the column even though the database
    is already stamped through 0018 with 0011 long since applied, so only
    0019 itself -- not a re-run of 0011 -- is what's left to bring it to
    head."""
    _run_migrations(fresh_database_url, revision="0018_workspace_registry")
    assert await _column_exists(fresh_database_url, "email_records", "is_read") is True

    engine = create_async_engine(fresh_database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE email_records DROP COLUMN IF EXISTS is_read")
            )
    finally:
        await engine.dispose()

    assert await _column_exists(fresh_database_url, "email_records", "is_read") is False

    _run_migrations(fresh_database_url)

    assert await _column_exists(fresh_database_url, "email_records", "is_read") is True


def _search_storage_rows(record_suffix: str):
    """Build related historical records using the production mapper dependencies."""
    message_id = f"<search-storage-{record_suffix}@example.com>"
    content_hash = hashlib.sha256(b"historical quartz").hexdigest()
    email = Email(
        user_id="search-storage-user",
        organization_id="search-storage-org",
        message_id=message_id,
        sender="sender@example.com",
        subject="historical",
        body="quartz",
        date=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )
    attachment = Attachment(
        email=email,
        filename=f"search-storage-{record_suffix}.txt",
        content="historical quartz",
    )
    node = ContentNodeRecord(
        email=email,
        content_node_uid=f"search-node-{record_suffix}",
        source_kind="email_body",
        source_record_uid=message_id,
        node_kind="document",
        node_path="/document[1]",
        ordinal_index=0,
        safe_text_content="historical quartz",
        content_hash=content_hash,
    )
    segment = ContentSegmentRecord(
        email=email,
        content_node=node,
        content_segment_uid=f"search-segment-{record_suffix}",
        source_kind="email_body",
        source_record_uid=message_id,
        segment_kind="paragraph",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=0,
        safe_text_content="historical quartz",
        content_hash=content_hash,
        word_count=2,
    )
    project_object = ProjectGraphObjectRecord(
        email=email,
        primary_content_segment=segment,
        object_uid=f"search-project-{record_suffix}",
        user_id=email.user_id,
        organization_id=email.organization_id,
        workspace_id="workspace-search-storage-org",
        object_type="requirement",
        title="historical",
        summary="quartz",
        confidence=0.9,
        source_segment_uids=[segment.content_segment_uid],
        extractor_name="deterministic_reference",
        extractor_version="test",
    )
    return {
        "email_records": email,
        "email_attachments": attachment,
        "content_segments": segment,
        "project_graph_objects": project_object,
    }


def _search_document_values(column_names, document: str):
    """Split a complete test document across a surface's real storage columns."""
    # The first SHA-256 word fits the project's 240-character title limit.
    parts = document.split(" ", 1) if len(column_names) == 2 else [document]
    values = dict(zip(column_names, parts, strict=True))
    if "safe_text_content" in values:
        values["content_hash"] = hashlib.sha256(document.encode()).hexdigest()
        values["word_count"] = len(document.split())
    return values


@pytest.mark.parametrize(
    ("surface", "column_names"),
    [
        ("email_records", ("subject", "body")),
        ("email_attachments", ("content",)),
        ("content_segments", ("safe_text_content",)),
        ("project_graph_objects", ("title", "summary")),
    ],
    ids=["email", "attachment", "segment", "project"],
)
@pytest.mark.asyncio
async def test_search_trigram_storage_forward_repair_preserves_large_documents(
    fresh_database_url,
    surface,
    column_names,
):
    """Catch whole-document index overflow and destructive index rollback."""
    _run_migrations(fresh_database_url, revision="0019_email_read_state_repair")
    engine = create_async_engine(fresh_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    historical_rows = _search_storage_rows("historical")
    model = type(historical_rows[surface])
    primary_key = inspect(model).primary_key[0]
    columns = [getattr(model, name) for name in column_names]
    search_document = columns[0]
    if len(columns) == 2:
        search_document = columns[0] + " " + columns[1]

    async def assert_document(row_id, expected: str, tail_query: str):
        """Verify complete stored bytes and the literal perfect tail-word score."""
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(
                        *columns,
                        func.word_similarity(
                            func.search_normalized_text(tail_query),
                            func.search_normalized_text(search_document),
                        ),
                    ).where(primary_key == row_id)
                )
            ).one()
        assert " ".join(row[:-1]) == expected
        # A complete final word has exactly the query's trigrams, so score = 1.
        assert row[-1] == 1.0

    try:
        async with session_factory.begin() as session:
            session.add_all(historical_rows.values())
            await session.flush()
            historical_id = inspect(historical_rows[surface]).identity[0]

        _run_migrations(fresh_database_url)
        await assert_document(historical_id, "historical quartz", "quartz")
        async with engine.connect() as connection:
            index_methods = list(
                await connection.scalars(
                    text(
                        "SELECT access_method.amname FROM pg_index AS index_entry "
                        "JOIN pg_class AS index_object ON index_object.oid = index_entry.indexrelid "
                        "JOIN pg_class AS table_object ON table_object.oid = index_entry.indrelid "
                        "JOIN pg_namespace AS table_schema ON table_schema.oid = table_object.relnamespace "
                        "JOIN pg_am AS access_method ON access_method.oid = index_object.relam "
                        "WHERE table_schema.nspname = 'public' AND table_object.relname = :table_name "
                        "AND index_object.relname LIKE '%_trgm' AND index_entry.indisvalid"
                    ),
                    {"table_name": surface},
                )
            )
        assert index_methods == ["gin"], "storage repair must retain a valid trigram index"

        documents = {}
        for tail_query in ("quartz", "zircon", "topaz"):
            # Distinct digests exercise diverse trigram keys, not repeated text;
            # the non-hex tail word occurs only beyond the 32 KiB boundary.
            prefix = " ".join(
                hashlib.sha256(f"{surface}:{tail_query}:{index}".encode()).hexdigest()
                for index in range(1024)
            )
            assert len(prefix.encode()) > 32 * 1024
            documents[tail_query] = f"{prefix} {tail_query}"

        inserted_rows = _search_storage_rows("inserted")
        for name, value in _search_document_values(
            column_names, documents["quartz"]
        ).items():
            setattr(inserted_rows[surface], name, value)
        async with session_factory.begin() as session:
            session.add_all(inserted_rows.values())
            await session.flush()
            inserted_id = inspect(inserted_rows[surface]).identity[0]
        await assert_document(inserted_id, documents["quartz"], "quartz")

        async with engine.begin() as connection:
            await connection.execute(
                update(model)
                .where(primary_key.in_([historical_id, inserted_id]))
                .values(_search_document_values(column_names, documents["zircon"]))
            )
        for row_id in (historical_id, inserted_id):
            await assert_document(row_id, documents["zircon"], "zircon")

        _run_migrations(fresh_database_url)
        for row_id in (historical_id, inserted_id):
            await assert_document(row_id, documents["zircon"], "zircon")

        _run_downgrade(fresh_database_url, "0019_email_read_state_repair")
        for row_id in (historical_id, inserted_id):
            await assert_document(row_id, documents["zircon"], "zircon")
        # Downgrade must retain the corrected indexes and their ability to accept
        # new large values, not reinstall the known failing GiST representation.
        async with engine.begin() as connection:
            await connection.execute(
                update(model)
                .where(primary_key.in_([historical_id, inserted_id]))
                .values(_search_document_values(column_names, documents["topaz"]))
            )
        for row_id in (historical_id, inserted_id):
            await assert_document(row_id, documents["topaz"], "topaz")

        _run_migrations(fresh_database_url)
        for row_id in (historical_id, inserted_id):
            await assert_document(row_id, documents["topaz"], "topaz")
    finally:
        await engine.dispose()
