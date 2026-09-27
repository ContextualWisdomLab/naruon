import datetime
import base64
import asyncio
import hashlib
import uuid
from dataclasses import replace
from email.message import EmailMessage

import pytest
import pytest_asyncio
from fastapi import HTTPException
from asyncpg.exceptions import (
    InvalidAuthorizationSpecificationError,
    InvalidPasswordError,
)
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from api.auth import AuthContext
from api.emails import (
    get_attachment_facts,
    get_attachment_segment,
    get_attachment_segments,
    get_email_thread,
)
from db.models import (
    Attachment,
    Base,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
)
from services.project_graph import (
    ProjectObjectType,
    ProjectSemanticEdge,
    ProjectSemanticExtractionResult,
    ProjectSemanticObject,
    ProjectSourceSegment,
    apply_project_graph_correction,
    extract_project_semantics,
    persist_project_graph_projection,
)
from services.project_graph.extractors import extract_attachment_facts
import services.email_import_service as import_service
from services.newsdom_pdf_recognition import NewsdomRuntimeConfig
from services.newsdom_worker import NewsdomRecognitionWorker, process_pending_attachment
import services.newsdom_worker as newsdom_worker_module


@pytest_asyncio.fixture(scope="function")
async def project_graph_sessionmaker():
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


@pytest.mark.asyncio
async def test_project_graph_projection_persists_source_cited_objects_and_edges(
    project_graph_sessionmaker,
):
    user_id = f"project-user-{uuid.uuid4().hex}"
    organization_id = f"org-projection-{uuid.uuid4().hex[:12]}"
    workspace_id = f"workspace-{organization_id}"
    async with project_graph_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        extraction = extract_project_semantics([_source_segment(segment)])

        result = await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        await session.commit()

        # The deterministic reference extractor emits a REQUIREMENT and a
        # FEATURE for the seeded sentence; assert on the requirement and
        # its evidence edge specifically.
        assert len(result.objects) == 2
        assert len(result.edges) == 2
        assert sorted(obj.object_type for obj in result.objects) == [
            "feature",
            "requirement",
        ]
        persisted_object = next(
            obj for obj in result.objects if obj.object_type == "requirement"
        )
        persisted_edge = next(
            edge
            for edge in result.edges
            if edge.target_object_id == persisted_object.project_graph_object_id
        )
        assert persisted_object.user_id == user_id
        assert persisted_object.organization_id == organization_id
        assert persisted_object.workspace_id == workspace_id
        assert persisted_object.primary_content_segment_id == segment.content_segment_id
        assert persisted_object.source_segment_uids == [segment.content_segment_uid]
        assert persisted_object.attributes_json["source_record_uid"] == (
            segment.source_record_uid
        )
        assert (
            persisted_edge.target_object_id == persisted_object.project_graph_object_id
        )
        assert persisted_edge.source_uid == f"segment:{segment.content_segment_uid}"
        assert persisted_edge.source_segment_uids == [segment.content_segment_uid]


@pytest_asyncio.fixture(scope="function")
async def isolated_fact_sessionmaker():
    schema = f"attachment_fact_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
        execution_options={"schema_translate_map": {None: schema}},
    )
    schema_created = False
    try:
        try:
            async with admin_engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.execute(text(f"CREATE SCHEMA {schema}"))
                schema_created = True
            async with scoped_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except (
            InvalidAuthorizationSpecificationError,
            InvalidPasswordError,
            OperationalError,
            OSError,
        ) as exc:
            pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
        yield async_sessionmaker(scoped_engine, expire_on_commit=False)
    finally:
        await scoped_engine.dispose()
        if schema_created:
            async with admin_engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin_engine.dispose()


