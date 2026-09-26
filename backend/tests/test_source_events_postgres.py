"""Verify calendar evidence persists with its email owner's boundary."""

import datetime
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Base, SourceEventRecord
from services.email_import_service import _build_email_object


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_calendar_source_event_persists_with_owner_and_citations():
    schema = f"e1_source_event_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)

        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
            "UID:meeting@example.com\nDTSTART:20260927T100000Z\n"
            "DTEND:20260927T110000Z\nSUMMARY:Meeting\n"
            "END:VEVENT\nEND:VCALENDAR"
        )
        email, _ = _build_email_object(
            parsed={
                "message_id": "<meeting@example.com>",
                "sender": "sender@example.com",
                "recipients": "owner@example.com",
                "body": "See attached",
            },
            user_id="owner-a",
            organization_id="org-1",
            message_id="<meeting@example.com>",
            thread_id="meeting-thread",
            fingerprint="meeting-fingerprint",
            persisted_date=datetime.datetime(2026, 9, 27, tzinfo=datetime.timezone.utc),
            attachment_payloads=[
                {
                    "filename": "meeting.ics",
                    "content": "Calendar attachment",
                    "content_type": "text/calendar",
                    "parse_content": ics,
                    "parse_content_type": "text/calendar",
                    "parser_key": "calendar",
                    "parse_status": "parsed",
                }
            ],
            fitted_embeddings=[],
            owner_addresses=["owner@example.com"],
        )
        sessions = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with sessions() as session:
            session.add(email)
            await session.commit()
            owned = (
                await session.execute(
                    select(SourceEventRecord).where(
                        SourceEventRecord.user_id == "owner-a"
                    )
                )
            ).scalar_one()
            assert owned.email_id == email.id
            assert owned.visibility_scope == "organization"
            assert owned.source_event_key == "meeting@example.com"
            assert owned.source_segment_uids
            assert (
                await session.execute(
                    select(SourceEventRecord).where(
                        SourceEventRecord.user_id == "owner-b"
                    )
                )
            ).scalar_one_or_none() is None

            await session.delete(email)
            await session.commit()
            assert (
                await session.execute(select(SourceEventRecord))
            ).scalar_one_or_none() is None
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
