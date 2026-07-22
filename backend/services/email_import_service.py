import asyncio
import urllib.parse
import datetime
import hashlib
import logging
import mailbox
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from sqlalchemy import bindparam, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    KnowledgeGraphEdgeRecord,
)
from services.archive import extract_backup_async
from services.batch_embedding_service import try_batch_import_embeddings
from services.content_graph import ParseResult, parse_content
from services.email_dedupe_service import (
    email_strong_fingerprint,
    strong_email_fingerprint,
)
from services.email_service import generate_email_fingerprint
from services.email_parser import EmailData, parse_eml_bytes
from services.embedding import (
    STORAGE_EMBEDDING_DIMENSION,
    fit_embedding_vector,
    generate_embeddings,
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
    normalize_message_id,
)

EMBEDDING_DIMENSION = STORAGE_EMBEDDING_DIMENSION
MAX_IMPORT_UPLOADS = 10
MAX_IMPORT_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMPORT_EML_FILES = 100
MAX_IMPORT_ARCHIVE_EXTRACT_BYTES = MAX_IMPORT_UPLOAD_BYTES
MAX_IMPORT_ARCHIVE_FILES = MAX_IMPORT_EML_FILES
MAX_IMPORT_EMAILS_PER_OWNER = 1000
EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE = "naruon-email-import-quota"
MAX_UPLOAD_FILENAME_DECODE_ROUNDS = 5
SUPPORTED_EMAIL_IMPORT_SUFFIXES = frozenset({".eml", ".mbox", ".zip"})
SOURCE_TIME_EVIDENCE_PRECEDENCE = [
    "embedded_metadata",
    "explicit_filename_date",
    "filesystem_created_at",
    "filesystem_modified_at",
]
logger = logging.getLogger(__name__)

EmailImportItemStatus = Literal["imported", "skipped_duplicate", "failed"]
DedupeMatchReason = Literal[
    "embedded_message_id",
    "raw_content_sha256",
    "complete_source_fingerprint",
]


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


@dataclass
class EmailImportItemResult:
    filename: str
    status: EmailImportItemStatus
    reason_code: str | None = None
    attachment_count: int = 0
    dedupe_review_required: bool = False
    dedupe_reason_codes: list[str] = field(default_factory=list)
    dedupe_match_reason: DedupeMatchReason | None = None


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
    decoded_filename = filename or ""
    for _ in range(MAX_UPLOAD_FILENAME_DECODE_ROUNDS):
        next_filename = urllib.parse.unquote(decoded_filename)
        if next_filename == decoded_filename:
            break
        decoded_filename = next_filename
    else:
        if urllib.parse.unquote(decoded_filename) != decoded_filename:
            return None

    if not decoded_filename.isprintable():
        return None

    # Treat both network/client path separators as separators, independently of
    # the operating system that hosts the backend.
    normalized_filename = decoded_filename.replace("\\", "/")
    name = Path(normalized_filename).name.strip()
    if not name or name in {".", ".."}:
        return None
    return name


def canonical_email_import_upload_filename(filename: str | None) -> str | None:
    """Return one supported canonical upload basename, or fail closed."""
    canonical_name = _canonical_upload_filename(filename)
    if (
        canonical_name is None
        or Path(canonical_name).suffix.lower() not in SUPPORTED_EMAIL_IMPORT_SUFFIXES
    ):
        return None
    return canonical_name


def _safe_upload_filename(filename: str | None) -> str:
    return _canonical_upload_filename(filename) or "upload"


def _safe_display_filename_component(filename: str | None) -> str:
    normalized_filename = (filename or "").replace("\\", "/")
    name = Path(normalized_filename).name.strip()
    sanitized_name = "".join(
        character if character.isprintable() else "_"
        for character in name
    ).strip()
    if sanitized_name in {"", ".", ".."}:
        return "upload"
    return sanitized_name


def _safe_item_filename(upload_name: str, eml_path: Path | None = None) -> str:
    safe_upload_name = _safe_upload_filename(upload_name)
    if eml_path is None:
        return safe_upload_name
    safe_item_name = _safe_display_filename_component(eml_path.name)
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


def _message_identity_for(
    parsed: EmailData, content: bytes
) -> tuple[str, DedupeMatchReason]:
    embedded_message_id = normalize_message_id(parsed.get("message_id"))
    if parsed.get("message_id_evidence_status") == "embedded" and embedded_message_id:
        return embedded_message_id, "embedded_message_id"
    return _fallback_message_id(content), "raw_content_sha256"