@pytest.mark.asyncio
async def test_attachment_segment_pages_keep_exact_owner_scoped_citations(
    isolated_fact_sessionmaker,
):
    user_id = f"segment-user-{uuid.uuid4().hex}"
    organization_id = f"org-segment-{uuid.uuid4().hex[:12]}"
    async with isolated_fact_sessionmaker() as session:
        seed = await _seed_source_segment(
            session, user_id=user_id, organization_id=organization_id
        )
        email = await session.get(Email, seed.email_id)
        attachment = Attachment(
            email_id=email.id, filename="invoice.txt", content="", parse_status="parsed"
        )
        session.add(attachment)
        await session.flush()
        node = ContentNodeRecord(
            content_node_uid=f"node-{uuid.uuid4().hex[:16]}",
            email_id=email.id,
            attachment_id=attachment.id,
            source_kind="attachment",
            source_record_uid=f"attachment:{attachment.id}",
            node_kind="document",
            node_path="/document[1]",
            ordinal_index=1,
            safe_text_content="",
            content_hash=uuid.uuid4().hex,
        )
        session.add(node)
        await session.flush()
        segment_uids = [f"seg-{uuid.uuid4().hex[:16]}" for _ in range(3)]
        for index, uid in enumerate(segment_uids, start=1):
            session.add(
                ContentSegmentRecord(
                    content_segment_uid=uid,
                    email_id=email.id,
                    attachment_id=attachment.id,
                    content_node_id=node.content_node_id,
                    source_kind="attachment",
                    source_record_uid=f"attachment:{attachment.id}",
                    segment_kind="paragraph",
                    segment_path=f"/document[1]/paragraph[{index}]",
                    ordinal_index=index,
                    safe_text_content=f"Invoice line {index}",
                    content_hash=uuid.uuid4().hex,
                    word_count=3,
                )
            )
        await session.commit()

        owner = AuthContext(
            user_id=user_id,
            role="member",
            organization_id=organization_id,
            group_ids=(),
            workspace_id=f"workspace-{organization_id}",
        )
        compact = await get_email_thread(
            email.thread_id, db=session, auth_context=owner
        )
        assert compact["thread"][0].attachment_evidence[0].segments == []

        first = await get_attachment_segments(
            attachment.id, limit=2, offset=0, db=session, auth_context=owner
        )
        assert [item.uid for item in first.segments] == segment_uids[:2]
        assert first.next_offset == 2
        second = await get_attachment_segments(
            attachment.id, limit=2, offset=2, db=session, auth_context=owner
        )
        assert [item.uid for item in second.segments] == segment_uids[2:]
        assert second.next_offset is None
        exact = await get_attachment_segment(
            attachment.id, segment_uids[2], db=session, auth_context=owner
        )
        assert exact.text == "Invoice line 3"

        other = AuthContext(
            user_id=f"other-{user_id}",
            role="member",
            organization_id=organization_id,
            group_ids=(),
            workspace_id=f"workspace-{organization_id}",
        )
        with pytest.raises(HTTPException) as denied:
            await get_attachment_segment(
                attachment.id, segment_uids[2], db=session, auth_context=other
            )
        assert denied.value.status_code == 404
        with pytest.raises(HTTPException) as denied_page:
            await get_attachment_segments(
                attachment.id, limit=2, offset=0, db=session, auth_context=other
            )
        assert denied_page.value.status_code == 404


@pytest.mark.asyncio
async def test_project_graph_uid_collision_does_not_transfer_object_ownership(
    isolated_fact_sessionmaker,
):
    first_user = f"fact-user-{uuid.uuid4().hex}"
    second_user = f"fact-user-{uuid.uuid4().hex}"
    organization_id = f"org-fact-{uuid.uuid4().hex[:12]}"
    workspace_id = f"workspace-{organization_id}"
    async with isolated_fact_sessionmaker() as session:
        first_segment = await _seed_source_segment(
            session, user_id=first_user, organization_id=organization_id
        )
        first_segment_id = first_segment.content_segment_id
        original = extract_project_semantics([_source_segment(first_segment)]).objects[0]
        first_extraction = ProjectSemanticExtractionResult(
            objects=(original,), edges=(), extractor_name="test", extractor_version="1"
        )
        await persist_project_graph_projection(
            session, extraction=first_extraction, user_id=first_user,
            organization_id=organization_id, workspace_id=workspace_id,
        )
        await session.commit()

        second_segment = await _seed_source_segment(
            session, user_id=second_user, organization_id=organization_id
        )
        colliding = replace(
            original, source_segment_uids=(second_segment.content_segment_uid,)
        )
        second_extraction = replace(first_extraction, objects=(colliding,))
        with pytest.raises(ValueError, match="different scope"):
            await persist_project_graph_projection(
                session, extraction=second_extraction, user_id=second_user,
                organization_id=organization_id, workspace_id=workspace_id,
            )
        await session.rollback()

        persisted = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == original.uid
            )
        )
        assert persisted.user_id == first_user
        assert persisted.primary_content_segment_id == first_segment_id


