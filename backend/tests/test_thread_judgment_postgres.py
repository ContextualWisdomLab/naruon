"""Verify judgment evidence stays inside the signed email owner's scope."""

import datetime
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.emails import ThreadJudgmentRequest, create_thread_judgment
from core.config import settings
from db.models import Base, ContentNodeRecord, ContentSegmentRecord, Email
from services.llm_provider_selection import RuntimeLLMProvider
from services.thread_judgment import CitedStatement, ThreadJudgmentDraft


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_thread_judgment_uses_only_owner_segments():
    schema = f"e1_judgment_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    now = datetime.datetime(2026, 9, 27, tzinfo=datetime.timezone.utc)
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)

        sessions = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with sessions() as session:
            for owner, message_id, segment_uid in (
                ("owner-a", "owned@example.com", "owned-segment"),
                ("owner-b", "foreign@example.com", "foreign-segment"),
            ):
                segment_text = f"Message for {owner}" + (
                    "x" * 2000 if owner == "owner-a" else ""
                )
                email = Email(
                    user_id=owner,
                    organization_id="org-1",
                    message_id=message_id,
                    thread_id="shared-thread",
                    sender="sender@example.com",
                    date=now,
                    body=f"Message for {owner}",
                )
                session.add(email)
                await session.flush()
                node = ContentNodeRecord(
                    content_node_uid=f"node-{owner}",
                    email_id=email.id,
                    source_kind="email_body",
                    source_record_uid=message_id,
                    node_kind="body",
                    node_path="body",
                    ordinal_index=0,
                    safe_text_content=segment_text,
                    content_hash=f"hash-{owner}",
                )
                session.add(node)
                await session.flush()
                session.add(
                    ContentSegmentRecord(
                        content_segment_uid=segment_uid,
                        email_id=email.id,
                        content_node_id=node.content_node_id,
                        source_kind="email_body",
                        source_record_uid=message_id,
                        segment_kind="paragraph",
                        segment_path="body/1",
                        ordinal_index=0,
                        safe_text_content=segment_text,
                        content_hash=f"hash-{owner}",
                        word_count=3,
                    )
                )
            await session.commit()

        provider = RuntimeLLMProvider(
            api_key="test-key",
            base_url="https://example.com/v1",
            chat_model="test-model",
            embedding_model="test-embedding",
            provider_name="test-provider",
            provider_source="llm_provider",
        )
        judgment = ThreadJudgmentDraft(
            current_state=CitedStatement(
                text="Owner's message is present",
                evidence_segment_uids=["owned-segment"],
            ),
            judgment_point=None,
            recommended_action=None,
            blocking_dependencies=[],
            unresolved_commitments=[],
            tensions=[],
        )
        synthesize = AsyncMock(return_value=judgment)
        auth = AuthContext(
            user_id="owner-a",
            role="member",
            organization_id="org-1",
            group_ids=(),
            workspace_id="workspace-org-1",
        )
        with (
            patch(
                "api.emails.resolve_runtime_llm_provider",
                AsyncMock(return_value=provider),
            ),
            patch("api.emails.synthesize_thread_judgment", synthesize),
        ):
            async with sessions() as session:
                result = await create_thread_judgment(
                    ThreadJudgmentRequest(thread_id="shared-thread"),
                    db=session,
                    auth_context=auth,
                )
            assert result.status == "ready"
            assert result.source_count == 1
            assert result.evidence_limited is True
            assert [item.uid for item in result.evidence] == ["owned-segment"]
            assert [item.uid for item in synthesize.await_args.args[0]] == [
                "owned-segment"
            ]
            assert synthesize.await_args.args[1] == []

            async with sessions() as session:
                with pytest.raises(HTTPException) as error:
                    await create_thread_judgment(
                        ThreadJudgmentRequest(thread_id="shared-thread"),
                        db=session,
                        auth_context=AuthContext(
                            user_id="owner-c",
                            role="member",
                            organization_id="org-1",
                            group_ids=(),
                            workspace_id="workspace-org-1",
                        ),
                    )
            assert error.value.status_code == 404
            assert synthesize.await_count == 1
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
