import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload, undefer

from core.config import settings
from db.models import Attachment, Base, ContentNodeRecord, Email, TicketTask
from services.email_parser import parse_eml_bytes
from services.email_embedding_worker import EmailEmbeddingWorker, ZERO_VECTOR
from services.imap_worker import process_fetched_email
from services.hybrid_retrieval.retrieval_channels import (
    build_dense_attachment_statement,
    build_dense_email_statement,
)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_self_note_rollback_and_same_message_across_owners(monkeypatch, caplog):
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
            assert (
                await session.execute(select(TicketTask))
            ).scalar_one().related_email_id == email.id
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
                (
                    await session.execute(
                        select(ContentNodeRecord).where(
                            ContentNodeRecord.node_kind == "personal_reference"
                        )
                    )
                )
                .scalars()
                .all()
            )
            tasks = (await session.execute(select(TicketTask))).scalars().all()
            assert {email.user_id for email in emails} == {"owner-a", "owner-b"}
            assert len(nodes) == len({node.content_node_uid for node in nodes}) == 2
            assert len(tasks) == 2
            first_email_id = emails[0].id

            # A previously stored zero vector and new NULL vectors both need
            # a durable retry after the provider becomes available.
            emails[0].embedding = ZERO_VECTOR
            session.add(
                Attachment(
                    email_id=emails[0].id,
                    filename="note.txt",
                    content="Attachment note",
                    content_type="text/plain",
                )
            )
            await session.commit()

        monkeypatch.setattr(
            "services.email_embedding_worker.AsyncSessionLocal", sessions
        )

        async def no_provider(*args, **kwargs):
            return None

        monkeypatch.setattr(
            "services.email_embedding_worker.resolve_runtime_llm_provider",
            no_provider,
        )
        await EmailEmbeddingWorker(batch_limit=10)._sweep()

        async with sessions() as session:
            pending = (
                (
                    await session.execute(
                        select(Email)
                        .options(
                            undefer(Email.embedding),
                            selectinload(Email.attachments).undefer(
                                Attachment.embedding
                            ),
                        )
                        .order_by(Email.id)
                    )
                )
                .scalars()
                .all()
            )
            assert list(pending[0].embedding) == ZERO_VECTOR
            assert pending[1].embedding is None
            assert pending[0].attachments[0].embedding is None

        async def provider(*args, **kwargs):
            return SimpleNamespace(
                api_key="test", base_url=None, embedding_model="test"
            )

        embed_calls = 0

        async def embed(parsed, embedding_provider, batch_context=None):
            nonlocal embed_calls
            assert scoped_engine.pool.checkedout() == 0
            call = embed_calls
            embed_calls += 1
            if call == 0:
                raise RuntimeError("retry this source")
            if call == 2:
                async with sessions() as concurrent_session:
                    await concurrent_session.execute(
                        update(Email)
                        .where(Email.id == first_email_id)
                        .values(embedding=[2.0] * 1536)
                    )
                    await concurrent_session.commit()
            vectors = [[1.0] * 1536 for _ in range(1 + len(parsed["attachments"]))]
            if call == 2:
                vectors[-1] = ZERO_VECTOR
            return parsed["attachments"], vectors

        monkeypatch.setattr(
            "services.email_embedding_worker.resolve_runtime_llm_provider", provider
        )

        async def cancel_embed(parsed, embedding_provider, batch_context=None):
            raise asyncio.CancelledError

        monkeypatch.setattr(
            "services.email_embedding_worker._extract_and_generate_embeddings",
            cancel_embed,
        )
        with pytest.raises(asyncio.CancelledError):
            await EmailEmbeddingWorker(batch_limit=10)._sweep()
        assert scoped_engine.pool.checkedout() == 0

        monkeypatch.setattr(
            "services.email_embedding_worker._extract_and_generate_embeddings", embed
        )
        await EmailEmbeddingWorker(batch_limit=10)._sweep()
        await EmailEmbeddingWorker(batch_limit=10)._sweep()
        await EmailEmbeddingWorker(batch_limit=10)._sweep()
        assert embed_calls == 4
        assert "reason=RuntimeError" in caplog.text

        async with sessions() as session:
            completed = (
                (
                    await session.execute(
                        select(Email)
                        .options(
                            undefer(Email.embedding),
                            selectinload(Email.attachments).undefer(
                                Attachment.embedding
                            ),
                        )
                        .order_by(Email.id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(completed) == 2
            assert [email.embedding[0] for email in completed] == [2.0, 1.0]
            assert completed[0].attachments[0].embedding[0] == 1.0
            owner_filters = Email.owner_filters("owner-a", "org-1")
            body_hits = (
                await session.execute(
                    build_dense_email_statement([1.0] * 1536, owner_filters, 10)
                )
            ).all()
            attachment_hits = (
                await session.execute(
                    build_dense_attachment_statement([1.0] * 1536, owner_filters, 10)
                )
            ).all()
            assert [row.email_id for row in body_hits] == [first_email_id]
            assert [row.email_id for row in attachment_hits] == [first_email_id]
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