@pytest.mark.asyncio
async def test_attachment_fact_persists_owner_and_exact_attachment_citation(
    isolated_fact_sessionmaker,
):
    user_id = f"fact-user-{uuid.uuid4().hex}"
    organization_id = f"org-fact-{uuid.uuid4().hex[:12]}"
    async with isolated_fact_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        attachment = Attachment(
            email_id=segment.email_id,
            filename="invoice.txt",
            content="Invoice date: 2026-09-27 합계: ₩1,200,000",
        )
        session.add(attachment)
        await session.flush()
        segment.attachment_id = attachment.id
        segment.source_kind = "attachment"
        segment.source_record_uid = f"attachment:{attachment.id}"
        segment.safe_text_content = attachment.content
        extraction = extract_attachment_facts([_source_segment(segment)])

        result = await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=f"workspace-{organization_id}",
        )
        await session.commit()

        assert len(result.objects) == len(result.edges) == 2
        fact = next(
            item for item in result.objects if item.attributes_json["fact_kind"] == "amount"
        )
        assert fact.attachment_id == attachment.id
        assert fact.email_id == segment.email_id
        assert fact.user_id == user_id
        assert fact.organization_id == organization_id
        assert fact.source_segment_uids == [segment.content_segment_uid]
        assert fact.attributes_json["fact_kind"] == "amount"
        assert fact.attributes_json["value"] == "₩1,200,000"
        assert fact.attributes_json["label_locale"] == "ko"
        assert fact.attributes_json["validation_status"] == "format_validated"
        assert fact.attributes_json["source_segment_hash"] == hashlib.sha256(
            segment.safe_text_content.encode("utf-8")
        ).hexdigest()
        assert fact.status_code == "candidate"
        assert fact.confidence == 0.9
        assert (fact.extractor_name, fact.extractor_version) == (
            "literal_attachment_fact", "1"
        )
        date_fact = next(
            item for item in result.objects if item.attributes_json["fact_kind"] == "date"
        )
        assert date_fact.attributes_json["label_locale"] == "en"
        assert any(
            edge.target_object_id == fact.project_graph_object_id
            for edge in result.edges
        )

        first_email = await session.get(Email, segment.email_id)
        other_email = Email(
            user_id=user_id,
            organization_id=organization_id,
            message_id=f"<{uuid.uuid4().hex}@example.com>",
            thread_id=first_email.thread_id,
            sender="partner@example.com",
            date=datetime.datetime.now(datetime.timezone.utc),
            body="Follow-up with an attachment",
        )
        session.add(other_email)
        await session.flush()
        other_attachment = Attachment(
            email_id=other_email.id, filename="parties.txt", content="Vendor: Partner Ltd",
        )
        session.add(other_attachment)
        await session.flush()
        source_uid = f"attachment:{other_attachment.id}"
        other_node = ContentNodeRecord(
            content_node_uid=f"node-{uuid.uuid4().hex[:16]}",
            email_id=other_email.id,
            attachment_id=other_attachment.id,
            source_kind="attachment",
            source_record_uid=source_uid,
            parent_node_uid=None,
            node_kind="document",
            node_path="/document[1]",
            ordinal_index=1,
            display_label="parties.txt",
            safe_text_content=other_attachment.content,
            content_hash=uuid.uuid4().hex,
        )
        session.add(other_node)
        await session.flush()
        other_segment = ContentSegmentRecord(
            content_segment_uid=f"seg-{uuid.uuid4().hex[:16]}",
            email_id=other_email.id,
            attachment_id=other_attachment.id,
            content_node_id=other_node.content_node_id,
            source_kind="attachment",
            source_record_uid=source_uid,
            segment_kind="paragraph",
            segment_path="/document[1]/paragraph[1]",
            ordinal_index=1,
            safe_text_content=other_attachment.content,
            content_hash=uuid.uuid4().hex,
            word_count=3,
        )
        session.add(other_segment)
        await session.flush()
        await persist_project_graph_projection(
            session,
            extraction=extract_attachment_facts([_source_segment(other_segment)]),
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=f"workspace-{organization_id}",
        )
        await session.commit()

        owner = AuthContext(
            user_id=user_id, role="member", organization_id=organization_id,
            group_ids=(), workspace_id=f"workspace-{organization_id}",
        )
        first = await get_attachment_facts(
            segment.email_id, limit=1, offset=0, db=session, auth_context=owner,
        )
        second = await get_attachment_facts(
            segment.email_id, limit=1, offset=1, db=session, auth_context=owner,
        )
        assert first.next_offset == 1
        assert second.next_offset is None
        assert all(item.validation_status == "format_validated"
                   for item in first.facts + second.facts)
        fact.attributes_json = {**fact.attributes_json, "validation_status": "inferred_unverified",
                                "evidence_excerpt": "합계: ₩1,200,000"}
        await session.commit()
        candidate_page = await get_attachment_facts(
            segment.email_id, limit=10, offset=0, db=session, auth_context=owner,
        )
        assert next(item for item in candidate_page.facts
                    if item.object_uid == fact.object_uid).validation_status == "inferred_unverified"
        assert next(item for item in candidate_page.facts
                    if item.object_uid == fact.object_uid).evidence_excerpt == "합계: ₩1,200,000"
        fact.attributes_json = {**fact.attributes_json, "evidence_excerpt": "Invented quote"}
        await session.commit()
        with pytest.raises(HTTPException) as invalid_excerpt:
            await get_attachment_facts(segment.email_id, limit=10, offset=0,
                                       db=session, auth_context=owner)
        assert invalid_excerpt.value.status_code == 409
        fact.attributes_json = {**fact.attributes_json, "evidence_excerpt": "합계: ₩1,200,000"}
        await session.commit()
        assert {item.fact_kind for item in first.facts + second.facts} == {
            "date", "amount"
        }
        assert all(
            item.source_segment_uid == segment.content_segment_uid
            and item.attachment_id == attachment.id
            and item.evidence_excerpt == segment.safe_text_content
            for item in first.facts + second.facts
        )
        thread_page = await get_attachment_facts(
            segment.email_id, include_thread=True, limit=10, offset=0,
            db=session, auth_context=owner,
        )
        assert {item.email_id for item in thread_page.facts} == {
            segment.email_id, other_email.id,
        }
        assert len(thread_page.facts) == 3

        other_user = AuthContext(
            user_id="different-user", role="member", organization_id=organization_id,
            group_ids=(), workspace_id=f"workspace-{organization_id}",
        )
        with pytest.raises(HTTPException) as denied:
            await get_attachment_facts(
                segment.email_id, limit=1, offset=0, db=session,
                auth_context=other_user,
            )
        assert denied.value.status_code == 404

        segment.safe_text_content = "Total: $999"
        await session.commit()
        with pytest.raises(HTTPException) as stale_text:
            await get_attachment_facts(
                segment.email_id, limit=10, offset=0, db=session, auth_context=owner,
            )
        assert stale_text.value.status_code == 409

        segment.safe_text_content = attachment.content
        fact.source_segment_uids = ["wrong-segment"]
        await session.commit()
        with pytest.raises(HTTPException) as stale_citation:
            await get_attachment_facts(
                segment.email_id, limit=10, offset=0, db=session, auth_context=owner,
            )
        assert stale_citation.value.status_code == 409


