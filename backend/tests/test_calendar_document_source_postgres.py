"""Exercise authenticated calendar files as independent event evidence."""

import datetime
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.events import (
    CalendarSourceUploadRequest,
    EventRelationCorrectionRequest,
    correct_event_relation,
    delete_calendar_source,
    download_calendar_source,
    list_calendar_sources,
    list_event_conflicts,
    list_event_relations,
    reconcile_event_relations,
    upload_calendar_source,
)
from core.config import settings
from db.models import (
    Base,
    CalendarSourceDocumentRecord,
    EventRelationCorrectionRecord,
    EventRelationRecord,
    SourceEventRecord,
)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_calendar_document_relations_keep_source_and_owner_boundary():
    schema = f"e1_calendar_document_{uuid.uuid4().hex[:12]}"
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
        sessions = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with sessions() as session:
            owner = AuthContext(
                user_id="owner-a",
                organization_id="org-1",
                workspace_id="workspace-org-1",
                role="member",
                group_ids=(),
            )
            other_owner = AuthContext(
                user_id="owner-b",
                organization_id="org-1",
                workspace_id="workspace-org-1",
                role="member",
                group_ids=(),
            )
            other_workspace = AuthContext(
                user_id="owner-a",
                organization_id="org-1",
                workspace_id="workspace-other",
                role="member",
                group_ids=(),
            )

            def ics(uid: str, start: str, end: str) -> str:
                return (
                    "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
                    f"UID:{uid}\nDTSTART:{start}\nDTEND:{end}\n"
                    f"SUMMARY:{uid}\nEND:VEVENT\nEND:VCALENDAR"
                )

            first_ics = ics("first@example.com", "20260927T100000Z", "20260927T110000Z")
            first = await upload_calendar_source(
                CalendarSourceUploadRequest(
                    ics_text=first_ics, visibility_scope="organization"
                ),
                owner,
                session,
            )
            second = await upload_calendar_source(
                CalendarSourceUploadRequest(
                    ics_text=ics(
                        "second@example.com", "20260927T103000Z", "20260927T113000Z"
                    ),
                    visibility_scope="organization",
                ),
                owner,
                session,
            )
            assert len(first) == len(second) == 1
            assert first[0].email_id is None
            assert first[0].document_id
            assert any(
                citation.label == "시작" and "20260927T100000Z" in citation.excerpt
                for citation in first[0].citations
            )
            source = await download_calendar_source(
                first[0].document_id, owner, session
            )
            assert source.body.decode() == first_ics
            assert source.headers["cache-control"] == "private, no-store"

            progress = await reconcile_event_relations("organization", owner, session)
            assert progress.processed_conflicts == 1
            relations = (
                await list_event_relations("organization", owner, session)
            ).items
            assert len(relations) == 1
            assert {
                relations[0].source.document_id,
                relations[0].target.document_id,
            } == {
                first[0].document_id,
                second[0].document_id,
            }
            assert all(
                event.citations for event in (relations[0].source, relations[0].target)
            )
            await correct_event_relation(
                relations[0].relation_uid,
                EventRelationCorrectionRequest(relation_type="unrelated"),
                "organization",
                owner,
                session,
            )
            assert (
                await list_event_conflicts("organization", other_owner, session)
            ).items == []
            with pytest.raises(HTTPException) as denied:
                await download_calendar_source(
                    first[0].document_id, other_owner, session
                )
            assert denied.value.status_code == 404
            with pytest.raises(HTTPException) as denied:
                await download_calendar_source(
                    first[0].document_id, other_workspace, session
                )
            assert denied.value.status_code == 404

            with pytest.raises(HTTPException) as invalid:
                await upload_calendar_source(
                    CalendarSourceUploadRequest(
                        ics_text="not a calendar", visibility_scope="personal"
                    ),
                    owner,
                    session,
                )
            assert invalid.value.status_code == 422

            assert (
                len(
                    (await session.execute(select(CalendarSourceDocumentRecord)))
                    .scalars()
                    .all()
                )
                == 2
            )
            assert (
                len((await session.execute(select(SourceEventRecord))).scalars().all())
                == 2
            )
            listing = await list_calendar_sources(None, owner, session)
            assert {item.document_id for item in listing.items} == {
                first[0].document_id,
                second[0].document_id,
            }
            assert listing.next_cursor is None
            assert (await list_calendar_sources(None, other_owner, session)).items == []
            with pytest.raises(HTTPException) as denied:
                await delete_calendar_source(first[0].document_id, other_owner, session)
            assert denied.value.status_code == 404
            await delete_calendar_source(first[0].document_id, owner, session)
            assert (
                len((await session.execute(select(SourceEventRecord))).scalars().all())
                == 1
            )
            assert (
                await session.execute(select(EventRelationRecord))
            ).scalar_one_or_none() is None
            assert (
                await session.execute(select(EventRelationCorrectionRecord))
            ).scalar_one_or_none() is None
            with pytest.raises(HTTPException) as removed:
                await download_calendar_source(first[0].document_id, owner, session)
            assert removed.value.status_code == 404

            session.add_all(
                CalendarSourceDocumentRecord(
                    user_id=owner.user_id,
                    organization_id=owner.organization_id,
                    workspace_id=owner.workspace_id,
                    visibility_scope="personal",
                    content=first_ics,
                )
                for _ in range(20)
            )
            await session.commit()
            first_page = await list_calendar_sources(None, owner, session)
            assert len(first_page.items) == 20
            assert first_page.next_cursor is not None
            second_page = await list_calendar_sources(
                first_page.next_cursor, owner, session
            )
            assert len(second_page.items) == 1
            assert second_page.next_cursor is None

            start = datetime.datetime(2026, 10, 1, 10, tzinfo=datetime.timezone.utc)

            def vevent(
                uid: str, begins: datetime.datetime, ends: datetime.datetime
            ) -> str:
                return (
                    "BEGIN:VEVENT\n"
                    f"UID:{uid}\nDTSTART:{begins:%Y%m%dT%H%M%SZ}\n"
                    f"DTEND:{ends:%Y%m%dT%H%M%SZ}\nSUMMARY:{uid}\nEND:VEVENT\n"
                )

            bulk_ics = (
                "BEGIN:VCALENDAR\nVERSION:2.0\n"
                + vevent("long@example.com", start, start + datetime.timedelta(hours=2))
                + "".join(
                    vevent(
                        f"short-{index}@example.com",
                        start + datetime.timedelta(minutes=index),
                        start + datetime.timedelta(minutes=index + 1),
                    )
                    for index in range(101)
                )
                + "END:VCALENDAR"
            )
            await upload_calendar_source(
                CalendarSourceUploadRequest(
                    ics_text=bulk_ics, visibility_scope="organization"
                ),
                owner,
                session,
            )
            overlaps_one = await list_event_conflicts("organization", owner, session)
            assert len(overlaps_one.items) == 100
            assert overlaps_one.next_cursor is not None
            overlaps_two = await list_event_conflicts(
                "organization", owner, session, overlaps_one.next_cursor
            )
            assert len(overlaps_two.items) == 1
            assert overlaps_two.next_cursor is None
            with pytest.raises(HTTPException) as invalid_cursor:
                await list_event_conflicts("organization", owner, session, "bad")
            assert invalid_cursor.value.status_code == 422
            assert (
                len(
                    {
                        (item.source_event_uid, item.target_event_uid)
                        for item in (*overlaps_one.items, *overlaps_two.items)
                    }
                )
                == 101
            )
            progress_one = await reconcile_event_relations(
                "organization", owner, session
            )
            progress_two = await reconcile_event_relations(
                "organization", owner, session, progress_one.next_cursor
            )
            assert (
                progress_one.processed_conflicts,
                progress_two.processed_conflicts,
            ) == (100, 1)
            assert progress_two.next_cursor is None
            relations_one = await list_event_relations("organization", owner, session)
            relations_two = await list_event_relations(
                "organization", owner, session, relations_one.next_cursor
            )
            assert (len(relations_one.items), len(relations_two.items)) == (100, 1)
            assert relations_two.next_cursor is None
            with pytest.raises(HTTPException) as invalid_cursor:
                await list_event_relations("organization", owner, session, "bad")
            assert invalid_cursor.value.status_code == 422
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
