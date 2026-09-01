"""Background worker glue for re-evaluating quarantined attachments.

``POST /api/data/attachments/{attachment_uid}/reparse-intent`` moves a
``content_type_mismatch_quarantined`` attachment to ``reparse_pending``,
retaining its raw bytes (base64) but performing no synchronous re-parse (see
``docs/adr/0005-attachment-content-type-quarantine.md``). This worker sweeps
``reparse_pending`` rows and replays the exact same classification pipeline
(:func:`services.attachment_parser.parse_email_attachment`) against those
retained bytes and the attachment's original declared ``content_type`` -- so
a fix to that pipeline (e.g. the OOXML/ODF/EPUB/JAR false-positive
carve-out) is automatically picked up on the next reparse pass with no
bespoke logic here. An attachment whose disagreement was genuine simply
lands back in the quarantine status; nothing here decides that on its own.
"""

from __future__ import annotations

import asyncio
import logging
import random

from sqlalchemy import bindparam, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from db.models import Attachment, ContentNodeRecord, ContentSegmentRecord
from db.session import AsyncSessionLocal, engine
from services.attachment_parser import (
    AttachmentParseResult,
    decode_quarantined_attachment_payload,
    parse_email_attachment,
)
from services.content_graph import content_graph_source_record_uid, parse_content

logger = logging.getLogger(__name__)
_sysrand = random.SystemRandom()

DEFAULT_ATTACHMENT_REPARSE_INTERVAL_SECONDS = 60
DEFAULT_ATTACHMENT_REPARSE_BATCH_LIMIT = 10
ATTACHMENT_REPARSE_SWEEP_LOCK_NAMESPACE = "naruon-attachment-reparse-sweep"
MAX_STARTUP_JITTER_SECONDS = 30

# Mirrors api.data.ATTACHMENT_REPARSE_PENDING_STATUS. Duplicated as a literal
# (not imported) to avoid a services -> api import: api already imports from
# services, and this worker has no other reason to depend on the router module.
ATTACHMENT_REPARSE_PENDING_STATUS = "reparse_pending"
# A retained payload that is not valid base64 cannot become valid on a later
# sweep -- a terminal, non-retryable data problem, not a transient one.
ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS = "reparse_payload_invalid"

# Per-item processing outcome for the one case this worker can never turn
# into a fresh AttachmentParseResult. Every other outcome is reported as the
# resulting parse_status itself (e.g. "parsed", the quarantine status again,
# "unsupported_content_type") so a caller sees exactly what classification
# decided, not a coarse success/failure flag.
RESULT_DECODE_FAILED = "decode_failed"

_SWEEP_LOCK_PARAMS = {
    "namespace_key": ATTACHMENT_REPARSE_SWEEP_LOCK_NAMESPACE,
    "sweep_key": "sweep",
}


def apply_reparsed_result(*, attachment: Attachment, result: AttachmentParseResult) -> None:
    """Land a fresh classification result onto an existing attachment row.

    ``filename`` and ``content_type`` are not overwritten: they are the
    attachment's identity and the sender's original declaration, neither of
    which a reparse pass should silently rewrite (``parse_email_attachment``
    only ever normalizes them for a *new* row, and the retained
    ``attachment.content_type`` is what is fed back in as its input here).

    ``content`` is only overwritten when the result actually has content to
    store. A reparse that lands on a status with no displayable content
    (``unsupported_content_type``, ``parse_size_limit_exceeded``) returns
    ``content=""`` by design -- storing that would destroy the only retained
    copy of the original quarantined bytes, permanently losing a file that
    later parser support could otherwise still recover.

    A reparse that lands on ``"parsed"`` also indexes the recognized content
    into the content graph, mirroring what the initial import path already
    does for an attachment that parses cleanly on first import
    (``email_import_service._append_email_content_graph``) -- without this, a
    previously-quarantined attachment stayed invisible to content-graph-backed
    search/AI-hub features even after successful reparse recognition.
    """
    if result.content:
        attachment.content = result.content
    attachment.parse_content_type = result.parse_content_type
    attachment.parser_key = result.parser_key
    attachment.parse_status = result.parse_status
    attachment.parse_error_code = result.parse_error_code
    if result.parse_status == "parsed":
        _append_reparsed_attachment_content_graph(attachment=attachment, result=result)