@pytest.mark.asyncio
async def test_attachment_fact_failure_rolls_back_email_and_retry_is_idempotent(
    isolated_fact_sessionmaker,
    monkeypatch,
    tmp_path,
):
    user_id = f"fact-user-{uuid.uuid4().hex}"
    organization_id = f"org-fact-{uuid.uuid4().hex[:12]}"
    message_id = f"<{uuid.uuid4().hex}@example.com>"
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["Date"] = "Sun, 27 Sep 2026 10:00:00 +0000"
    message["From"] = "partner@example.com"
    message["To"] = "owner@example.com"
    message["Subject"] = "Invoice"
    message.set_content("Please see attached invoice.")
    message.add_attachment(
        "Invoice date: 2026-09-27\nTotal: $1,200",
        subtype="plain",
        filename="invoice.txt",
    )
    eml_path = tmp_path / "invoice.eml"
    eml_path.write_bytes(message.as_bytes())

    real_persist = import_service.persist_project_graph_projection
    attempts = 0

    async def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            await real_persist(*args, **kwargs)
            raise RuntimeError("injected projection failure")
        return await real_persist(*args, **kwargs)

    monkeypatch.setattr(import_service, "persist_project_graph_projection", fail_once)
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTION_ENABLED", False
    )
    async with isolated_fact_sessionmaker() as session:

        async def import_once():
            return await import_service._import_single_eml(
                session,
                eml_path=eml_path,
                display_filename="invoice.eml",
                user_id=user_id,
                organization_id=organization_id,
            )

        failed = await import_once()
        assert failed.status == "failed"
        assert (
            await session.scalar(
                select(func.count()).select_from(Email).where(Email.user_id == user_id)
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProjectGraphObjectRecord)
                .where(
                    ProjectGraphObjectRecord.user_id == user_id,
                    ProjectGraphObjectRecord.object_type == "attachment_fact",
                )
            )
            == 0
        )

        imported = await import_once()
        assert imported.status == "imported"
        duplicate = await import_once()
        assert duplicate.status == "skipped_duplicate"
        assert attempts == 2
        assert (
            await session.scalar(
                select(func.count()).select_from(Email).where(Email.user_id == user_id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProjectGraphObjectRecord)
                .where(
                    ProjectGraphObjectRecord.user_id == user_id,
                    ProjectGraphObjectRecord.object_type == "attachment_fact",
                )
            )
            == 2
        )

        second_user = f"fact-user-{uuid.uuid4().hex}"
        second_owner = await import_service._import_single_eml(
            session,
            eml_path=eml_path,
            display_filename="invoice.eml",
            user_id=second_user,
            organization_id=organization_id,
        )
        assert second_owner.status == "imported"
        assert await session.scalar(
            select(func.count()).select_from(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.user_id == second_user,
                ProjectGraphObjectRecord.object_type == "attachment_fact",
            )
        ) == 2