def _email_fingerprint(parsed: EmailData) -> str | None:
    source_date = parsed.get("source_date")
    if parsed.get("date_evidence_status") != "parsed" or not isinstance(
        source_date, datetime.datetime
    ):
        return None
    return strong_email_fingerprint(
        sender=parsed.get("sender"),
        subject=parsed.get("subject"),
        date=_utc_datetime(source_date),
        body=parsed.get("body"),
    )


def _legacy_email_fingerprint(parsed: EmailData) -> str | None:
    source_date = parsed.get("source_date")
    if parsed.get("date_evidence_status") != "parsed" or not isinstance(
        source_date, datetime.datetime
    ):
        return None
    sender = parsed.get("sender")
    subject = parsed.get("subject")
    body = parsed.get("body")
    if not (
        sender
        and sender.strip()
        and subject
        and subject.strip()
        and body
        and body.strip()
    ):
        return None
    return generate_email_fingerprint(
        {
            "sender": sender,
            "subject": subject,
            "date": _utc_datetime(source_date).isoformat(),
            "body": body,
        }
    )


def _dedupe_review_reason_codes(
    parsed: EmailData, fingerprint: str | None
) -> list[str]:
    reason_codes: list[str] = []
    date_evidence_status = parsed.get("date_evidence_status")
    if date_evidence_status == "missing":
        reason_codes.append("date_evidence_missing")
    elif date_evidence_status == "invalid":
        reason_codes.append("date_evidence_invalid")
    elif date_evidence_status != "parsed" or not isinstance(
        parsed.get("source_date"), datetime.datetime
    ):
        reason_codes.append("date_evidence_unavailable")

    message_id_evidence_status = parsed.get("message_id_evidence_status")
    if message_id_evidence_status == "invalid":
        reason_codes.append("message_id_evidence_invalid")
    elif message_id_evidence_status != "embedded":
        reason_codes.append("message_id_evidence_missing")
    if fingerprint is None:
        reason_codes.append("complete_source_fingerprint_unavailable")
    return reason_codes


def _source_lineage_for(
    parsed: EmailData,
    *,
    content: bytes,
    display_filename: str,
    identity_match_reason: DedupeMatchReason,
) -> dict[str, object]:
    """Build bounded source evidence without trusting temporary file timestamps."""
    source_date = parsed.get("source_date")
    date_evidence_status = parsed.get("date_evidence_status")
    has_embedded_date = date_evidence_status == "parsed" and isinstance(
        source_date, datetime.datetime
    )
    message_id_evidence_status = parsed.get("message_id_evidence_status")

    return {
        "schema_version": 1,
        "source_kind": "rfc822",
        "source_filename": display_filename,
        "raw_content_sha256": hashlib.sha256(content).hexdigest(),
        "production_time": {
            "selected_value": (
                _utc_datetime(source_date).isoformat() if has_embedded_date else None
            ),
            "selected_source": ("embedded_date_header" if has_embedded_date else None),
            "embedded_status": (
                date_evidence_status
                if date_evidence_status in {"parsed", "missing", "invalid"}
                else "missing"
            ),
            "evidence_precedence": list(SOURCE_TIME_EVIDENCE_PRECEDENCE),
        },
        "message_identity": {
            "selected_source": (
                "embedded_message_id"
                if identity_match_reason == "embedded_message_id"
                else "raw_content_sha256"
            ),
            "embedded_status": (
                message_id_evidence_status
                if message_id_evidence_status in {"embedded", "missing", "invalid"}
                else "missing"
            ),
        },
    }


