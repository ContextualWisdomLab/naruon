"""Background worker glue for NewsDOM PDF DOM recognition.

Attachments and workspace documents whose PDF recognition was deferred at
import time are processed here: the sidecar is called (via
:mod:`services.newsdom_pdf_recognition`) and the returned tree is landed into
the persisted attachment/document content and, for attachments, the
``content_nodes`` / ``content_segments`` graph.

The apply functions are deliberately session-free so they can be unit tested
with in-memory model instances and a mocked NewsDOM client.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

from sqlalchemy import bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Document,
    Email,
)
from db.session import AsyncSessionLocal, engine
from services.attachment_parser import decode_deferred_attachment_payload
from services.content_graph import ParseResult
from services.newsdom_client import (
    NewsdomConfigurationError,
    NewsdomRequestError,
    request_pdf_dom,
)
from services.newsdom_pdf_recognition import (
    PDF_DOM_RECOGNITION_FAILED_STATUS,
    PDF_DOM_RECOGNITION_PARSED_STATUS,
    PDF_DOM_RECOGNITION_PENDING_STATUS,
    PDF_PARSE_CONTENT_TYPE,
    PDF_PARSER_KEY,
    NewsdomRuntimeConfig,
    ParseRequestFn,
    PdfDomRecognitionRecords,
    recognize_pdf_dom,
    resolve_newsdom_config_from_db,
)

logger = logging.getLogger(__name__)
_sysrand = random.SystemRandom()

# How the worker resolves a runtime config for an organization. Injectable so
# the per-item processors are unit-testable without a database.
ConfigResolver = Callable[
    [AsyncSession, str | None], Awaitable[NewsdomRuntimeConfig | None]
]


def _append_parse_result_to_attachment(
    *,
    email: Email,
    attachment: Attachment,
    parse_result: ParseResult,
) -> None:
    """Append recognized graph records to an email and its attachment."""
    node_records_by_uid: dict[str, ContentNodeRecord] = {}
    for parsed_node in parse_result.nodes:
        node_record = ContentNodeRecord(
            content_node_uid=parsed_node.content_node_uid,
            source_kind=parsed_node.source_kind,
            source_record_uid=parsed_node.source_record_uid,
            parent_node_uid=parsed_node.parent_node_uid,
            node_kind=parsed_node.node_kind,
            node_path=parsed_node.node_path,
            ordinal_index=parsed_node.ordinal_index,
            display_label=parsed_node.display_label,
            safe_text_content=parsed_node.safe_text_content,
            content_hash=parsed_node.content_hash,
        )
        email.content_nodes.append(node_record)
        attachment.content_nodes.append(node_record)
        node_records_by_uid[parsed_node.content_node_uid] = node_record

    for parsed_segment in parse_result.segments:
        node_record = node_records_by_uid.get(parsed_segment.content_node_uid)
        segment_record = ContentSegmentRecord(
            content_segment_uid=parsed_segment.content_segment_uid,
            source_kind=parsed_segment.source_kind,
            source_record_uid=parsed_segment.source_record_uid,
            segment_kind=parsed_segment.segment_kind,
            segment_path=parsed_segment.segment_path,
            ordinal_index=parsed_segment.ordinal_index,
            heading_path=parsed_segment.heading_path,
            safe_text_content=parsed_segment.safe_text_content,
            content_hash=parsed_segment.content_hash,
            word_count=parsed_segment.word_count,
        )
        if node_record is not None:
            node_record.segments.append(segment_record)
        email.content_segments.append(segment_record)
        attachment.content_segments.append(segment_record)


def apply_recognition_to_attachment(
    *,
    email: Email,
    attachment: Attachment,
    records: PdfDomRecognitionRecords,
) -> None:
    """Land recognized PDF DOM records onto an attachment (text + graph)."""
    attachment.content = records.parse_text
    attachment.parse_content_type = PDF_PARSE_CONTENT_TYPE
    attachment.parser_key = PDF_PARSER_KEY
    attachment.parse_status = PDF_DOM_RECOGNITION_PARSED_STATUS
    attachment.parse_error_code = None
    _append_parse_result_to_attachment(
        email=email,
        attachment=attachment,
        parse_result=records.parse_result,
    )


def apply_recognition_to_document(
    *,
    document: Document,
    records: PdfDomRecognitionRecords,
) -> None:
    """Land recognized PDF text onto a workspace document (mirrors the HWP
    conversion worker: content + status, no content graph rows)."""
    document.document_content = records.parse_text
    document.document_status = PDF_DOM_RECOGNITION_PARSED_STATUS


async def recognize_attachment_pdf(
    *,
    email: Email,
    attachment: Attachment,
    pdf_bytes: bytes,
    config: NewsdomRuntimeConfig | None,
    source_record_uid: str,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> PdfDomRecognitionRecords:
    """Recognize a PDF and land its text and graph on an attachment."""
    records = await recognize_pdf_dom(
        config=config,
        pdf_bytes=pdf_bytes,
        filename=attachment.filename or "attachment.pdf",
        source_kind="attachment",
        source_record_uid=source_record_uid,
        display_name=attachment.filename or "",
        request_fn=request_fn,
    )
    apply_recognition_to_attachment(email=email, attachment=attachment, records=records)
    return records


async def recognize_document_pdf(
    *,
    document: Document,
    pdf_bytes: bytes,
    config: NewsdomRuntimeConfig | None,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> PdfDomRecognitionRecords:
    """Recognize a PDF and land its text on a workspace document."""
    records = await recognize_pdf_dom(
        config=config,
        pdf_bytes=pdf_bytes,
        filename=document.document_name or "document.pdf",
        source_kind="workspace_document",
        source_record_uid=document.document_id,
        display_name=document.document_name or "",
        request_fn=request_fn,
    )
    apply_recognition_to_document(document=document, records=records)
    return records


# --------------------------------------------------------------------------
# Production worker: sweep pending attachments/documents and recognize them.
# --------------------------------------------------------------------------

DEFAULT_NEWSDOM_INTERVAL_SECONDS = 60
DEFAULT_NEWSDOM_BATCH_LIMIT = 10
NEWSDOM_SWEEP_LOCK_NAMESPACE = "naruon-newsdom-recognition-sweep"
MAX_STARTUP_JITTER_SECONDS = 30

# Per-item processing outcomes.
RESULT_RECOGNIZED = "recognized"
RESULT_PENDING = "pending"
RESULT_FAILED = "failed"

_SWEEP_LOCK_PARAMS = {
    "namespace_key": NEWSDOM_SWEEP_LOCK_NAMESPACE,
    "sweep_key": "sweep",
}


async def process_pending_attachment(
    *,
    session: AsyncSession,
    attachment: Attachment,
    config_resolver: ConfigResolver = resolve_newsdom_config_from_db,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> str:
    """Recognize one pending attachment PDF, or record a safe outcome.

    Returns ``RESULT_RECOGNIZED`` on success, ``RESULT_PENDING`` when no active
    provider is configured yet (left pending to retry later), or
    ``RESULT_FAILED`` when the payload or the sidecar response is unusable (a
    visible failure status is recorded - never a false ``parsed``).
    """
    email = attachment.email
    if email is None:
        attachment.parse_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        attachment.parse_error_code = "orphan_attachment"
        return RESULT_FAILED
    try:
        pdf_bytes = decode_deferred_attachment_payload(attachment.content)
    except ValueError as exc:
        attachment.parse_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        attachment.parse_error_code = "invalid_pending_payload"
        logger.warning(
            "NewsDOM attachment %s rejected before recognition: %s",
            getattr(attachment, "id", "?"),
            exc,
        )
        return RESULT_FAILED

    config = await config_resolver(session, email.organization_id)
    if config is None:
        # Degrade gracefully: no active NewsDOM provider for this org yet.
        logger.info(
            "NewsDOM attachment %s remains pending: no active provider for "
            "organization %s.",
            getattr(attachment, "id", "?"),
            email.organization_id or "personal-scope",
        )
        return RESULT_PENDING

    try:
        await recognize_attachment_pdf(
            email=email,
            attachment=attachment,
            pdf_bytes=pdf_bytes,
            config=config,
            source_record_uid=f"attachment-{attachment.id}",
            request_fn=request_fn,
        )
    except NewsdomConfigurationError as exc:
        logger.warning(
            "NewsDOM attachment %s remains pending: provider configuration "
            "was rejected: %s",
            getattr(attachment, "id", "?"),
            exc,
        )
        return RESULT_PENDING
    except (NewsdomRequestError, ValueError) as exc:
        attachment.parse_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        attachment.parse_error_code = "recognition_failed"
        logger.warning(
            "NewsDOM attachment %s recognition failed: %s",
            getattr(attachment, "id", "?"),
            exc,
        )
        return RESULT_FAILED
    return RESULT_RECOGNIZED


async def process_pending_document(
    *,
    session: AsyncSession,
    document: Document,
    config_resolver: ConfigResolver = resolve_newsdom_config_from_db,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> str:
    """Recognize one pending workspace-document PDF, or record a safe outcome."""
    from api.data import decode_pending_pdf_document_bytes

    try:
        pdf_bytes = decode_pending_pdf_document_bytes(document)
    except ValueError as exc:
        document.document_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        logger.warning(
            "NewsDOM document %s rejected before recognition: %s",
            getattr(document, "document_id", "?"),
            exc,
        )
        return RESULT_FAILED

    config = await config_resolver(session, document.organization_id)
    if config is None:
        logger.info(
            "NewsDOM document %s remains pending: no active provider for "
            "organization %s.",
            getattr(document, "document_id", "?"),
            document.organization_id or "personal-scope",
        )
        return RESULT_PENDING

    try:
        await recognize_document_pdf(
            document=document,
            pdf_bytes=pdf_bytes,
            config=config,
            request_fn=request_fn,
        )
    except NewsdomConfigurationError as exc:
        logger.warning(
            "NewsDOM document %s remains pending: provider configuration was "
            "rejected: %s",
            getattr(document, "document_id", "?"),
            exc,
        )
        return RESULT_PENDING
    except (NewsdomRequestError, ValueError) as exc:
        document.document_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        logger.warning(
            "NewsDOM document %s recognition failed: %s",
            getattr(document, "document_id", "?"),
            exc,
        )
        return RESULT_FAILED
    return RESULT_RECOGNIZED


def _engine_uses_postgresql() -> bool:
    """Return whether advisory-lock SQL is supported by the configured engine."""
    return engine.dialect.name == "postgresql"


async def _try_acquire_sweep_lease(connection: AsyncConnection) -> bool:
    """Become the sweep leader for this cycle on this dedicated connection.

    Takes an ``AsyncConnection`` rather than the per-item ``AsyncSession``
    deliberately: ``AsyncSession.commit()``/``rollback()`` release their
    underlying connection back to the pool on every call (SQLAlchemy's normal
    "connectionless execution" behavior), so acquiring the lock through that
    session risks releasing it -- or never releasing it -- from a *different*
    physical backend connection than the one PostgreSQL actually granted the
    advisory lock to. Advisory locks are scoped to the acquiring backend
    session, so a mismatched unlock is a silent no-op and the lock stays held
    (blocking every replica's sweep) until the stray connection is eventually
    recycled or closed. Mirrors
    ``services.attachment_reparse_worker._try_acquire_sweep_lease``.

    Sets AUTOCOMMIT on this connection first: without it, the advisory-lock
    SELECT below opens an implicit transaction that would otherwise stay
    open and idle on this connection for the whole sweep (every other
    statement runs through the separate per-item session), risking
    PostgreSQL's ``idle_in_transaction_session_timeout`` killing this
    connection mid-sweep and silently dropping the lease.
    """
    await connection.execution_options(isolation_level="AUTOCOMMIT")
    acquired = await connection.scalar(
        select(
            func.pg_try_advisory_lock(
                func.hashtext(bindparam("namespace_key")),
                func.hashtext(bindparam("sweep_key")),
            )
        ),
        _SWEEP_LOCK_PARAMS,
    )
    return bool(acquired)


async def _release_sweep_lease(connection: AsyncConnection) -> None:
    """Release the PostgreSQL advisory lock on the connection that holds it."""
    await connection.scalar(
        select(
            func.pg_advisory_unlock(
                func.hashtext(bindparam("namespace_key")),
                func.hashtext(bindparam("sweep_key")),
            )
        ),
        _SWEEP_LOCK_PARAMS,
    )


class NewsdomRecognitionWorker:
    """Periodically recognize pending PDF attachments and workspace documents.

    Mirrors :class:`ReplySlaScheduler`: a jittered periodic loop, a PostgreSQL
    advisory-lock lease so only one replica sweeps per cycle, and per-item
    error isolation. Items whose organization has no active NewsDOM provider are
    left pending (they recognize once a provider is configured); unusable
    payloads/responses are marked failed rather than parsed. The lease is
    acquired and released on one dedicated connection held open for the
    whole sweep, and each row is re-fetched fresh by id before processing --
    the same two corrections applied to
    :class:`services.attachment_reparse_worker.AttachmentReparseWorker`,
    which shares this same lease/cursor/per-item-isolation design.
    """

    def __init__(
        self,
        *,
        interval_seconds: int = DEFAULT_NEWSDOM_INTERVAL_SECONDS,
        batch_limit: int = DEFAULT_NEWSDOM_BATCH_LIMIT,
        request_fn: ParseRequestFn = request_pdf_dom,
        config_resolver: ConfigResolver = resolve_newsdom_config_from_db,
    ):
        """Configure the sweep cadence, batch size, and injectable adapters."""
        self.interval_seconds = interval_seconds
        self.batch_limit = batch_limit
        self._request_fn = request_fn
        self._config_resolver = config_resolver
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._attachment_cursor: int | None = None
        self._document_cursor: str | None = None

    async def start(self) -> None:
        """Start the recognition loop once."""
        if self._is_running:
            logger.warning("NewsdomRecognitionWorker is already running.")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("NewsdomRecognitionWorker started.")

    async def stop(self) -> None:
        """Cancel and await the active recognition loop."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("NewsdomRecognitionWorker cancellation acknowledged.")
        logger.info("NewsdomRecognitionWorker stopped.")

    async def _run_loop(self) -> None:
        """Run jittered recognition sweeps until stopped."""
        try:
            await asyncio.sleep(
                _sysrand.uniform(
                    0, min(self.interval_seconds / 10, MAX_STARTUP_JITTER_SECONDS)
                )
            )
        except asyncio.CancelledError:
            return

        while self._is_running:
            try:
                await self._sweep()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Error in NewsdomRecognitionWorker loop.", exc_info=True)
            if self._is_running:
                try:
                    await asyncio.sleep(self.interval_seconds)
                except asyncio.CancelledError:
                    break

    async def _sweep(self) -> None:
        """Process one leased attachment and document sweep.

        The advisory lock (when the engine supports it) is acquired and
        released on one dedicated connection held open for the whole sweep --
        never through the per-item ``AsyncSession`` used by
        ``_sweep_attachments``/``_sweep_documents``. See
        ``_try_acquire_sweep_lease`` for why that distinction matters.
        """
        if not _engine_uses_postgresql():
            async with AsyncSessionLocal() as session:
                await self._sweep_attachments(session)
                await self._sweep_documents(session)
            return
        async with engine.connect() as lock_connection:
            if not await _try_acquire_sweep_lease(lock_connection):
                logger.debug(
                    "NewsDOM recognition sweep skipped: another replica holds "
                    "the lease."
                )
                return
            try:
                async with AsyncSessionLocal() as session:
                    await self._sweep_attachments(session)
                    await self._sweep_documents(session)
            finally:
                await _release_sweep_lease(lock_connection)

    async def _sweep_attachments(self, session: AsyncSession) -> None:
        """Process a bounded, starvation-free batch of pending attachments.

        The cursor only advances past a row once it is confirmed resolved:
        its processing did not raise, AND it did not return
        ``RESULT_PENDING``. A row whose processing raised, or that came back
        ``RESULT_PENDING`` (e.g. no active provider configured for its
        organization yet), keeps its ``pdf_dom_recognition_pending`` status
        untouched, so if the cursor advanced past it anyway it would never
        be reselected by ``_load_pending_attachments``'s ``id > cursor``
        filter until the whole forward queue happens to drain to empty --
        silent, indefinite starvation of that one row under continuous
        inbound attachment traffic. Capping the cursor at the first
        unresolved row (failure or still-pending) keeps that row in range
        for the next sweep, while later rows in the same batch are still
        processed normally. Each row is also re-fetched fresh by id rather
        than reusing the bulk-loaded instance: ``AsyncSession.rollback()``
        expires every object already loaded in this session, and
        ``process_pending_attachment`` reads attachment/email attributes
        synchronously, so a stale, expired instance from an earlier item's
        failure would raise on that read instead of just isolating the one
        failure. Mirrors
        ``services.attachment_reparse_worker.AttachmentReparseWorker._sweep_attachments``.
        """
        rows = await self._load_pending_attachments(session)
        first_unresolved_id = None
        for attachment_id in [attachment.id for attachment in rows]:
            try:
                attachment = await session.get(
                    Attachment,
                    attachment_id,
                    options=[selectinload(Attachment.email)],
                )
                if attachment is None:
                    continue
                result = await process_pending_attachment(
                    session=session,
                    attachment=attachment,
                    config_resolver=self._config_resolver,
                    request_fn=self._request_fn,
                )
                await session.commit()
                if result == RESULT_PENDING:
                    if first_unresolved_id is None:
                        first_unresolved_id = attachment_id
                else:
                    logger.info(
                        "NewsDOM attachment %s recognition result: %s",
                        attachment_id,
                        result,
                    )
            except Exception:
                await session.rollback()
                logger.error(
                    "NewsDOM attachment %s recognition raised.",
                    attachment_id,
                    exc_info=True,
                )
                if first_unresolved_id is None:
                    first_unresolved_id = attachment_id
        if rows:
            self._attachment_cursor = (
                first_unresolved_id - 1
                if first_unresolved_id is not None
                else rows[-1].id
            )

    def _pending_attachment_statement(self, after_id: int | None):
        """Build the next deterministic attachment batch query."""
        statement = select(Attachment).where(
            Attachment.parse_status == PDF_DOM_RECOGNITION_PENDING_STATUS
        )
        if after_id is not None:
            statement = statement.where(Attachment.id > after_id)
        return (
            statement.order_by(Attachment.id)
            .options(selectinload(Attachment.email))
            .limit(self.batch_limit)
        )

    async def _load_pending_attachments(
        self, session: AsyncSession
    ) -> list[Attachment]:
        """Load after the last attempted row, wrapping at the table tail.

        Advancing over rows that remain pending prevents an unconfigured
        organization's first batch from permanently starving configured rows.
        """
        rows = (
            (
                await session.execute(
                    self._pending_attachment_statement(self._attachment_cursor)
                )
            )
            .scalars()
            .all()
        )
        if not rows and self._attachment_cursor is not None:
            self._attachment_cursor = None
            rows = (
                (await session.execute(self._pending_attachment_statement(None)))
                .scalars()
                .all()
            )
        return rows

    async def _sweep_documents(self, session: AsyncSession) -> None:
        """Process a bounded, starvation-free batch of pending documents.

        Same starvation/staleness fix as ``_sweep_attachments`` -- a row that
        raised, or that came back ``RESULT_PENDING`` (no active provider
        configured for its organization yet), must not advance the cursor
        past it -- adapted for ``Document.document_id`` being an opaque
        string primary key rather than an auto-incrementing integer: there
        is no ``id - 1`` to fall back on, so instead of capping at "first
        unresolved row minus one" this tracks the id of the last row
        actually confirmed resolved before any unresolved row, and never
        advances the cursor past that point. This is equivalent to the
        integer case for a contiguous key (both stop the cursor exactly at
        the position before the first unresolved row) and remains correct
        for a non-contiguous or non-numeric key.
        """
        rows = await self._load_pending_documents(session)
        last_resolved_id = self._document_cursor
        unresolved = False
        for document_id in [document.document_id for document in rows]:
            try:
                document = await session.get(Document, document_id)
                if document is None:
                    if not unresolved:
                        last_resolved_id = document_id
                    continue
                result = await process_pending_document(
                    session=session,
                    document=document,
                    config_resolver=self._config_resolver,
                    request_fn=self._request_fn,
                )
                await session.commit()
                if result == RESULT_PENDING:
                    unresolved = True
                else:
                    if not unresolved:
                        last_resolved_id = document_id
                    logger.info(
                        "NewsDOM document %s recognition result: %s",
                        document_id,
                        result,
                    )
            except Exception:
                await session.rollback()
                logger.error(
                    "NewsDOM document %s recognition raised.",
                    document_id,
                    exc_info=True,
                )
                unresolved = True
        if rows:
            self._document_cursor = (
                last_resolved_id if unresolved else rows[-1].document_id
            )

    def _pending_document_statement(self, after_id: str | None):
        """Build the next deterministic workspace-document batch query."""
        statement = select(Document).where(
            Document.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS
        )
        if after_id is not None:
            statement = statement.where(Document.document_id > after_id)
        return statement.order_by(Document.document_id).limit(self.batch_limit)

    async def _load_pending_documents(self, session: AsyncSession) -> list[Document]:
        """Load after the last attempted document and wrap at the tail."""
        rows = (
            (
                await session.execute(
                    self._pending_document_statement(self._document_cursor)
                )
            )
            .scalars()
            .all()
        )
        if not rows and self._document_cursor is not None:
            self._document_cursor = None
            rows = (
                (await session.execute(self._pending_document_statement(None)))
                .scalars()
                .all()
            )
        return rows
