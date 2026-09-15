import asyncio
import datetime
from collections import defaultdict
from email import policy as email_policy
import hashlib
import logging
import mailbox
import os
import stat
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from sqlalchemy import bindparam, event, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from core.config import settings
from db.session import engine
from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    KnowledgeGraphEdgeRecord,
)
from services.archive import extract_backup_async
from services.batch_embedding_service import (
    BatchEmbeddingPartial,
    try_batch_import_embeddings,
)
from services.circuit_breaker import CircuitOpenError
from services.content_graph import ParseResult, parse_content
from services.email_dedupe_service import strong_email_fingerprint
from services.email_parser import EmailData, parse_eml_bytes
from services.embedding import (
    STORAGE_EMBEDDING_DIMENSION,
    fit_embedding_vector,
    generate_embeddings,
    split_embedding_inputs,
)
from services.exceptions import ArchiveError, EmailParseError, EmbeddingGenerationError
from services.project_graph import (
    ProjectSourceSegment,
    persist_project_graph_projection,
)
from services.project_graph.extractor_registry import (
    KgExtractorContext,
    run_extraction,
)
from services.threading_service import (
    assign_thread_id,
    generate_email_fingerprint,
    normalize_message_id,
)

EMBEDDING_DIMENSION = STORAGE_EMBEDDING_DIMENSION
MAX_IMPORT_UPLOADS = 10
# Transport safety ceiling only; parser and embedding chunking must accept
# sources larger than 20 MiB without confusing the request guard for a parser
# limit.
MAX_IMPORT_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_IMPORT_EML_FILES = 100
MAX_IMPORT_EMAILS_PER_OWNER = 1000
MAX_UPLOAD_FILENAME_DECODE_ROUNDS = 8
MAX_EMBEDDING_CHUNKS_PER_WINDOW = 32
SUPPORTED_EMAIL_IMPORT_SUFFIXES = frozenset({".eml", ".mbox", ".zip"})
EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE = "naruon-email-import-quota"
logger = logging.getLogger(__name__)

EmailImportItemStatus = Literal["imported", "skipped_duplicate", "failed"]


class EmailImportQuotaExceeded(Exception):
    pass


@dataclass(frozen=True)
class EmailImportUpload:
    filename: str
    content: bytes


@dataclass(frozen=True)
class EmailImportEmbeddingProvider:
    api_key: str
    base_url: str | None
    embedding_model: str
    embedding_base_url: str | None = None


@dataclass(frozen=True)
class EmailImportBatchContext:
    """Scope needed to route bulk import embeddings via contextual-orchestrator.

    Carried alongside the embedding provider so ``_generate_import_embeddings``
    can resolve per-tenant batch settings (Fernet DB), submit the batch to the
    orchestrator, and record batch jobs.
    """

    session: AsyncSession
    user_id: str
    organization_id: str | None


EmailContentParseResults = tuple[ParseResult, tuple[ParseResult | None, ...]]


@dataclass
class EmailImportItemResult:
    filename: str
    status: EmailImportItemStatus
    reason_code: str | None = None
    attachment_count: int = 0


@dataclass
class EmailImportResult:
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    attachment_count: int = 0
    items: list[EmailImportItemResult] = field(default_factory=list)

    def add_item(self, item: EmailImportItemResult) -> None:
        self.items.append(item)
        if item.status == "imported":
            self.imported_count += 1
            self.attachment_count += item.attachment_count
        elif item.status == "skipped_duplicate":
            self.skipped_count += 1
        else:
            self.failed_count += 1


def _canonical_upload_filename(filename: str | None) -> str | None:
    decoded = filename or ""
    for _ in range(MAX_UPLOAD_FILENAME_DECODE_ROUNDS):
        next_name = urllib.parse.unquote(decoded)
        if next_name == decoded:
            break
        decoded = next_name
    if urllib.parse.unquote(decoded) != decoded:
        return None

    if any(unicodedata.category(character).startswith("C") for character in decoded):
        return None

    # pathlib on POSIX does not treat a backslash as a separator. Normalize both
    # separator forms before selecting the final filename component.
    name = Path(decoded.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        return None
    return name


def canonical_email_import_upload_filename(filename: str | None) -> str | None:
    """Return a supported canonical upload basename, or fail closed."""
    canonical_name = _canonical_upload_filename(filename)
    if (
        canonical_name is None
        or Path(canonical_name).suffix.lower() not in SUPPORTED_EMAIL_IMPORT_SUFFIXES
    ):
        return None
    return canonical_name


def _safe_upload_filename(filename: str | None) -> str:
    return _canonical_upload_filename(filename) or "upload"


def _safe_item_filename(upload_name: str, eml_path: Path | None = None) -> str:
    safe_upload_name = _safe_upload_filename(upload_name)
    if eml_path is None:
        return safe_upload_name
    safe_item_name = _safe_upload_filename(eml_path.name)
    if safe_item_name == safe_upload_name:
        return safe_upload_name
    return f"{safe_upload_name}:{safe_item_name}"


def _utc_datetime(value: object) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc)


