"""Verify calendar evidence persists with its email owner's boundary."""

import datetime
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from api.auth import AuthContext
from api.events import list_event_conflicts
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

            def peer(uid: str, *, owner: str, visibility: str, workspace: str):
                return SourceEventRecord(
                    event_uid=uid,
                    user_id=owner,
                    organization_id="org-1",
                    workspace_id=workspace,
                    visibility_scope=visibility,
                    source_kind="calendar_fixture",
                    source_record_uid=uid,
                    source_event_key=uid,
                    event_type="calendar_event",
                    title="Another meeting",
                    status_code="confirmed",
                    starts_at=datetime.datetime(
                        2026, 9, 27, 10, 30, tzinfo=datetime.timezone.utc
                    ),
                    ends_at=datetime.datetime(
                        2026, 9, 27, 11, 30, tzinfo=datetime.timezone.utc
                    ),
                    source_segment_uids=[f"segment-{uid}"],
                )

            same_owner = peer(
                "event_same_owner",
                owner="owner-a",
                visibility="organization",
                workspace="workspace-org-1",
            )
            other_owner = peer(
                "event_other_owner",
                owner="owner-b",
                visibility="organization",
                workspace="workspace-org-1",
            )
            personal = peer(
                "event_personal",
                owner="owner-a",
                visibility="personal",
                workspace="workspace-org-1",
            )
            other_workspace = peer(
                "event_other_workspace",
                owner="owner-a",
                visibility="organization",
                workspace="workspace-other",
            )
            session.add_all([same_owner, other_owner, personal, other_workspace])
            await session.commit()
            auth = AuthContext(
                user_id="owner-a",
                organization_id="org-1",
                workspace_id="workspace-org-1",
                role="member",
                group_ids=(),
            )
            conflicts = await list_event_conflicts(
                visibility_scope="organization", auth_context=auth, db=session
            )
            assert len(conflicts) == 1
            assert conflicts[0].reason_code == "occupied_interval_overlap"
            assert {conflicts[0].source_event_uid, conflicts[0].target_event_uid} == {
                owned.event_uid,
                same_owner.event_uid,
            }
            assert owned.source_segment_uids in (
                conflicts[0].source_segment_uids,
                conflicts[0].target_segment_uids,
            )
            assert (
                await list_event_conflicts(
                    visibility_scope="personal", auth_context=auth, db=session
                )
                == []
            )

            await session.delete(email)
            for event in (same_owner, other_owner, personal, other_workspace):
                await session.delete(event)
            await session.commit()
            assert (
                await session.execute(select(SourceEventRecord))
            ).scalar_one_or_none() is None
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