async def _find_existing_email(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str,
    message_id: str,
    identity_match_reason: DedupeMatchReason,
    fingerprint: str | None,
    legacy_fingerprint: str | None,
) -> tuple[Email | None, DedupeMatchReason | None]:
    message_lookup_values = {message_id, f"<{message_id}>"}
    dedupe_conditions = [Email.message_id.in_(message_lookup_values)]
    fingerprint_lookup_values = {
        value for value in (fingerprint, legacy_fingerprint) if value is not None
    }
    if fingerprint_lookup_values:
        dedupe_conditions.append(Email.fingerprint.in_(fingerprint_lookup_values))
    result = await session.execute(
        select(Email).where(
            *Email.owner_filters(user_id, organization_id),
            or_(*dedupe_conditions),
        )
    )
    existing_emails = result.scalars().all()
    for existing_email in existing_emails:
        if normalize_message_id(existing_email.message_id) == message_id:
            return existing_email, identity_match_reason
    if fingerprint is not None:
        for existing_email in existing_emails:
            stored_fingerprint = existing_email.fingerprint
            if stored_fingerprint == fingerprint:
                return existing_email, "complete_source_fingerprint"
            if (
                legacy_fingerprint is not None
                and stored_fingerprint == legacy_fingerprint
            ):
                # Legacy fingerprints truncate the body. Require the full-source
                # fingerprint too, so a shared 500-character prefix is not a match.
                if email_strong_fingerprint(existing_email) == fingerprint:
                    return existing_email, "complete_source_fingerprint"
                continue
            if email_strong_fingerprint(existing_email) == fingerprint:
                return existing_email, "complete_source_fingerprint"
    return None, None


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


async def _acquire_owner_import_quota_lock(
    session: AsyncSession, *, user_id: str, organization_id: str
) -> bool:
    if not _session_uses_postgresql(session):
        return False
    lock_params = {
        "namespace_key": EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE,
        "owner_key": f"{user_id}\x00{organization_id}",
    }
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