@pytest.mark.asyncio
async def test_concurrent_same_owner_import_keeps_one_email_and_fact(
    isolated_fact_sessionmaker,
):
    user_id = f"fact-user-{uuid.uuid4().hex}"
    organization_id = f"org-fact-{uuid.uuid4().hex[:12]}"
    message = EmailMessage()
    message["Message-ID"] = f"<{uuid.uuid4().hex}@example.com>"
    message["Date"] = "Sun, 27 Sep 2026 10:00:00 +0000"
    message["From"] = "partner@example.com"
    message["To"] = "owner@example.com"
    message["Subject"] = "Invoice"
    message.set_content("Please see attached invoice.")
    message.add_attachment("Total: $1,200", subtype="plain", filename="invoice.txt")
    upload = import_service.EmailImportUpload("invoice.eml", message.as_bytes())

    async def import_once():
        async with isolated_fact_sessionmaker() as session:
            return await import_service.import_email_uploads(
                session,
                uploads=[upload],
                user_id=user_id,
                organization_id=organization_id,
            )

    results = await asyncio.wait_for(
        asyncio.gather(import_once(), import_once()), timeout=20
    )
    assert sorted((item.imported_count, item.skipped_count) for item in results) == [
        (0, 1), (1, 0)
    ]
    async with isolated_fact_sessionmaker() as session:
        assert await session.scalar(
            select(func.count()).select_from(Email).where(Email.user_id == user_id)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.user_id == user_id,
                ProjectGraphObjectRecord.object_type == "attachment_fact",
            )
        ) == 1