def _append_reparsed_attachment_content_graph(
    *, attachment: Attachment, result: AttachmentParseResult
) -> None:
    """Build content graph records for a successfully reparsed attachment.

    Reuses the same ``parse_content`` helper and ``source_record_uid``
    identity convention (``content_graph_source_record_uid``) the import path
    uses in ``email_import_service._append_email_content_graph`` -- this is
    not a second indexing path, just a second call site for the same one.

    It differs only in how the new records attach to their parents. The
    import path appends to a transient ``Email``/``Attachment`` pair (neither
    has a real id yet) and lets SQLAlchemy's relationship cascade resolve
    ``email_id``/``attachment_id`` at flush time. Here ``attachment`` is
    already a persisted row with a stable, permanent ``attachment_uid``, so
    ``source_record_uid`` is keyed on that uid alone (not the message-id +
    list-position convention the import path uses, since a persisted
    attachment's position among its email's siblings is not reliably
    reproducible) and ``email_id`` is taken directly from the attachment's
    already-loaded ``email_id`` column instead of an ``Email`` relationship
    append.
    """
    parse_source_content = result.parse_content or result.content
    if not parse_source_content.strip():
        return

    parse_result = parse_content(
        source_kind="attachment",
        source_record_uid=content_graph_source_record_uid(
            "attachment", attachment.attachment_uid
        ),
        content=parse_source_content,
        content_type=result.parse_content_type or result.content_type or "text/plain",
        display_name=attachment.filename,
    )

    node_records_by_uid: dict[str, ContentNodeRecord] = {}
    for parsed_node in parse_result.nodes:
        node_record = ContentNodeRecord(
            email_id=attachment.email_id,
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
        attachment.content_nodes.append(node_record)
        node_records_by_uid[parsed_node.content_node_uid] = node_record

    for parsed_segment in parse_result.segments:
        segment_record = ContentSegmentRecord(
            email_id=attachment.email_id,
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
        node_records_by_uid[parsed_segment.content_node_uid].segments.append(
            segment_record
        )
        attachment.content_segments.append(segment_record)


def process_reparse_pending_attachment(*, attachment: Attachment) -> str:
    """Re-evaluate one ``reparse_pending`` attachment in place.

    Returns the resulting ``parse_status`` on a successful re-evaluation
    (``"parsed"``, the quarantine status again, or any other terminal status
    ``parse_email_attachment`` can return), or ``RESULT_DECODE_FAILED`` when
    the retained payload itself is not valid base64 -- moved to a dedicated
    failure status so the sweep does not retry it forever.
    """
    try:
        raw_content = decode_quarantined_attachment_payload(attachment.content)
    except ValueError as exc:
        attachment.parse_status = ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS
        attachment.parse_error_code = ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS
        logger.warning(
            "Attachment %s reparse rejected: %s",
            getattr(attachment, "id", "?"),
            exc,
        )
        return RESULT_DECODE_FAILED

    result = parse_email_attachment(
        filename=attachment.filename,
        content_type=attachment.content_type,
        raw_content=raw_content,
    )
    apply_reparsed_result(attachment=attachment, result=result)
    return result.parse_status


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
    recycled or closed.

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


class AttachmentReparseWorker:
    """Periodically re-evaluate ``reparse_pending`` attachments.

    Mirrors :class:`services.newsdom_worker.NewsdomRecognitionWorker`: a
    jittered periodic loop, a PostgreSQL advisory-lock lease so only one
    replica sweeps per cycle, per-item error isolation, and a starvation-free
    cursor. Unlike that worker, re-evaluation never depends on an external
    provider being configured, so there is no "left pending, retry later"
    outcome here -- every row is fully resolved (to a parsed status, back to
    quarantine, or to the dedicated payload-invalid failure) on its very
    first sweep.
    """

    def __init__(
        self,
        *,
        interval_seconds: int = DEFAULT_ATTACHMENT_REPARSE_INTERVAL_SECONDS,
        batch_limit: int = DEFAULT_ATTACHMENT_REPARSE_BATCH_LIMIT,
    ):
        """Configure the sweep cadence and batch size."""
        self.interval_seconds = interval_seconds
        self.batch_limit = batch_limit
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._attachment_cursor: int | None = None

    async def start(self) -> None:
        """Start the reparse loop once."""
        if self._is_running:
            logger.warning("AttachmentReparseWorker is already running.")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AttachmentReparseWorker started.")

    async def stop(self) -> None:
        """Cancel and await the active reparse loop."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("AttachmentReparseWorker cancellation acknowledged.")
        logger.info("AttachmentReparseWorker stopped.")

    async def _run_loop(self) -> None:
        """Run jittered reparse sweeps until stopped."""
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
                logger.error("Error in AttachmentReparseWorker loop.", exc_info=True)
            if self._is_running:
                try:
                    await asyncio.sleep(self.interval_seconds)
                except asyncio.CancelledError:
                    break

    async def _sweep(self) -> None:
        """Process one leased reparse sweep.

        The advisory lock (when the engine supports it) is acquired and
        released on one dedicated connection held open for the whole sweep --
        never through the per-item ``AsyncSession`` used by
        ``_sweep_attachments``. See ``_try_acquire_sweep_lease`` for why that
        distinction matters.
        """
        if not _engine_uses_postgresql():
            async with AsyncSessionLocal() as session:
                await self._sweep_attachments(session)
            return
        async with engine.connect() as lock_connection:
            if not await _try_acquire_sweep_lease(lock_connection):
                logger.debug(
                    "Attachment reparse sweep skipped: another replica holds "
                    "the lease."
                )
                return
            try:
                async with AsyncSessionLocal() as session:
                    await self._sweep_attachments(session)
            finally:
                await _release_sweep_lease(lock_connection)

    async def _sweep_attachments(self, session: AsyncSession) -> None:
        """Process a bounded, starvation-free batch of reparse-pending rows.

        The cursor only advances past a row once it is confirmed resolved
        (its status actually left ``reparse_pending``, whether to a parsed
        state or back to quarantine). A row whose processing raised keeps its
        ``reparse_pending`` status untouched, so if the cursor advanced past
        it anyway it would never be reselected by
        ``_load_reparse_pending_attachments``'s ``id > cursor`` filter until
        the whole forward queue happens to drain to empty -- silent,
        indefinite starvation of that one row under continuous inbound
        reparse-intent traffic. Capping the cursor at the first failure keeps
        that row (and, harmlessly, any already-resolved rows after it that
        the ``parse_status`` filter will simply skip) in range for the next
        sweep.
        """
        rows = await self._load_reparse_pending_attachments(session)
        first_failed_id = None
        for attachment_id in [attachment.id for attachment in rows]:
            try:
                # Re-fetch fresh rather than reusing the bulk-loaded instance:
                # AsyncSession.rollback() expires every object already loaded
                # in this session, and process_reparse_pending_attachment
                # reads attachment attributes synchronously -- a stale,
                # expired instance from an earlier item's failure would raise
                # on that read instead of just isolating the one failure.
                # Fetching fresh here sidesteps that whole class of bug
                # regardless of exactly when SQLAlchemy decides to expire.
                attachment = await session.get(Attachment, attachment_id)
                if attachment is None:
                    continue
                result = process_reparse_pending_attachment(attachment=attachment)
                await session.commit()
                logger.info(
                    "Attachment %s reparse result: %s",
                    attachment_id,
                    result,
                )
            except Exception:
                await session.rollback()
                logger.error(
                    "Attachment %s reparse raised.",
                    attachment_id,
                    exc_info=True,
                )
                if first_failed_id is None:
                    first_failed_id = attachment_id
        if rows:
            self._attachment_cursor = (
                first_failed_id - 1 if first_failed_id is not None else rows[-1].id
            )

    def _reparse_pending_statement(self, after_id: int | None):
        """Build the next deterministic reparse-pending batch query."""
        statement = select(Attachment).where(
            Attachment.parse_status == ATTACHMENT_REPARSE_PENDING_STATUS
        )
        if after_id is not None:
            statement = statement.where(Attachment.id > after_id)
        return statement.order_by(Attachment.id).limit(self.batch_limit)

    async def _load_reparse_pending_attachments(
        self, session: AsyncSession
    ) -> list[Attachment]:
        """Load after the last attempted row, wrapping at the table tail.

        Every row this worker touches is fully resolved on its first sweep
        (see the class docstring), so wrapping only matters when a batch
        landed exactly on the cursor's row -- it still keeps the cursor
        logic identical to the NewsDOM worker's, rather than a subtly
        different variant for one fewer edge case.
        """
        rows = (
            (
                await session.execute(
                    self._reparse_pending_statement(self._attachment_cursor)
                )
            )
            .scalars()
            .all()
        )
        if not rows and self._attachment_cursor is not None:
            self._attachment_cursor = None
            rows = (
                (await session.execute(self._reparse_pending_statement(None)))
                .scalars()
                .all()
            )
        return rows