async def _release_owner_import_quota_lock(
    session: AsyncSession, *, user_id: str, organization_id: str
) -> None:
    lock_params = {
        "namespace_key": EMAIL_IMPORT_QUOTA_LOCK_NAMESPACE,
        "owner_key": f"{user_id}\x00{organization_id}",
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


async def _extract_and_generate_embeddings(
    parsed: EmailData,
    embedding_provider: EmailImportEmbeddingProvider | None,
    batch_context: "EmailImportBatchContext | None" = None,
) -> tuple[list[dict], list[list[float]]]:
    attachment_payloads = list(parsed.get("attachments", []))
    embedding_texts = [str(parsed.get("body") or "")]
    embedding_texts.extend(
        str(attachment.get("content") or "") for attachment in attachment_payloads
    )
    fitted_embeddings = await _generate_import_embeddings(
        embedding_texts,
        embedding_provider=embedding_provider,
        batch_context=batch_context,
    )
    return attachment_payloads, fitted_embeddings


def _build_email_object(
    *,
    parsed: EmailData,
    user_id: str,
    organization_id: str,
    message_id: str,
    thread_id: str | None,
    fingerprint: str | None,
    persisted_date: datetime.datetime,
    source_lineage_json: dict[str, object],
    attachment_payloads: list[dict],
    fitted_embeddings: list[list[float]],
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
        source_lineage_json=source_lineage_json,
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
) -> None:
    body_parse_result = parse_content(
        source_kind="email_body",
        source_record_uid=_content_graph_source_record_uid("email", message_id),
        content=str(parsed.get("body_parse_content") or parsed.get("body") or ""),
        content_type=str(parsed.get("body_content_type") or "text/plain"),
        display_name="Email body",
    )
    _append_parse_result_records(
        email_obj=email_obj,
        attachment_obj=None,
        parse_result=body_parse_result,
    )

    for attachment_index, (attachment_obj, attachment_payload) in enumerate(
        zip(email_obj.attachments, attachment_payloads),
        start=1,
    ):
        if attachment_payload.get("parse_status", "parsed") != "parsed":
            continue
        parse_source_content = str(
            attachment_payload.get("parse_content")
            if attachment_payload.get("parse_content") is not None
            else attachment_payload.get("content") or ""
        )
        if not parse_source_content.strip():
            continue
        attachment_parse_result = parse_content(
            source_kind="attachment",
            source_record_uid=_content_graph_source_record_uid(
                "attachment",
                message_id,
                str(attachment_index),
                attachment_obj.filename,
            ),
            content=parse_source_content,
            content_type=str(
                attachment_payload.get("parse_content_type")
                or attachment_payload.get("content_type")
                or "text/plain"
            ),
            display_name=attachment_obj.filename,
        )
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
    ] = {}
    for segment in sorted(
        email_obj.content_segments,
        key=lambda item: (
            item.source_kind,
            item.source_record_uid,
            item.ordinal_index,
            item.segment_path,
        ),
    ):
        segments_by_source.setdefault(
            (segment.source_kind, segment.source_record_uid),
            [],
        ).append(segment)
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
    to the deterministic keyword baseline instead of losing the projection.
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
            "Email import item failed: reason_code=parse_failed filename=%r error_type=%s",
            display_filename,
            type(exc).__name__,
        )
        return EmailImportItemResult(
            filename=display_filename,
            status="failed",
            reason_code="parse_failed",
        )

    message_id, identity_match_reason = _message_identity_for(parsed, content)
    parsed["message_id"] = message_id
    persisted_date = _utc_datetime(parsed.get("date"))
    fingerprint = _email_fingerprint(parsed)
    legacy_fingerprint = _legacy_email_fingerprint(parsed)

    existing_email, dedupe_match_reason = await _find_existing_email(
        session,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        identity_match_reason=identity_match_reason,
        fingerprint=fingerprint,
        legacy_fingerprint=legacy_fingerprint,
    )
    if existing_email is not None:
        return EmailImportItemResult(
            filename=display_filename,
            status="skipped_duplicate",
            reason_code="duplicate_email",
            dedupe_match_reason=dedupe_match_reason,
        )

    thread_id = await assign_thread_id(
        session,
        parsed,
        user_id=user_id,
        organization_id=organization_id,
    )

    attachment_payloads, fitted_embeddings = await _extract_and_generate_embeddings(
        parsed, embedding_provider, batch_context
    )

    email_obj, attachment_count = _build_email_object(
        parsed=parsed,
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id=thread_id,
        fingerprint=fingerprint,
        persisted_date=persisted_date,
        source_lineage_json=_source_lineage_for(
            parsed,
            content=content,
            display_filename=display_filename,
            identity_match_reason=identity_match_reason,
        ),
        attachment_payloads=attachment_payloads,
        fitted_embeddings=fitted_embeddings,
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
            "Email import item failed: reason_code=database_commit_failed filename=%r",
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

    dedupe_reason_codes = _dedupe_review_reason_codes(parsed, fingerprint)
    return EmailImportItemResult(
        filename=display_filename,
        status="imported",
        attachment_count=attachment_count,
        dedupe_review_required=bool(dedupe_reason_codes),
        dedupe_reason_codes=dedupe_reason_codes,
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
    if embedding_provider is None:
        return [_zero_embedding() for _ in texts]
    if batch_context is not None and texts:
        # Bulk import embeddings are latency-tolerant: route them through
        # contextual-orchestrator first. A None result means batch is
        # unconfigured/unavailable, so we transparently fall through to the
        # existing per-request path below.
        batched = await try_batch_import_embeddings(
            batch_context.session,
            texts,
            embedding_provider=embedding_provider,
            user_id=batch_context.user_id,
            organization_id=batch_context.organization_id,
            dimension=EMBEDDING_DIMENSION,
        )
        if batched is not None:
            return batched
    try:
        provider_embeddings = await generate_embeddings(
            texts,
            embedding_provider.api_key,
            base_url=embedding_provider.base_url,
            model=embedding_provider.embedding_model,
        )
    except (EmbeddingGenerationError, ValueError) as exc:
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
                    base_url=embedding_provider.base_url,
                    model=embedding_provider.embedding_model,
                )
                if not single_embedding:
                    recovered.append(_zero_embedding())
                    continue
                recovered.append(
                    fit_embedding_vector(single_embedding[0], EMBEDDING_DIMENSION)
                )
            except (
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
    upload_name = canonical_email_import_upload_filename(upload.filename)
    if upload_name is None:
        return [], "unsupported_file_type"
    upload_path = upload_dir / upload_name
    try:
        await asyncio.to_thread(upload_path.write_bytes, upload.content)
    except (OSError, ValueError):
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
        extracted_paths = await extract_backup_async(
            upload_path,
            extract_dir,
            max_extract_size=MAX_IMPORT_ARCHIVE_EXTRACT_BYTES,
            max_file_count=MAX_IMPORT_ARCHIVE_FILES,
        )
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
        for index, key in enumerate(parsed_mailbox.iterkeys(), start=1):
            if len(eml_paths) >= MAX_IMPORT_EML_FILES:
                return [], "mbox_too_many_eml_files"
            eml_path = extract_dir / f"message_{index:06d}.eml"
            eml_path.write_bytes(parsed_mailbox.get_bytes(key, from_=False))
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
                        "Email import upload failed: reason_code=%s filename=%r",
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
        if lock_acquired:
            await _release_owner_import_quota_lock(
                session, user_id=user_id, organization_id=organization_id
            )

    return result
