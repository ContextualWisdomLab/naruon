import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Base, ContentNodeRecord, Email, TicketTask
from services.email_parser import parse_eml_bytes
from services.imap_worker import process_fetched_email


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_self_note_rollback_and_same_message_across_owners():
    schema = f"e1_reference_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    parsed = parse_eml_bytes(
        b"From: owner@example.com\n"
        b"To: owner@example.com\n"
        b"Subject: Private note\n"
        b"Message-ID: <shared-message@example.com>\n\n"
        b"Remember the booking.\n"
    )
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)

        sessions = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with sessions() as session:
            email = await process_fetched_email(
                session, parsed, "owner-a", "org-1", ["owner@example.com"]
            )
            assert email.is_personal_reference is True
            assert (await session.execute(select(TicketTask))).scalar_one().related_email_id == email.id
            await session.rollback()

        async with sessions() as session:
            assert (await session.execute(select(Email))).scalars().all() == []
            assert (await session.execute(select(TicketTask))).scalars().all() == []
            for owner in ("owner-a", "owner-b"):
                await process_fetched_email(
                    session, parsed, owner, "org-1", ["owner@example.com"]
                )
            await session.commit()

        async with sessions() as session:
            emails = (await session.execute(select(Email))).scalars().all()
            nodes = (
                await session.execute(
                    select(ContentNodeRecord).where(
                        ContentNodeRecord.node_kind == "personal_reference"
                    )
                )
            ).scalars().all()
            tasks = (await session.execute(select(TicketTask))).scalars().all()
            assert {email.user_id for email in emails} == {"owner-a", "owner-b"}
            assert len(nodes) == len({node.content_node_uid for node in nodes}) == 2
            assert len(tasks) == 2
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