def _fallback_message_id(content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    return f"import-{digest}@local.naruon"


def _message_id_for(parsed: EmailData, content: bytes) -> str:
    return normalize_message_id(parsed.get("message_id")) or _fallback_message_id(
        content
    )


def _email_fingerprint(parsed: EmailData, persisted_date: datetime.datetime) -> str:
    strong_fingerprint = strong_email_fingerprint(
        sender=parsed.get("sender"),
        subject=parsed.get("subject"),
        date=persisted_date,
        body=parsed.get("body"),
    )
    if strong_fingerprint:
        return strong_fingerprint
    return generate_email_fingerprint(
        parsed.get("subject"),
        persisted_date.isoformat(),
        parsed.get("sender"),
        parsed.get("recipients"),
    )


async def _find_existing_email(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str,
    message_id: str,
    fingerprint: str,
) -> Email | None:
    message_lookup_values = {message_id, f"<{message_id}>"}
    result = await session.execute(
        select(Email).where(
            *Email.owner_filters(user_id, organization_id),
            or_(
                Email.message_id.in_(message_lookup_values),
                Email.fingerprint == fingerprint,
            ),
        )
    )
    return result.scalar_one_or_none()


async def _owner_email_import_count(
    session: AsyncSession, *, user_id: str, organization_id: str
) -> int:
    count = await session.scalar(
        select(func.count(Email.id)).where(
            *Email.owner_filters(user_id, organization_id)
        )
    )
    return int(count or 0)


def _session_uses_postgresql(session: AsyncSession) -> bool:
    try:
        bind = session.get_bind()
    except Exception:
        return False
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


def _owner_import_lock_key(user_id: str, organization_id: str) -> str:
    """Return a PostgreSQL-text-safe, collision-resistant owner lock key."""
    if "\x00" in user_id or "\x00" in organization_id:
        raise ValueError("email import owner identity contains NUL")
    return hashlib.sha256(
        user_id.encode("utf-8")
        + b"\x00"
        + organization_id.encode("utf-8")
    ).hexdigest()


async def _acquire_owner_import_quota_lock(
    session: AsyncSession, *, user_id: str, organization_id: str
) -> AsyncConnection | bool | None:
    """Hold an owner lease across item commits; discard unconfirmed acquisition."""
    if not _session_uses_postgresql(session):
        return None
    lock_params = {
        "namespace_key": EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE,
        "owner_key": _owner_import_lock_key(user_id, organization_id),
    }
    # The import session binds to its caller's held connection so each item can
    # commit without returning the leased socket or needing a second pool slot.
    # Standalone helper callers still own a dedicated lease connection.
    if isinstance(session, AsyncSession):
        session_bind = getattr(session, "bind", None)
        lock_connection = (
            session_bind
            if isinstance(session_bind, AsyncConnection)
            else await engine.connect()
        )
        try:
            await lock_connection.execute(
                select(
                    func.pg_advisory_lock(
                        func.hashtext(bindparam("namespace_key")),
                        func.hashtext(bindparam("owner_key")),
                    )
                ),
                lock_params,
            )
        except BaseException:
            await _close_owner_import_connection(lock_connection, discard_connection=True)
            raise
        return lock_connection

    # Lightweight PostgreSQL test doubles retain the old query contract.
    await session.execute(
        select(
            func.pg_advisory_lock(
                func.hashtext(bindparam("namespace_key")),
                func.hashtext(bindparam("owner_key")),
            )
        ),
        lock_params,
    )
    return True


async def _close_owner_import_connection(
    lock_connection: AsyncConnection, *, discard_connection: bool
) -> None:
    """Complete lease cleanup even if the caller is cancelled again while waiting."""
    async def close_connection() -> None:
        """Discard an uncertain socket before returning its pool slot."""
        try:
            if discard_connection:
                await lock_connection.invalidate()
        finally:
            await lock_connection.close()

    cleanup_task = asyncio.create_task(close_connection())
    interrupted_cleanup = False
    while True:
        try:
            await asyncio.shield(cleanup_task)
            break
        except asyncio.CancelledError:
            if cleanup_task.cancelled():
                raise
            interrupted_cleanup = True
    if interrupted_cleanup:
        raise asyncio.CancelledError


async def _release_owner_import_quota_lock(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str,
    lock: AsyncConnection | bool | None,
) -> None:
    """Return a lease connection only after PostgreSQL confirms its unlock."""
    if lock is not None and lock is not True:
        try:
            lock_params = {
                "namespace_key": EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE,
                "owner_key": _owner_import_lock_key(user_id, organization_id),
            }
            lock_result = await lock.execute(
                select(
                    func.pg_advisory_unlock(
                        func.hashtext(bindparam("namespace_key")),
                        func.hashtext(bindparam("owner_key")),
                    )
                ),
                lock_params,
            )
            if lock_result.scalar_one() is not True:
                raise RuntimeError("email import lease release unconfirmed")
            await lock.commit()
        except BaseException:
            await _close_owner_import_connection(lock, discard_connection=True)
            raise
        else:
            await _close_owner_import_connection(lock, discard_connection=False)
        return
    if lock is not True:
        return

    lock_params = {
        "namespace_key": EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE,
        "owner_key": _owner_import_lock_key(user_id, organization_id),
    }
    await session.execute(
        select(
            func.pg_advisory_unlock(
                func.hashtext(bindparam("namespace_key")),
                func.hashtext(bindparam("owner_key")),
            )
        ),
        lock_params,
    )


def _parse_email_content_results(
    parsed: EmailData,
    *,
    message_id: str,
    attachment_payloads: list[dict],
    owner_scope_key: str | None = None,
) -> EmailContentParseResults:
    """Scope persisted graph identities; embedding-only previews may omit scope."""
    source_scope = (owner_scope_key,) if owner_scope_key is not None else ()
    body_parse_result = parse_content(
        source_kind="email_body",
        source_record_uid=_content_graph_source_record_uid(
            "email", *source_scope, message_id
        ),
        content=str(parsed.get("body_parse_content") or parsed.get("body") or ""),
        content_type=str(parsed.get("body_content_type") or "text/plain"),
        display_name="Email body",
    )
    attachment_parse_results: list[ParseResult | None] = []
    for attachment_index, attachment_payload in enumerate(attachment_payloads, start=1):
        if attachment_payload.get("parse_status", "parsed") != "parsed":
            attachment_parse_results.append(None)
            continue
        parse_source_content = str(
            attachment_payload.get("parse_content")
            if attachment_payload.get("parse_content") is not None
            else attachment_payload.get("content") or ""
        )
        if not parse_source_content.strip():
            attachment_parse_results.append(None)
            continue
        attachment_parse_results.append(
            parse_content(
                source_kind="attachment",
                source_record_uid=_content_graph_source_record_uid(
                    "attachment",
                    *source_scope,
                    message_id,
                    str(attachment_index),
                    str(attachment_payload.get("filename") or "attachment.txt"),
                ),
                content=parse_source_content,
                content_type=str(
                    attachment_payload.get("parse_content_type")
                    or attachment_payload.get("content_type")
                    or "text/plain"
                ),
                display_name=str(
                    attachment_payload.get("filename") or "attachment.txt"
                ),
            )
        )
    return body_parse_result, tuple(attachment_parse_results)


def _semantic_embedding_inputs(
    parsed: EmailData,
    attachment_payloads: list[dict],
    parse_results: EmailContentParseResults,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Use persisted graph segments as embedding units before provider safety splits.

    ADR: Semantic graph segments are the primary units; the generic embedding
    boundary splitter remains only a physical context-limit fallback.
    See: docs/adr/0001-local-llm-and-orchestrator-boundary.md
    """
    body_parse_result, attachment_parse_results = parse_results
    source_results: list[ParseResult | None] = [
        body_parse_result,
        *attachment_parse_results,
    ]
    source_fallbacks = [
        str(parsed.get("body") or ""),
        *(
            str(attachment.get("content") or "")
            if (attachment.get("parse_status") or "parsed") == "parsed"
            else ""
            for attachment in attachment_payloads
        ),
    ]

    embedding_texts: list[str] = []
    source_ranges: list[tuple[int, int]] = []
    for parse_result, fallback_text in zip(source_results, source_fallbacks):
        semantic_texts = []
        if parse_result is not None:
            for segment in parse_result.segments:
                text = segment.safe_text_content.strip()
                if not text:
                    continue
                if segment.heading_path and segment.segment_kind != "heading":
                    text = f"{segment.heading_path}\n{text}"
                semantic_texts.append(text)
        if not semantic_texts and fallback_text:
            semantic_texts.append(fallback_text)
        start = len(embedding_texts)
        embedding_texts.extend(semantic_texts)
        source_ranges.append((start, len(embedding_texts)))
    return embedding_texts, source_ranges


def _pool_source_embeddings(
    embeddings: list[list[float]],
    source_ranges: list[tuple[int, int]],
    token_weights: list[int] | None = None,
) -> list[list[float]]:
    pooled: list[list[float]] = []
    for start, end in source_ranges:
        source_embeddings = embeddings[start:end]
        if not source_embeddings:
            pooled.append(_zero_embedding())
            continue
        weights = (
            token_weights[start:end]
            if token_weights is not None
            else [1] * len(source_embeddings)
        )
        total_weight = sum(weights) or len(source_embeddings)
        width = max(len(embedding) for embedding in source_embeddings)
        pooled.append(
            fit_embedding_vector(
                [
                    sum(
                        (
                            embedding[index] if index < len(embedding) else 0.0
                        )
                        * weights[embedding_index]
                        for embedding_index, embedding in enumerate(source_embeddings)
                    )
                    / total_weight
                    for index in range(width)
                ],
                EMBEDDING_DIMENSION,
            )
        )
    return pooled


async def _extract_and_generate_embeddings(
    parsed: EmailData,
    embedding_provider: EmailImportEmbeddingProvider | None,
    batch_context: "EmailImportBatchContext | None" = None,
    *,
    message_id: str | None = None,
    parse_results: EmailContentParseResults | None = None,
) -> tuple[list[dict], list[list[float]]]:
    attachment_payloads = list(parsed.get("attachments", []))
    parse_results = parse_results or _parse_email_content_results(
        parsed,
        message_id=str(parsed.get("message_id") or message_id or "email-import"),
        attachment_payloads=attachment_payloads,
        owner_scope_key=(
            _owner_import_lock_key(batch_context.user_id, batch_context.organization_id)
            if batch_context is not None and batch_context.organization_id is not None
            else None
        ),
    )
    embedding_texts, source_ranges = _semantic_embedding_inputs(
        parsed,
        attachment_payloads,
        parse_results,
    )
    semantic_embeddings = await _generate_import_embeddings(
        embedding_texts,
        embedding_provider=embedding_provider,
        batch_context=batch_context,
    )
    return attachment_payloads, _pool_source_embeddings(
        semantic_embeddings,
        source_ranges,
    )


def _build_email_object(
    *,
    parsed: EmailData,
    user_id: str,
    organization_id: str,
    message_id: str,
    thread_id: str | None,
    fingerprint: str,
    persisted_date: datetime.datetime,
    attachment_payloads: list[dict],
    fitted_embeddings: list[list[float]],
    parse_results: EmailContentParseResults | None = None,
) -> tuple[Email, int]:
    email_obj = Email(
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=fingerprint,
        sender=parsed.get("sender", ""),
        reply_to=parsed.get("reply_to"),
        recipients=parsed.get("recipients"),
        subject=parsed.get("subject"),
        in_reply_to=parsed.get("in_reply_to"),
        references=parsed.get("references"),
        date=persisted_date,
        body=parsed.get("body", ""),
        embedding=fitted_embeddings[0] if fitted_embeddings else _zero_embedding(),
    )

    attachment_count = 0
    for attachment_index, attachment in enumerate(attachment_payloads, start=1):
        attachment_content_type = str(
            attachment.get("content_type") or "application/octet-stream"
        )
        attachment_parse_status = str(attachment.get("parse_status") or "parsed")
        attachment_parse_content_type = str(
            attachment.get("parse_content_type") or attachment_content_type
        )
        attachment_parser_key = str(
            attachment.get("parser_key")
            or _fallback_attachment_parser_key(
                attachment_parse_content_type,
                attachment_parse_status,
            )
        )
        email_obj.attachments.append(
            Attachment(
                filename=str(attachment.get("filename") or "attachment.txt"),
                content=str(attachment.get("content") or ""),
                content_type=attachment_content_type,
                parse_status=attachment_parse_status,
                parse_content_type=attachment_parse_content_type,
                parser_key=attachment_parser_key,
                parse_error_code=(
                    str(attachment.get("parse_error_code"))
                    if attachment.get("parse_error_code") is not None
                    else None
                ),
                embedding=(
                    fitted_embeddings[attachment_index]
                    if attachment_index < len(fitted_embeddings)
                    else _zero_embedding()
                ),
            )
        )
        attachment_count += 1

    _append_email_content_graph(
        email_obj=email_obj,
        parsed=parsed,
        message_id=message_id,
        attachment_payloads=attachment_payloads,
        parse_results=parse_results,
    )
    _append_knowledge_graph_edges(email_obj)

    return email_obj, attachment_count


def _fallback_attachment_parser_key(
    parse_content_type: str,
    parse_status: str,
) -> str:
    if parse_status == "unsupported_content_type":
        return "unsupported_binary"
    if parse_content_type in {"application/json", "text/json"}:
        return "json"
    if parse_content_type in {"text/csv", "application/csv"}:
        return "csv"
    if parse_content_type in {"application/xml", "text/xml"}:
        return "xml"
    if parse_content_type == "text/calendar":
        return "calendar"
    if parse_content_type == "text/html":
        return "html"
    if parse_content_type in {
        "text/markdown",
        "text/x-markdown",
        "application/markdown",
    }:
        return "markdown"
    if parse_content_type == "text/plain":
        return "plain_text"
    return "unsupported_binary"


def _append_email_content_graph(
    *,
    email_obj: Email,
    parsed: EmailData,
    message_id: str,
    attachment_payloads: list[dict],
    parse_results: EmailContentParseResults | None = None,
) -> None:
    parse_results = parse_results or _parse_email_content_results(
        parsed,
        message_id=message_id,
        attachment_payloads=attachment_payloads,
        owner_scope_key=_owner_import_lock_key(
            email_obj.user_id, email_obj.organization_id
        ),
    )
    body_parse_result, attachment_parse_results = parse_results
    _append_parse_result_records(
        email_obj=email_obj,
        attachment_obj=None,
        parse_result=body_parse_result,
    )

    for attachment_obj, attachment_parse_result in zip(
        email_obj.attachments,
        attachment_parse_results,
    ):
        if attachment_parse_result is None:
            continue
        _append_parse_result_records(
            email_obj=email_obj,
            attachment_obj=attachment_obj,
            parse_result=attachment_parse_result,
        )


def _append_parse_result_records(
    *,
    email_obj: Email,
    attachment_obj: Attachment | None,
    parse_result: ParseResult,
) -> None:
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
        email_obj.content_nodes.append(node_record)
        if attachment_obj is not None:
            attachment_obj.content_nodes.append(node_record)
        node_records_by_uid[parsed_node.content_node_uid] = node_record

    for parsed_segment in parse_result.segments:
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
        node_records_by_uid[parsed_segment.content_node_uid].segments.append(
            segment_record
        )
        email_obj.content_segments.append(segment_record)
        if attachment_obj is not None:
            attachment_obj.content_segments.append(segment_record)


def _append_knowledge_graph_edges(email_obj: Email) -> None:
    nodes_by_uid = {
        node.content_node_uid: node
        for node in sorted(
            email_obj.content_nodes,
            key=lambda item: (
                item.source_kind,
                item.source_record_uid,
                item.ordinal_index,
                item.node_path,
            ),
        )
    }
    ordinal_index = 1

    def add_edge(
        *,
        edge_kind: str,
        edge_path: str,
        source_kind: str,
        source_record_uid: str,
        source_node: ContentNodeRecord | None = None,
        target_node: ContentNodeRecord | None = None,
        source_segment: ContentSegmentRecord | None = None,
        target_segment: ContentSegmentRecord | None = None,
    ) -> None:
        nonlocal ordinal_index
        edge = KnowledgeGraphEdgeRecord(
            edge_uid=_knowledge_graph_edge_uid(
                edge_kind,
                _edge_endpoint_uid(source_node, source_segment),
                _edge_endpoint_uid(target_node, target_segment),
                edge_path,
            ),
            source_kind=source_kind,
            source_record_uid=source_record_uid,
            edge_kind=edge_kind,
            edge_path=edge_path,
            ordinal_index=ordinal_index,
            source_node=source_node,
            target_node=target_node,
            source_segment=source_segment,
            target_segment=target_segment,
        )
        email_obj.knowledge_graph_edges.append(edge)
        attachment = _edge_attachment(
            source_node=source_node,
            target_node=target_node,
            source_segment=source_segment,
            target_segment=target_segment,
        )
        if attachment is not None:
            attachment.knowledge_graph_edges.append(edge)
        ordinal_index += 1

    for node in nodes_by_uid.values():
        if not node.parent_node_uid:
            continue
        parent_node = nodes_by_uid.get(node.parent_node_uid)
        if parent_node is None:
            continue
        add_edge(
            edge_kind="node_contains_node",
            edge_path=f"{parent_node.node_path}/contains/{node.node_path}",
            source_kind=node.source_kind,
            source_record_uid=node.source_record_uid,
            source_node=parent_node,
            target_node=node,
        )

    segments_by_source: dict[
        tuple[str, str],
        list[ContentSegmentRecord],
    ] = defaultdict(list)
    for segment in sorted(
        email_obj.content_segments,
        key=lambda item: (
            item.source_kind,
            item.source_record_uid,
            item.ordinal_index,
            item.segment_path,
        ),
    ):
        segments_by_source[(segment.source_kind, segment.source_record_uid)].append(
            segment
        )
        add_edge(
            edge_kind="node_has_segment",
            edge_path=f"{segment.content_node.node_path}/has/{segment.segment_path}",
            source_kind=segment.source_kind,
            source_record_uid=segment.source_record_uid,
            source_node=segment.content_node,
            target_segment=segment,
        )

    for (_source_kind, _source_record_uid), segments in segments_by_source.items():
        for source_segment, target_segment in zip(segments, segments[1:]):
            add_edge(
                edge_kind="segment_next",
                edge_path=(
                    f"{source_segment.segment_path}/next/{target_segment.segment_path}"
                ),
                source_kind=source_segment.source_kind,
                source_record_uid=source_segment.source_record_uid,
                source_segment=source_segment,
                target_segment=target_segment,
            )

        latest_heading_by_path: dict[str, ContentSegmentRecord] = {}
        for segment in segments:
            if segment.segment_kind == "heading" and segment.heading_path:
                latest_heading_by_path[segment.heading_path] = segment
                continue
            if segment.segment_kind != "paragraph" or not segment.heading_path:
                continue
            heading_segment = _nearest_heading_segment(
                segment.heading_path,
                latest_heading_by_path,
            )
            if heading_segment is None:
                continue
            add_edge(
                edge_kind="heading_contains_segment",
                edge_path=(
                    f"{heading_segment.segment_path}/contains/{segment.segment_path}"
                ),
                source_kind=segment.source_kind,
                source_record_uid=segment.source_record_uid,
                source_segment=heading_segment,
                target_segment=segment,
            )


def _edge_endpoint_uid(
    node: ContentNodeRecord | None,
    segment: ContentSegmentRecord | None,
) -> str:
    if segment is not None:
        return f"segment:{segment.content_segment_uid}"
    if node is not None:
        return f"node:{node.content_node_uid}"
    return "none"


def _edge_attachment(
    *,
    source_node: ContentNodeRecord | None,
    target_node: ContentNodeRecord | None,
    source_segment: ContentSegmentRecord | None,
    target_segment: ContentSegmentRecord | None,
) -> Attachment | None:
    for candidate in (source_segment, target_segment):
        if candidate is not None and candidate.attachment is not None:
            return candidate.attachment
    for candidate in (source_node, target_node):
        if candidate is not None and candidate.attachment is not None:
            return candidate.attachment
    return None


def _nearest_heading_segment(
    heading_path: str,
    latest_heading_by_path: dict[str, ContentSegmentRecord],
) -> ContentSegmentRecord | None:
    heading_parts = heading_path.split(" > ")
    while heading_parts:
        candidate = " > ".join(heading_parts)
        if candidate in latest_heading_by_path:
            return latest_heading_by_path[candidate]
        heading_parts.pop()
    return None


def _knowledge_graph_edge_uid(
    edge_kind: str,
    source_uid: str,
    target_uid: str,
    edge_path: str,
) -> str:
    payload = "\x00".join((edge_kind, source_uid, target_uid, edge_path))
    digest = hashlib.sha256(payload.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"kgedge_{digest[:32]}"


def _content_graph_source_record_uid(prefix: str, *parts: str) -> str:
    payload = "\x00".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"{prefix}:{digest[:32]}"


def _project_source_segments(email_obj: Email) -> list[ProjectSourceSegment]:
    """Snapshot the imported email's content segments as project source segments.

    Called before commit while ``email_obj.content_segments`` is the in-memory
    list populated by ``_append_email_content_graph`` (no DB IO), so it is safe
    to build in the async session context.
    """
    return [
        ProjectSourceSegment(
            content_segment_uid=segment.content_segment_uid,
            source_kind=segment.source_kind,
            source_record_uid=segment.source_record_uid,
            safe_text_content=segment.safe_text_content,
            heading_path=segment.heading_path,
            segment_path=segment.segment_path,
            ordinal_index=segment.ordinal_index,
        )
        for segment in email_obj.content_segments
    ]


async def _extract_project_semantics_for_import(
    source_segments: list[ProjectSourceSegment],
    *,
    embedding_provider: EmailImportEmbeddingProvider | None,
):
    """Project segments into the graph via the configured extractor seam.

    Resolution goes through the named+versioned KG extractor registry
    (``services.project_graph.extractor_registry``) keyed by
    ``settings.PROJECT_GRAPH_EXTRACTOR``. The LLM extractors reuse the import's
    OpenAI-compatible provider credentials and enforce segment citations, so
    they cannot introduce uncited claims; a missing credential, an unconfigured
    orchestrator endpoint, or any provider/parse failure degrades down the chain
    to the deterministic reference extractor instead of losing the projection.
    """
    context = KgExtractorContext(
        api_key=embedding_provider.api_key if embedding_provider else None,
        base_url=embedding_provider.base_url if embedding_provider else None,
        model=settings.OPENAI_MODEL,
        orchestrator_base_url=settings.PROJECT_GRAPH_ORCHESTRATOR_BASE_URL,
    )
    return await run_extraction(
        source_segments,
        selector=settings.PROJECT_GRAPH_EXTRACTOR,
        context=context,
    )


async def _persist_project_graph_projection(
    session: AsyncSession,
    source_segments: list[ProjectSourceSegment],
    *,
    user_id: str,
    organization_id: str,
    embedding_provider: EmailImportEmbeddingProvider | None = None,
) -> None:
    """Best-effort projection of imported content segments into the project graph.

    Runs after the email is already committed. Flag-gated and defensive: any
    failure is logged and rolled back so it never fails the email import. The
    workspace scope mirrors the convention enforced by the project graph
    repository (``workspace-<organization_id>``).
    """
    if not source_segments:
        return
    try:
        extraction = await _extract_project_semantics_for_import(
            source_segments, embedding_provider=embedding_provider
        )
        if not extraction.objects:
            return
        workspace_id = (
            f"workspace-{organization_id}"
            if organization_id
            else f"workspace-{user_id}"
        )
        await persist_project_graph_projection(
            session,
            extraction=extraction,
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning(
            "Project graph projection skipped for imported email",
            exc_info=True,
        )


async def _import_single_eml(
    session: AsyncSession,
    *,
    eml_path: Path,
    display_filename: str,
    user_id: str,
    organization_id: str,
    embedding_provider: EmailImportEmbeddingProvider | None = None,
    batch_context: "EmailImportBatchContext | None" = None,
) -> EmailImportItemResult:
    try:
        content, parsed = await asyncio.to_thread(_read_and_parse_eml, eml_path)
    except EmailParseError as exc:
        logger.warning(
            "Email import item failed: reason_code=parse_failed filename=%s error_type=%s",
            display_filename,
            type(exc).__name__,
        )
        return EmailImportItemResult(
            filename=display_filename,
            status="failed",
            reason_code="parse_failed",
        )

    message_id = _message_id_for(parsed, content)
    parsed["message_id"] = message_id
    persisted_date = _utc_datetime(parsed.get("date"))
    fingerprint = _email_fingerprint(parsed, persisted_date)

    existing_email = await _find_existing_email(
        session,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        fingerprint=fingerprint,
    )
    if existing_email is not None:
        return EmailImportItemResult(
            filename=display_filename,
            status="skipped_duplicate",
            reason_code="duplicate_email",
        )

    thread_id = await assign_thread_id(
        session,
        parsed,
        user_id=user_id,
        organization_id=organization_id,
    )

    attachment_payloads = list(parsed.get("attachments", []))
    parse_results = _parse_email_content_results(
        parsed,
        message_id=message_id,
        attachment_payloads=attachment_payloads,
        owner_scope_key=_owner_import_lock_key(user_id, organization_id),
    )
    attachment_payloads, fitted_embeddings = await _extract_and_generate_embeddings(
        parsed,
        embedding_provider,
        batch_context,
        message_id=message_id,
        parse_results=parse_results,
    )

    email_obj, attachment_count = _build_email_object(
        parsed=parsed,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=fingerprint,
        persisted_date=persisted_date,
        attachment_payloads=attachment_payloads,
        fitted_embeddings=fitted_embeddings,
        parse_results=parse_results,
    )

    project_source_segments = (
        _project_source_segments(email_obj)
        if settings.PROJECT_GRAPH_EXTRACTION_ENABLED
        else []
    )

    session.add(email_obj)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning(
            "Email import item failed: reason_code=database_commit_failed filename=%s",
            display_filename,
        )
        return EmailImportItemResult(
            filename=display_filename,
            status="failed",
            reason_code="database_commit_failed",
        )

    await _persist_project_graph_projection(
        session,
        project_source_segments,
        user_id=user_id,
        organization_id=organization_id,
        embedding_provider=embedding_provider,
    )

    return EmailImportItemResult(
        filename=display_filename,
        status="imported",
        attachment_count=attachment_count,
    )


def _read_and_parse_eml(eml_path: Path) -> tuple[bytes, EmailData]:
    content = _read_eml_bytes(eml_path)
    return content, parse_eml_bytes(content)


def _zero_embedding() -> list[float]:
    return [0.0] * EMBEDDING_DIMENSION


async def _generate_import_embeddings(
    texts: list[str],
    *,
    embedding_provider: EmailImportEmbeddingProvider | None,
    batch_context: "EmailImportBatchContext | None" = None,
) -> list[list[float]]:
    if not texts:
        return []
    if embedding_provider is None:
        return [_zero_embedding() for _ in texts]
    batch_texts, batch_ranges, batch_token_weights = split_embedding_inputs(
        texts, embedding_provider.embedding_model
    )
    if batch_context is not None and texts:
        # Bulk import embeddings are latency-tolerant: route them through
        # contextual-orchestrator first. A None result means batch is
        # unconfigured/unavailable, so we transparently fall through to the
        # existing per-request path below.
        batched = await try_batch_import_embeddings(
            batch_context.session,
            batch_texts,
            embedding_provider=embedding_provider,
            user_id=batch_context.user_id,
            organization_id=batch_context.organization_id,
            dimension=EMBEDDING_DIMENSION,
        )
        if batched is not None:
            if isinstance(batched, BatchEmbeddingPartial):
                remainder: list[list[float]] = []
                for start in range(
                    0, len(batched.pending_texts), MAX_EMBEDDING_CHUNKS_PER_WINDOW
                ):
                    remainder.extend(
                        await _generate_import_embeddings(
                            batched.pending_texts[
                                start : start + MAX_EMBEDDING_CHUNKS_PER_WINDOW
                            ],
                            embedding_provider=embedding_provider,
                            batch_context=None,
                        )
                    )
                return _pool_source_embeddings(
                    [*batched.completed_vectors, *remainder],
                    batch_ranges,
                    batch_token_weights,
                )
            return _pool_source_embeddings(
                batched,
                batch_ranges,
                batch_token_weights,
            )
    try:
        provider_embeddings = await generate_embeddings(
            texts,
            embedding_provider.api_key,
            base_url=embedding_provider.embedding_base_url
            or embedding_provider.base_url,
            model=embedding_provider.embedding_model,
        )
    except (CircuitOpenError, EmbeddingGenerationError, ValueError) as exc:
        logger.warning(
            "Email import embedding generation failed; retrying imported content "
            "item by item before zero-vector fallback: "
            "error_type=%s text_count=%s",
            type(exc).__name__,
            len(texts),
        )
        recovered: list[list[float]] = []
        for index, text in enumerate(texts):
            try:
                single_embedding = await generate_embeddings(
                    [text],
                    embedding_provider.api_key,
                    base_url=embedding_provider.embedding_base_url
                    or embedding_provider.base_url,
                    model=embedding_provider.embedding_model,
                )
                if not single_embedding:
                    recovered.append(_zero_embedding())
                    continue
                recovered.append(
                    fit_embedding_vector(single_embedding[0], EMBEDDING_DIMENSION)
                )
            except (
                CircuitOpenError,
                EmbeddingGenerationError,
                ValueError,
                TypeError,
                IndexError,
            ) as item_exc:
                logger.warning(
                    "Email import embedding item retry failed; falling back to zero "
                    "vector for imported content: error_type=%s embedding_index=%s",
                    type(item_exc).__name__,
                    index,
                )
                recovered.append(_zero_embedding())
        return recovered

    fitted: list[list[float]] = []
    for index in range(len(texts)):
        if index >= len(provider_embeddings):
            fitted.append(_zero_embedding())
            continue
        try:
            fitted.append(
                fit_embedding_vector(provider_embeddings[index], EMBEDDING_DIMENSION)
            )
        except ValueError as exc:
            logger.warning(
                "Email import embedding fit failed; falling back to zero vector "
                "for imported content: error_type=%s embedding_index=%s",
                type(exc).__name__,
                index,
            )
            fitted.append(_zero_embedding())
    return fitted


def _read_eml_bytes(eml_path: Path) -> bytes:
    no_follow_flag = getattr(os, "O_NOFOLLOW", None)
    path_stat = None
    if no_follow_flag is None:
        try:
            path_stat = eml_path.lstat()
        except OSError as exc:
            raise EmailParseError("Failed to read email file") from exc
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
            raise EmailParseError("Failed to read email file")

    open_flags = os.O_RDONLY
    if no_follow_flag is not None:
        open_flags |= no_follow_flag
    file_descriptor_transferred = False
    try:
        file_descriptor = os.open(eml_path, open_flags)
    except OSError as exc:
        raise EmailParseError("Failed to read email file") from exc

    try:
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise EmailParseError("Failed to read email file")
        if path_stat is not None and (
            getattr(file_stat, "st_ino", None) != getattr(path_stat, "st_ino", None)
            or getattr(file_stat, "st_dev", None) != getattr(path_stat, "st_dev", None)
        ):
            raise EmailParseError("Failed to read email file")
        file_handle = os.fdopen(file_descriptor, "rb")
        file_descriptor_transferred = True
        with file_handle:
            return file_handle.read()
    except OSError as exc:
        raise EmailParseError("Failed to read email file") from exc
    finally:
        if not file_descriptor_transferred:
            os.close(file_descriptor)


async def _eml_paths_for_upload(
    *,
    upload: EmailImportUpload,
    upload_dir: Path,
) -> tuple[list[Path], str | None]:
    upload_name = _safe_upload_filename(upload.filename)
    upload_path = upload_dir / upload_name
    try:
        await asyncio.to_thread(upload_path.write_bytes, upload.content)
    except OSError:
        return [], "file_write_failed"

    suffix = upload_path.suffix.lower()
    if suffix == ".eml":
        return [upload_path], None
    if suffix == ".mbox":
        return _eml_paths_for_mbox_upload(upload_path, upload_dir)
    if suffix != ".zip":
        return [], "unsupported_file_type"

    extract_dir = upload_dir / "extracted"
    try:
        extracted_paths = await extract_backup_async(upload_path, extract_dir)
    except ArchiveError:
        return [], "archive_extract_failed"

    # _read_eml_bytes() performs the final no-follow regular-file validation.
    eml_paths = [path for path in extracted_paths if path.suffix.lower() == ".eml"]
    if not eml_paths:
        return [], "archive_contains_no_eml"
    if len(eml_paths) > MAX_IMPORT_EML_FILES:
        return [], "archive_too_many_eml_files"
    return eml_paths, None


def _eml_paths_for_mbox_upload(
    upload_path: Path,
    upload_dir: Path,
) -> tuple[list[Path], str | None]:
    extract_dir = upload_dir / "mbox"
    extract_dir.mkdir(parents=True, exist_ok=True)

    parsed_mailbox = None
    try:
        parsed_mailbox = mailbox.mbox(upload_path, create=False)
        eml_paths: list[Path] = []
        for index, message in enumerate(parsed_mailbox, start=1):
            if len(eml_paths) >= MAX_IMPORT_EML_FILES:
                return [], "mbox_too_many_eml_files"
            eml_path = extract_dir / f"message_{index:06d}.eml"
            eml_path.write_bytes(message.as_bytes(policy=email_policy.default))
            eml_paths.append(eml_path)
    except (OSError, mailbox.Error, UnicodeError, ValueError):
        return [], "mbox_parse_failed"
    finally:
        if parsed_mailbox is not None:
            parsed_mailbox.close()

    if not eml_paths:
        return [], "mbox_contains_no_eml"
    return eml_paths, None


async def import_email_uploads(
    session: AsyncSession,
    *,
    uploads: list[EmailImportUpload],
    user_id: str,
    organization_id: str,
    embedding_provider: EmailImportEmbeddingProvider | None = None,
) -> EmailImportResult:
    """Import with one held connection, including an existing provider lookup."""
    if isinstance(session, AsyncSession) and _session_uses_postgresql(session):
        if session.new or session.dirty or session.deleted:
            raise ValueError("email import requires settled caller state")
        import_connection = await session.connection()
        import_session = AsyncSession(
            bind=import_connection,
            expire_on_commit=False,
            join_transaction_mode="control_fully",
        )
        leased_driver = import_connection.sync_connection.connection.dbapi_connection

        def reject_reconnected_import(
            database_connection,
            database_cursor,
            query_statement,
            query_parameters,
            execution_context,
            execute_many,
        ):
            """A replacement socket cannot execute SQL under a lost owner's lease."""
            if database_connection.connection.dbapi_connection is not leased_driver:
                raise RuntimeError("email import lease connection lost")

        event.listen(
            import_connection.sync_connection,
            "before_cursor_execute",
            reject_reconnected_import,
        )
        try:
            return await _import_email_uploads_on_session(
                import_session,
                uploads=uploads,
                user_id=user_id,
                organization_id=organization_id,
                embedding_provider=embedding_provider,
            )
        finally:
            try:
                try:
                    await import_session.close()
                finally:
                    await session.close()
            finally:
                event.remove(
                    import_connection.sync_connection,
                    "before_cursor_execute",
                    reject_reconnected_import,
                )
    return await _import_email_uploads_on_session(
        session,
        uploads=uploads,
        user_id=user_id,
        organization_id=organization_id,
        embedding_provider=embedding_provider,
    )


async def _import_email_uploads_on_session(
    session: AsyncSession,
    *,
    uploads: list[EmailImportUpload],
    user_id: str,
    organization_id: str,
    embedding_provider: EmailImportEmbeddingProvider | None,
) -> EmailImportResult:
    """Keep quota planning and every item transaction inside the owner lease."""
    lock_acquired = await _acquire_owner_import_quota_lock(
        session, user_id=user_id, organization_id=organization_id
    )
    batch_context = EmailImportBatchContext(
        session=session,
        user_id=user_id,
        organization_id=organization_id,
    )
    try:
        result = EmailImportResult()
        existing_email_count = await _owner_email_import_count(
            session, user_id=user_id, organization_id=organization_id
        )
        remaining_quota = MAX_IMPORT_EMAILS_PER_OWNER - existing_email_count
        if remaining_quota <= 0:
            raise EmailImportQuotaExceeded()

        with TemporaryDirectory(prefix="naruon-email-import-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            planned_imports: list[tuple[str, Path]] = []
            for index, upload in enumerate(uploads):
                upload_name = _safe_upload_filename(upload.filename)
                upload_dir = temp_dir / f"upload_{index}"
                upload_dir.mkdir(parents=True, exist_ok=True)
                eml_paths, failure_reason = await _eml_paths_for_upload(
                    upload=upload,
                    upload_dir=upload_dir,
                )
                if failure_reason is not None:
                    logger.warning(
                        "Email import upload failed: reason_code=%s filename=%s",
                        failure_reason,
                        upload_name,
                    )
                    result.add_item(
                        EmailImportItemResult(
                            filename=upload_name,
                            status="failed",
                            reason_code=failure_reason,
                        )
                    )
                    continue

                planned_imports.extend(
                    (
                        _safe_item_filename(upload_name, eml_path),
                        eml_path,
                    )
                    for eml_path in eml_paths
                )

            if len(planned_imports) > remaining_quota:
                raise EmailImportQuotaExceeded()

            for display_filename, eml_path in planned_imports:
                result.add_item(
                    await _import_single_eml(
                        session,
                        eml_path=eml_path,
                        display_filename=display_filename,
                        user_id=user_id,
                        organization_id=organization_id,
                        embedding_provider=embedding_provider,
                        batch_context=batch_context,
                    )
                )
    finally:
        if lock_acquired is not None:
            await _release_owner_import_quota_lock(
                session,
                user_id=user_id,
                organization_id=organization_id,
                lock=lock_acquired,
            )

    return result