@pytest.mark.asyncio
async def test_deferred_pdf_recognition_persists_attachment_facts(
    isolated_fact_sessionmaker, monkeypatch,
):
    user_id = f"fact-user-{uuid.uuid4().hex}"
    organization_id = f"org-fact-{uuid.uuid4().hex[:12]}"
    async with isolated_fact_sessionmaker() as session:
        segment = await _seed_source_segment(
            session, user_id=user_id, organization_id=organization_id
        )
        email = await session.get(Email, segment.email_id)
        attachment = Attachment(
            email=email,
            filename="invoice.pdf",
            content=base64.b64encode(b"%PDF-1.7 fixture").decode("ascii"),
            parse_status="pdf_dom_recognition_pending",
        )
        session.add(attachment)
        await session.commit()

    async def resolve_config(_session, _organization_id):
        return NewsdomRuntimeConfig(
            base_url="https://newsdom.example.com",
            api_token=None,
            request_language="auto",
            recognition_mode="auto",
            provider_name="fixture",
        )

    async def recognize(**_kwargs):
        return {"pages": [{"page_number": 1, "articles": [
            {"headline": "Invoice", "body_blocks": [
                "Invoice date: 2026-09-27\nTotal: $1,200"
            ]}
        ]}]}

    async with isolated_fact_sessionmaker() as session:
        pending = await session.scalar(
            NewsdomRecognitionWorker(batch_limit=1)._pending_attachment_statement(None)
        )
        real_persist = newsdom_worker_module.persist_project_graph_projection

        async def fail_after_write(*args, **kwargs):
            await real_persist(*args, **kwargs)
            raise RuntimeError("injected fact persistence failure")

        monkeypatch.setattr(
            newsdom_worker_module, "persist_project_graph_projection", fail_after_write
        )
        with pytest.raises(RuntimeError, match="injected fact persistence failure"):
            await process_pending_attachment(
                session=session,
                attachment=pending,
                config_resolver=resolve_config,
                request_fn=recognize,
            )
        await session.rollback()
        assert await session.scalar(
            select(func.count()).select_from(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.user_id == user_id
            )
        ) == 0

        monkeypatch.setattr(
            newsdom_worker_module, "persist_project_graph_projection", real_persist
        )
        pending = await session.scalar(
            NewsdomRecognitionWorker(batch_limit=1)._pending_attachment_statement(None)
        )
        assert pending.parse_status == "pdf_dom_recognition_pending"
        result = await process_pending_attachment(
            session=session,
            attachment=pending,
            config_resolver=resolve_config,
            request_fn=recognize,
        )
        assert result == "recognized"
        await session.commit()
        facts = (
            await session.scalars(
                select(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.user_id == user_id,
                    ProjectGraphObjectRecord.attachment_id == attachment.id,
                    ProjectGraphObjectRecord.object_type == "attachment_fact",
                )
            )
        ).all()
        assert {fact.attributes_json["fact_kind"] for fact in facts} == {
            "date", "amount"
        }
        assert all(fact.source_segment_uids for fact in facts)


