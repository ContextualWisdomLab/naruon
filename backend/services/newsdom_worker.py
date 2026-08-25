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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Document,
    Email,
)
from db.session import AsyncSessionLocal
from services.attachment_parser import decode_deferred_attachment_payload
from services.content_graph import ParseResult
from services.newsdom_client import (
    NewsdomConfigurationError,
    NewsdomPayloadTooLargeError,
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
    except NewsdomPayloadTooLargeError as exc:
        attachment.parse_status = PDF_DOM_RECOGNITION_FAILED_STATUS
        attachment.parse_error_code = "provider_payload_size_exceeded"
        # A bounded, expected admission rejection is operational information,
        # not an infrastructure warning; the persisted error code remains the
        # customer-visible source of truth.
        logger.info(
            "NewsDOM attachment %s exceeds the provider payload contract: %s",
            getattr(attachment, "id", "?"),
            exc,
        )
        return RESULT_FAILED
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


def _session_uses_postgresql(session: AsyncSession) -> bool:
    """Return whether advisory-lock SQL is supported by the session bind."""
    try:
        bind = session.get_bind()
    except Exception:
        return False
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


async def _try_acquire_sweep_lease(session: AsyncSession) -> bool | None:
    """Become the sweep leader for this cycle (None when not PostgreSQL)."""
    if not _session_uses_postgresql(session):
        return None
    acquired = await session.scalar(
        select(
            func.pg_try_advisory_lock(
                func.hashtext(bindparam("namespace_key")),
                func.hashtext(bindparam("sweep_key")),
            )
        ),
        _SWEEP_LOCK_PARAMS,
    )
    return bool(acquired)


async def _release_sweep_lease(session: AsyncSession) -> None:
    """Release the PostgreSQL advisory lock for a recognition sweep."""
    await session.scalar(
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
    payloads/responses are marked failed rather than parsed.
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
        """Process one leased attachment and document sweep."""
        async with AsyncSessionLocal() as session:
            lease = await _try_acquire_sweep_lease(session)
            if lease is False:
                logger.debug(
                    "NewsDOM recognition sweep skipped: another replica holds "
                    "the lease."
                )
                return
            try:
                await self._sweep_attachments(session)
                await self._sweep_documents(session)
            finally:
                if lease is True:
                    await _release_sweep_lease(session)

    async def _sweep_attachments(self, session: AsyncSession) -> None:
        """Process a bounded, starvation-free batch of pending attachments."""
        rows = await self._load_pending_attachments(session)
        if rows:
            self._attachment_cursor = rows[-1].id
        for attachment in rows:
            try:
                result = await process_pending_attachment(
                    session=session,
                    attachment=attachment,
                    config_resolver=self._config_resolver,
                    request_fn=self._request_fn,
                )
                await session.commit()
                if result != RESULT_PENDING:
                    logger.info(
                        "NewsDOM attachment %s recognition result: %s",
                        attachment.id,
                        result,
                    )
            except Exception:
                await session.rollback()
                logger.error(
                    "NewsDOM attachment %s recognition raised.",
                    getattr(attachment, "id", "?"),
                    exc_info=True,
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
        """Process a bounded, starvation-free batch of pending documents."""
        rows = await self._load_pending_documents(session)
        if rows:
            self._document_cursor = rows[-1].document_id
        for document in rows:
            try:
                result = await process_pending_document(
                    session=session,
                    document=document,
                    config_resolver=self._config_resolver,
                    request_fn=self._request_fn,
                )
                await session.commit()
                if result != RESULT_PENDING:
                    logger.info(
                        "NewsDOM document %s recognition result: %s",
                        document.document_id,
                        result,
                    )
            except Exception:
                await session.rollback()
                logger.error(
                    "NewsDOM document %s recognition raised.",
                    getattr(document, "document_id", "?"),
                    exc_info=True,
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
