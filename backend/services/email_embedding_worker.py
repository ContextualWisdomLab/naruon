"""Backfill committed email embeddings without holding up mailbox ingestion."""

import asyncio
import logging

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import selectinload, undefer

from db.models import Attachment, Email
from db.session import AsyncSessionLocal
from services.email_import_service import (
    EMBEDDING_DIMENSION,
    EmailImportEmbeddingProvider,
    _extract_and_generate_embeddings,
)
from services.llm_provider_selection import resolve_runtime_llm_provider

logger = logging.getLogger(__name__)
ZERO_VECTOR = [0.0] * EMBEDDING_DIMENSION


def _pending_vector(value) -> bool:
    """Treat absent and historical zero vectors as unfinished work."""
    return value is None or not any(value)


def _pending_email_statement(after_id: int | None):
    """Find one pending email after the cursor, including parsed attachments."""
    # ponytail: primary-key scan stays simple; add a pending-work index or queue
    # when the measured mailbox volume makes empty sweeps costly.
    email_pending = and_(
        or_(Email.embedding.is_(None), Email.embedding == ZERO_VECTOR),
        func.length(func.btrim(Email.body)) > 0,
    )
    attachment_pending = Email.attachments.any(
        and_(
            or_(Attachment.embedding.is_(None), Attachment.embedding == ZERO_VECTOR),
            Attachment.parse_status == "parsed",
            func.length(func.btrim(Attachment.content)) > 0,
        )
    )
    statement = select(Email).where(or_(email_pending, attachment_pending))
    if after_id is not None:
        statement = statement.where(Email.id > after_id)
    return (
        statement.order_by(Email.id)
        .options(
            undefer(Email.embedding),
            selectinload(Email.attachments).undefer(Attachment.embedding),
        )
        .limit(1)
    )


class EmailEmbeddingWorker:
    """Sweep committed mail in bounded batches and retry missing embeddings."""

    def __init__(self, *, interval_seconds: int = 60, batch_limit: int = 10):
        """Keep the sweep cadence, batch limit, and cursor for this process."""
        self.interval_seconds = interval_seconds
        self.batch_limit = batch_limit
        self._task: asyncio.Task | None = None
        self._running = False
        self._cursor: int | None = None

    async def start(self) -> None:
        """Start one background loop if it is not already running."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Cancel the loop so pending rows remain available after restart."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Retry sweeps until shutdown without masking cancellation."""
        while self._running:
            try:
                await self._sweep()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Email embedding sweep failed: %s", type(exc).__name__)
            if self._running:
                try:
                    await asyncio.sleep(self.interval_seconds)
                except asyncio.CancelledError:
                    break

    async def _sweep(self) -> None:
        """Generate outside DB sessions and conditionally persist completed vectors."""
        for _ in range(self.batch_limit):
            email_id = None
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        _pending_email_statement(self._cursor)
                    )
                    email = result.scalar_one_or_none()
                    if email is None:
                        self._cursor = None
                        break
                    email_id = self._cursor = email.id
                    owner_id, organization_id = email.user_id, email.organization_id
                    provider = await resolve_runtime_llm_provider(
                        session,
                        user_id=owner_id,
                        organization_id=organization_id,
                    )
                    body_text = (
                        email.body
                        if email.body.strip() and _pending_vector(email.embedding)
                        else ""
                    )
                    attachments = [
                        (attachment.id, attachment.content)
                        for attachment in email.attachments
                        if attachment.parse_status == "parsed"
                        and attachment.content.strip()
                        and _pending_vector(attachment.embedding)
                    ]
                    embedding_provider = (
                        EmailImportEmbeddingProvider(
                            api_key=provider.api_key,
                            base_url=provider.base_url,
                            embedding_model=provider.embedding_model,
                        )
                        if provider is not None
                        else None
                    )

                if embedding_provider is None or (not body_text and not attachments):
                    continue

                # ponytail: replicas may duplicate model calls; conditional writes
                # avoid stale overwrites without holding a DB connection for hours.
                _, vectors = await _extract_and_generate_embeddings(
                    {
                        "body": body_text,
                        "attachments": [
                            {"content": content, "parse_status": "parsed"}
                            for _, content in attachments
                        ],
                    },
                    embedding_provider,
                )
                async with AsyncSessionLocal() as session:
                    if body_text and not _pending_vector(vectors[0]):
                        await session.execute(
                            update(Email)
                            .where(
                                Email.id == email_id,
                                *Email.owner_filters(owner_id, organization_id),
                                Email.body == body_text,
                                or_(
                                    Email.embedding.is_(None),
                                    Email.embedding == ZERO_VECTOR,
                                ),
                            )
                            .values(embedding=vectors[0])
                        )
                    for (attachment_id, content), vector in zip(
                        attachments, vectors[1:], strict=True
                    ):
                        if _pending_vector(vector):
                            continue
                        await session.execute(
                            update(Attachment)
                            .where(
                                Attachment.id == attachment_id,
                                Attachment.email_id == email_id,
                                Attachment.email.has(
                                    and_(
                                        *Email.owner_filters(owner_id, organization_id)
                                    )
                                ),
                                Attachment.content == content,
                                or_(
                                    Attachment.embedding.is_(None),
                                    Attachment.embedding == ZERO_VECTOR,
                                ),
                            )
                            .values(embedding=vector)
                        )
                    await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "Email embedding item failed: id=%s reason=%s",
                    email_id,
                    type(exc).__name__,
                )