@pytest.mark.asyncio
async def test_project_graph_projection_persists_object_to_object_edges(
    project_graph_sessionmaker,
):
    user_id = f"project-user-{uuid.uuid4().hex}"
    organization_id = "org-acme"
    workspace_id = "workspace-org-acme"
    async with project_graph_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        segment_uid = segment.content_segment_uid
        feature = ProjectSemanticObject(
            uid=f"feature:{uuid.uuid4().hex[:16]}",
            object_type=ProjectObjectType.FEATURE,
            title="Feature: retry banner",
            summary="Show a retry banner on card decline.",
            source_segment_uids=(segment_uid,),
            confidence=0.8,
            extractor_name="llm_grounded_project_graph",
            extractor_version="test",
        )
        requirement = ProjectSemanticObject(
            uid=f"requirement:{uuid.uuid4().hex[:16]}",
            object_type=ProjectObjectType.REQUIREMENT,
            title="Requirement: handle card declines",
            summary="The checkout must handle card declines.",
            source_segment_uids=(segment_uid,),
            confidence=0.9,
            extractor_name="llm_grounded_project_graph",
            extractor_version="test",
        )
        relation_edge = ProjectSemanticEdge(
            source_uid=feature.uid,
            target_uid=requirement.uid,
            edge_type="implements",
            confidence=0.7,
            source_segment_uids=(segment_uid,),
        )
        extraction = ProjectSemanticExtractionResult(
            objects=(feature, requirement),
            edges=(relation_edge,),
            extractor_name="llm_grounded_project_graph",
            extractor_version="test",
        )

        result = await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        await session.commit()

        assert len(result.objects) == 2
        assert len(result.edges) == 1
        persisted_edge = result.edges[0]
        object_ids = {obj.project_graph_object_id for obj in result.objects}
        # The object-to-object edge wires both endpoints to persisted objects,
        # so the graph carries a real inter-object relationship (not just
        # segment evidence).
        assert persisted_edge.edge_type == "implements"
        assert persisted_edge.source_object_id in object_ids
        assert persisted_edge.target_object_id in object_ids
        assert persisted_edge.source_object_id != persisted_edge.target_object_id
        assert persisted_edge.source_segment_uids == [segment_uid]


@pytest.mark.asyncio
async def test_project_graph_projection_upserts_existing_records(
    project_graph_sessionmaker,
):
    user_id = f"project-user-{uuid.uuid4().hex}"
    organization_id = f"org-projection-{uuid.uuid4().hex[:12]}"
    workspace_id = f"workspace-{organization_id}"
    async with project_graph_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        extraction = extract_project_semantics([_source_segment(segment)])

        await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            status_code="confirmed",
        )
        await session.commit()

        object_count = await session.scalar(
            select(func.count())
            .select_from(ProjectGraphObjectRecord)
            .where(ProjectGraphObjectRecord.user_id == user_id)
        )
        edge_count = await session.scalar(
            select(func.count())
            .select_from(ProjectGraphEdgeRecord)
            .where(ProjectGraphEdgeRecord.user_id == user_id)
        )
        persisted_objects = (
            await session.scalars(
                select(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.user_id == user_id
                )
            )
        ).all()

        # Re-running the projection upserts the same two extracted
        # objects (requirement + feature) instead of duplicating them.
        assert object_count == 2
        assert edge_count == 2
        assert persisted_objects
        assert {obj.status_code for obj in persisted_objects} == {"confirmed"}


@pytest.mark.asyncio
async def test_project_graph_correction_records_before_after_and_updates_projection(
    project_graph_sessionmaker,
):
    user_id = f"project-user-{uuid.uuid4().hex}"
    organization_id = f"org-projection-{uuid.uuid4().hex[:12]}"
    workspace_id = f"workspace-{organization_id}"
    async with project_graph_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=user_id,
            organization_id=organization_id,
        )
        extraction = extract_project_semantics([_source_segment(segment)])
        result = await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )

        correction = await apply_project_graph_correction(
            session,
            object_uid=result.objects[0].object_uid,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            actor_user_id="reviewer",
            correction_action="confirm_requirement",
            after_json={
                "status_code": "approved",
                "title": "Requirement: confirmed checkout retry guidance",
            },
            rationale="Reviewed against the source segment.",
        )
        await session.commit()

        persisted_object = await session.get(
            ProjectGraphObjectRecord,
            result.objects[0].project_graph_object_id,
        )
        persisted_correction = await session.get(
            ProjectGraphCorrectionRecord,
            correction.project_graph_correction_id,
        )

        assert persisted_object is not None
        assert persisted_object.status_code == "approved"
        assert (
            persisted_object.title == "Requirement: confirmed checkout retry guidance"
        )
        assert persisted_correction is not None
        assert persisted_correction.before_json["status_code"] == "candidate"
        assert persisted_correction.after_json["status_code"] == "approved"
        assert persisted_correction.source_segment_uids == [segment.content_segment_uid]


@pytest.mark.asyncio
async def test_project_graph_projection_rejects_cross_scope_source_segments(
    project_graph_sessionmaker,
):
    organization_id = f"org-projection-{uuid.uuid4().hex[:12]}"
    async with project_graph_sessionmaker() as session:
        segment = await _seed_source_segment(
            session,
            user_id=f"project-user-{uuid.uuid4().hex}",
            organization_id=organization_id,
        )
        extraction = extract_project_semantics([_source_segment(segment)])

        with pytest.raises(ValueError, match="different scope"):
            await persist_project_graph_projection(
                session,
                extraction=extraction,
                user_id="different-user",
                organization_id=organization_id,
                workspace_id=f"workspace-{organization_id}",
            )


async def _seed_source_segment(
    session,
    *,
    user_id: str,
    organization_id: str,
) -> ContentSegmentRecord:
    await _cleanup_user(session, user_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    email = Email(
        user_id=user_id,
        organization_id=organization_id,
        message_id=f"<{uuid.uuid4().hex}@example.com>",
        thread_id=f"thread-{uuid.uuid4().hex}",
        fingerprint=f"sha256:{uuid.uuid4().hex}",
        sender="partner@example.com",
        recipients="owner@example.com",
        subject="Project Alpha requirements",
        date=now,
        body="요구사항 본문",
    )
    session.add(email)
    await session.flush()
    node = ContentNodeRecord(
        content_node_uid=f"node-{uuid.uuid4().hex[:16]}",
        email_id=email.id,
        attachment_id=None,
        source_kind="email_body",
        source_record_uid=email.message_id,
        parent_node_uid=None,
        node_kind="document",
        node_path="/document[1]",
        ordinal_index=1,
        display_label="body",
        safe_text_content="요구사항 문단",
        content_hash=uuid.uuid4().hex,
        created_at=now,
    )
    session.add(node)
    await session.flush()
    segment = ContentSegmentRecord(
        content_segment_uid=f"seg-{uuid.uuid4().hex[:16]}",
        email_id=email.id,
        attachment_id=None,
        content_node_id=node.content_node_id,
        source_kind="email_body",
        source_record_uid=email.message_id,
        segment_kind="paragraph",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=1,
        heading_path="Requirements",
        safe_text_content=(
            "요구사항: 결제 화면은 카드 승인 실패 시 재시도 안내를 반드시 보여줘야 합니다."
        ),
        content_hash=uuid.uuid4().hex,
        word_count=9,
        created_at=now,
    )
    session.add(segment)
    await session.flush()
    return segment


def _source_segment(segment: ContentSegmentRecord) -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid=segment.content_segment_uid,
        source_kind=segment.source_kind,
        source_record_uid=segment.source_record_uid,
        safe_text_content=segment.safe_text_content,
        heading_path=segment.heading_path,
        segment_path=segment.segment_path,
        ordinal_index=segment.ordinal_index,
    )


async def _cleanup_user(session, user_id: str) -> None:
    await session.execute(
        delete(ProjectGraphCorrectionRecord).where(
            ProjectGraphCorrectionRecord.user_id == user_id
        )
    )
    await session.execute(
        delete(ProjectGraphEdgeRecord).where(ProjectGraphEdgeRecord.user_id == user_id)
    )
    await session.execute(
        delete(ProjectGraphObjectRecord).where(
            ProjectGraphObjectRecord.user_id == user_id
        )
    )
    await session.execute(delete(Email).where(Email.user_id == user_id))
    await session.flush()
