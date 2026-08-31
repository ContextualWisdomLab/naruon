"""Deterministic, bounded BagIt/RO-Crate envelopes for tenant provenance."""

from __future__ import annotations

import hashlib
import io
import json
import math
import stat
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    KnowledgeGraphEdgeRecord,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
)


ARCHIVE_MAX_BYTES = 64 * 1024 * 1024
ARCHIVE_MAX_ENTRIES = 64
ENTRY_MAX_BYTES = 32 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
JSON_MAX_DEPTH = 64
JSON_SAFE_INTEGER_MAX = 2**53 - 1
_MAX_IDENTIFIER_LENGTH = 256
_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_PAYLOAD_NAME = "data/records.json"
_LOCAL_FILE_SIGNATURE = b"PK\x03\x04"
_EOCD_SIGNATURE = b"PK\x05\x06"
_EOCD_SIZE = 22
_EXPECTED_ENTRIES = frozenset(
    {
        "bagit.txt",
        "bag-info.txt",
        "manifest-sha512.txt",
        "tagmanifest-sha512.txt",
        "ro-crate-metadata.json",
        _PAYLOAD_NAME,
    }
)
_COLLECTIONS = (
    "emails",
    "attachments",
    "content_nodes",
    "content_segments",
    "structural_edges",
    "project_objects",
    "project_edges",
    "corrections",
)
_TEXTUAL_PARSER_KEYS = frozenset(
    {"plain_text", "html", "markdown", "json", "csv", "xml", "calendar", "pdf"}
)
_RECORD_KEYS = {
    "emails": frozenset(
        {
            "email_uid",
            "thread_uid",
            "fingerprint",
            "sender",
            "reply_to",
            "recipients",
            "subject",
            "in_reply_to",
            "references",
            "date",
            "body",
            "is_read",
        }
    ),
    "attachments": frozenset(
        {
            "attachment_uid",
            "email_uid",
            "filename",
            "content",
            "content_type",
            "parse_status",
            "parse_content_type",
            "parser_key",
            "parse_error_code",
        }
    ),
    "content_nodes": frozenset(
        {
            "content_node_uid",
            "email_uid",
            "attachment_uid",
            "source_kind",
            "source_record_uid",
            "parent_node_uid",
            "node_kind",
            "node_path",
            "ordinal_index",
            "display_label",
            "safe_text_content",
            "content_hash",
        }
    ),
    "content_segments": frozenset(
        {
            "content_segment_uid",
            "email_uid",
            "attachment_uid",
            "content_node_uid",
            "source_kind",
            "source_record_uid",
            "segment_kind",
            "segment_path",
            "ordinal_index",
            "heading_path",
            "safe_text_content",
            "content_hash",
            "word_count",
        }
    ),
    "structural_edges": frozenset(
        {
            "edge_uid",
            "email_uid",
            "attachment_uid",
            "source_node_uid",
            "target_node_uid",
            "source_segment_uid",
            "target_segment_uid",
            "source_kind",
            "source_record_uid",
            "edge_kind",
            "edge_path",
            "ordinal_index",
        }
    ),
    "project_objects": frozenset(
        {
            "object_uid",
            "email_uid",
            "attachment_uid",
            "primary_content_segment_uid",
            "object_type",
            "title",
            "summary",
            "status_code",
            "confidence",
            "source_segment_uids",
            "attributes_json",
            "extractor_name",
            "extractor_version",
        }
    ),
    "project_edges": frozenset(
        {
            "edge_uid",
            "source_uid",
            "target_uid",
            "edge_type",
            "confidence",
            "source_segment_uids",
            "source_object_uid",
            "target_object_uid",
            "primary_content_segment_uid",
        }
    ),
    "corrections": frozenset(
        {
            "correction_uid",
            "object_uid",
            "correction_action",
            "before_json",
            "after_json",
            "rationale",
            "source_segment_uids",
            "created_at",
        }
    ),
}


class ProvenanceArchiveError(ValueError):
    """Raised when a provenance envelope is malformed or outside this profile."""


@dataclass(frozen=True)
class TenantProvenanceScope:
    """Signed-session authority used for every source read and target write."""

    user_id: str
    organization_id: str | None
    workspace_id: str


@dataclass(frozen=True)
class ImportReceipt:
    """Verified import outcome without exposing persistence identifiers."""

    bundle_uid: str
    manifest_digest: str
    created: dict[str, int]
    skipped: dict[str, int]


def _fail() -> None:
    raise ProvenanceArchiveError("Invalid provenance archive")


def _validate_json_value(value: object, depth: int = 0) -> None:
    if depth > JSON_MAX_DEPTH:
        _fail()
    if value is None or isinstance(value, (str, bool)):
        return
    if type(value) is int:
        if not -JSON_SAFE_INTEGER_MAX <= value <= JSON_SAFE_INTEGER_MAX:
            _fail()
        return
    if isinstance(value, float):
        _fail()
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, depth + 1)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail()
            if not key.isascii():
                _fail()
            _validate_json_value(item, depth + 1)
        return
    _fail()


def _canonical_json(value: object) -> bytes:
    _validate_json_value(value)
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc


def _records_bundle_uid(records: Mapping[str, object]) -> str:
    schema_version = records.get("schema_version")
    if (
        records.get("profile") != "naruon-tenant-provenance/v1"
        or type(schema_version) is not int
        or schema_version != 1
    ):
        _fail()
    return _safe_identifier(records.get("bundle_uid"))


def _safe_identifier(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_IDENTIFIER_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _fail()
    return value


def _iso8601_date_or_datetime(value: object) -> str:
    date_published = _safe_identifier(value)
    try:
        date.fromisoformat(date_published)
    except ValueError:
        try:
            datetime.fromisoformat(date_published)
        except ValueError:
            _fail()
    return date_published


def _bag_info(bundle_uid: str) -> bytes:
    return (
        "Bag-Software-Agent: naruon\n"
        "Bagging-Date: 1980-01-01\n"
        f"External-Identifier: {bundle_uid}\n"
    ).encode("utf-8")


def _ro_crate(records: Mapping[str, object], payload_digest: str) -> bytes:
    activity = records.get("export_activity")
    if not isinstance(activity, Mapping):
        _fail()
    activity_uid = _safe_identifier(activity.get("activity_uid"))
    date_published = _iso8601_date_or_datetime(activity.get("date_published"))
    crate = {
        "@context": [
            "https://w3id.org/ro/crate/1.3/context",
            {"prov": "http://www.w3.org/ns/prov#"},
        ],
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.3"},
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "conformsTo": "naruon-tenant-provenance/v1",
                "datePublished": date_published,
                "hasPart": {"@id": _PAYLOAD_NAME},
                "name": "Naruon tenant provenance bundle",
            },
            {
                "@id": _PAYLOAD_NAME,
                "@type": "File",
                "encodingFormat": "application/json",
                "sha512": payload_digest,
            },
            {
                "@id": f"#{activity_uid}",
                "@type": ["CreateAction", "prov:Activity"],
                "instrument": {"@id": "#naruon"},
                "object": {"@id": _PAYLOAD_NAME},
                "prov:used": {"@id": "./"},
                "prov:wasAssociatedWith": {"@id": "#naruon"},
            },
            {
                "@id": "#naruon",
                "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
                "name": "Naruon",
            },
        ],
    }
    return _canonical_json(crate)


def _manifest(entries: Mapping[str, bytes], names: tuple[str, ...]) -> bytes:
    return b"".join(
        f"{hashlib.sha512(entries[name]).hexdigest()}  {name}\n".encode("ascii")
        for name in names
    )


def _archive_entries(records: Mapping[str, object]) -> dict[str, bytes]:
    payload = _canonical_json(records)
    bundle_uid = _records_bundle_uid(records)
    entries = {
        "bagit.txt": b"BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n",
        "bag-info.txt": _bag_info(bundle_uid),
        _PAYLOAD_NAME: payload,
        "ro-crate-metadata.json": _ro_crate(
            records, hashlib.sha512(payload).hexdigest()
        ),
    }
    entries["manifest-sha512.txt"] = _manifest(entries, (_PAYLOAD_NAME,))
    entries["tagmanifest-sha512.txt"] = _manifest(
        entries,
        ("bag-info.txt", "bagit.txt", "manifest-sha512.txt", "ro-crate-metadata.json"),
    )
    return entries


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_TIMESTAMP)
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.reserved = 0
    info.flag_bits = 0
    info.volume = 0
    info.internal_attr = 0
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    info.extra = b""
    info.comment = b""
    return info


def build_provenance_archive(records: Mapping[str, object]) -> bytes:
    """Build the fixed deterministic ZIP envelope for a validated record payload."""
    if not isinstance(records, Mapping):
        _fail()
    entries = _archive_entries(records)
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(entries):
            archive.writestr(
                _zip_info(name),
                entries[name],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    archive_bytes = output.getvalue()
    if len(archive_bytes) > ARCHIVE_MAX_BYTES:
        _fail()
    parse_provenance_archive(archive_bytes)
    return archive_bytes


def _is_unsafe_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    parts = name.split("/")
    return (
        not name
        or "\\" in name
        or "\x00" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or parts[0].endswith(":")
        or info.is_dir()
        or stat.S_ISLNK(info.external_attr >> 16)
        or bool(info.flag_bits & 0x1)
    )


def _has_fixed_metadata(info: zipfile.ZipInfo) -> bool:
    return (
        info.date_time == _FIXED_TIMESTAMP
        and info.create_system == 3
        and info.create_version == 20
        and info.extract_version == 20
        and info.reserved == 0
        and info.flag_bits == 0
        and info.volume == 0
        and info.internal_attr == 0
        and info.external_attr == (stat.S_IFREG | 0o644) << 16
        and info.compress_type == zipfile.ZIP_DEFLATED
        and info.extra == b""
        and info.comment == b""
    )


def _within_archive_bounds(
    *,
    archive_bytes: int,
    entry_count: int,
    total_bytes: int,
    entry_bytes: int,
    compressed_bytes: int,
) -> bool:
    return (
        0 <= archive_bytes <= ARCHIVE_MAX_BYTES
        and 0 <= entry_count <= ARCHIVE_MAX_ENTRIES
        and 0 <= total_bytes <= ARCHIVE_MAX_BYTES
        and 0 <= entry_bytes <= ENTRY_MAX_BYTES
        and compressed_bytes >= 0
        and (
            entry_bytes == 0
            or 0 < compressed_bytes
            and entry_bytes <= compressed_bytes * MAX_COMPRESSION_RATIO
        )
    )


def _has_profile_container_framing(archive_bytes: bytes | bytearray) -> bool:
    if (
        len(archive_bytes) < _EOCD_SIZE
        or not archive_bytes.startswith(_LOCAL_FILE_SIGNATURE)
        or archive_bytes[-_EOCD_SIZE:-18] != _EOCD_SIGNATURE
    ):
        return False
    (
        _,
        disk_number,
        directory_disk,
        entries_on_disk,
        entries,
        directory_size,
        directory_offset,
        comment_size,
    ) = struct.unpack("<4s4H2LH", archive_bytes[-_EOCD_SIZE:])
    return (
        disk_number == 0
        and directory_disk == 0
        and entries_on_disk == entries
        and entries != 0xFFFF
        and directory_size != 0xFFFFFFFF
        and directory_offset != 0xFFFFFFFF
        and comment_size == 0
        and directory_offset + directory_size == len(archive_bytes) - _EOCD_SIZE
    )


def _has_contiguous_member_data(infos: list[zipfile.ZipInfo], start_dir: int) -> bool:
    expected_offset = 0
    for info in infos:
        if info.header_offset != expected_offset:
            return False
        expected_offset += (
            zipfile.sizeFileHeader
            + len(info.filename.encode("ascii"))
            + len(info.extra)
            + info.compress_size
        )
    return expected_offset == start_dir


def _read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if not _within_archive_bounds(
        archive_bytes=0,
        entry_count=0,
        total_bytes=0,
        entry_bytes=info.file_size,
        compressed_bytes=info.compress_size,
    ):
        _fail()
    data = bytearray()
    try:
        with archive.open(info, "r") as source:
            while chunk := source.read(min(64 * 1024, ENTRY_MAX_BYTES + 1 - len(data))):
                data.extend(chunk)
                if len(data) > ENTRY_MAX_BYTES:
                    _fail()
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    if len(data) != info.file_size:
        _fail()
    return bytes(data)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail()
        value[key] = item
    return value


def _parse_records(data: bytes) -> dict[str, object]:
    try:
        records = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda _value: _fail(),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    if not isinstance(records, dict):
        _fail()
    if _canonical_json(records) != data:
        _fail()
    return records


def parse_provenance_archive(archive_bytes: bytes) -> dict[str, object]:
    """Validate a bounded fixed envelope and return its canonical record payload."""
    if (
        not isinstance(archive_bytes, (bytes, bytearray))
        or not _within_archive_bounds(
            archive_bytes=len(archive_bytes),
            entry_count=0,
            total_bytes=0,
            entry_bytes=0,
            compressed_bytes=0,
        )
        or not _has_profile_container_framing(archive_bytes)
    ):
        _fail()
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            if (
                archive.comment
                or not _within_archive_bounds(
                    archive_bytes=len(archive_bytes),
                    entry_count=len(infos),
                    total_bytes=sum(info.file_size for info in infos),
                    entry_bytes=0,
                    compressed_bytes=0,
                )
                or any(
                    _is_unsafe_member(info) or not _has_fixed_metadata(info)
                    for info in infos
                )
            ):
                _fail()
            names = [info.filename for info in infos]
            if (
                names != sorted(names)
                or len(set(names)) != len(names)
                or set(names) != _EXPECTED_ENTRIES
                or not _has_contiguous_member_data(infos, archive.start_dir)
            ):
                _fail()
            entries = {info.filename: _read_entry(archive, info) for info in infos}
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc

    records = _parse_records(entries[_PAYLOAD_NAME])
    expected = _archive_entries(records)
    if entries != expected:
        _fail()
    return records


def _scope_filters(model: Any, scope: TenantProvenanceScope, *, workspace: bool):
    organization_filter = (
        model.organization_id == scope.organization_id
        if scope.organization_id is not None
        else model.organization_id.is_(None)
    )
    filters = [model.user_id == scope.user_id, organization_filter]
    if workspace:
        filters.append(model.workspace_id == scope.workspace_id)
    return filters


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        _fail()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object) -> datetime:
    text_value = _safe_identifier(value)
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    if parsed.tzinfo is None:
        _fail()
    return parsed


def _confidence(value: float) -> str:
    if not math.isfinite(value):
        _fail()
    return repr(value)


def _parse_confidence(value: object) -> float:
    if not isinstance(value, str):
        _fail()
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    if not math.isfinite(parsed):
        _fail()
    return parsed


def _attachment_core(attachment: Attachment, email_uid: str) -> dict[str, object]:
    return {
        "email_uid": email_uid,
        "filename": attachment.filename,
        "content": attachment.content,
        "content_type": attachment.content_type,
        "parse_status": attachment.parse_status,
        "parse_content_type": attachment.parse_content_type,
        "parser_key": attachment.parser_key,
        "parse_error_code": attachment.parse_error_code,
    }


def _is_admitted_attachment(attachment: Attachment) -> bool:
    return (
        attachment.parse_status == "parsed"
        and attachment.parser_key in _TEXTUAL_PARSER_KEYS
    )


def _attachment_records(
    attachments: list[Attachment], email_uids: Mapping[int, str]
) -> tuple[list[dict[str, object]], dict[int, str]]:
    admitted = [
        attachment
        for attachment in attachments
        if attachment.email_id in email_uids and _is_admitted_attachment(attachment)
    ]
    admitted.sort(
        key=lambda item: (
            _canonical_json(_attachment_core(item, email_uids[item.email_id])),
            item.id,
        )
    )
    occurrence: dict[bytes, int] = {}
    records: list[dict[str, object]] = []
    uid_by_id: dict[int, str] = {}
    for attachment in admitted:
        core = _attachment_core(attachment, email_uids[attachment.email_id])
        canonical = _canonical_json(core)
        occurrence[canonical] = occurrence.get(canonical, 0) + 1
        uid = (
            "attachment-"
            + hashlib.sha256(
                canonical + b":" + str(occurrence[canonical]).encode("ascii")
            ).hexdigest()
        )
        uid_by_id[attachment.id] = uid
        records.append({"attachment_uid": uid, **core})
    return sorted(records, key=lambda item: item["attachment_uid"]), uid_by_id


def _email_record(email: Email) -> dict[str, object]:
    return {
        "email_uid": email.message_id,
        "thread_uid": email.thread_id,
        "fingerprint": email.fingerprint,
        "sender": email.sender,
        "reply_to": email.reply_to,
        "recipients": email.recipients,
        "subject": email.subject,
        "in_reply_to": email.in_reply_to,
        "references": email.references,
        "date": _utc_text(email.date),
        "body": email.body,
        "is_read": email.is_read,
    }


def _node_record(
    node: ContentNodeRecord,
    email_uids: Mapping[int, str],
    attachment_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "content_node_uid": node.content_node_uid,
        "email_uid": email_uids[node.email_id],
        "attachment_uid": attachment_uids.get(node.attachment_id),
        "source_kind": node.source_kind,
        "source_record_uid": node.source_record_uid,
        "parent_node_uid": node.parent_node_uid,
        "node_kind": node.node_kind,
        "node_path": node.node_path,
        "ordinal_index": node.ordinal_index,
        "display_label": node.display_label,
        "safe_text_content": node.safe_text_content,
        "content_hash": node.content_hash,
    }


def _segment_record(
    segment: ContentSegmentRecord,
    email_uids: Mapping[int, str],
    attachment_uids: Mapping[int, str],
    node_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "content_segment_uid": segment.content_segment_uid,
        "email_uid": email_uids[segment.email_id],
        "attachment_uid": attachment_uids.get(segment.attachment_id),
        "content_node_uid": node_uids[segment.content_node_id],
        "source_kind": segment.source_kind,
        "source_record_uid": segment.source_record_uid,
        "segment_kind": segment.segment_kind,
        "segment_path": segment.segment_path,
        "ordinal_index": segment.ordinal_index,
        "heading_path": segment.heading_path,
        "safe_text_content": segment.safe_text_content,
        "content_hash": segment.content_hash,
        "word_count": segment.word_count,
    }


def _structural_edge_record(
    edge: KnowledgeGraphEdgeRecord,
    email_uids: Mapping[int, str],
    attachment_uids: Mapping[int, str],
    node_uids: Mapping[int, str],
    segment_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "edge_uid": edge.edge_uid,
        "email_uid": email_uids[edge.email_id],
        "attachment_uid": attachment_uids.get(edge.attachment_id),
        "source_node_uid": node_uids.get(edge.source_node_id),
        "target_node_uid": node_uids.get(edge.target_node_id),
        "source_segment_uid": segment_uids.get(edge.source_segment_id),
        "target_segment_uid": segment_uids.get(edge.target_segment_id),
        "source_kind": edge.source_kind,
        "source_record_uid": edge.source_record_uid,
        "edge_kind": edge.edge_kind,
        "edge_path": edge.edge_path,
        "ordinal_index": edge.ordinal_index,
    }


def _project_object_record(
    project_object: ProjectGraphObjectRecord,
    email_uids: Mapping[int, str],
    attachment_uids: Mapping[int, str],
    segment_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "object_uid": project_object.object_uid,
        "email_uid": email_uids[project_object.email_id],
        "attachment_uid": attachment_uids.get(project_object.attachment_id),
        "primary_content_segment_uid": segment_uids[
            project_object.primary_content_segment_id
        ],
        "object_type": project_object.object_type,
        "title": project_object.title,
        "summary": project_object.summary,
        "status_code": project_object.status_code,
        "confidence": _confidence(project_object.confidence),
        "source_segment_uids": sorted(project_object.source_segment_uids),
        "attributes_json": project_object.attributes_json,
        "extractor_name": project_object.extractor_name,
        "extractor_version": project_object.extractor_version,
    }


def _project_edge_record(
    edge: ProjectGraphEdgeRecord,
    object_uids: Mapping[int, str],
    segment_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "edge_uid": edge.edge_uid,
        "source_uid": edge.source_uid,
        "target_uid": edge.target_uid,
        "edge_type": edge.edge_type,
        "confidence": _confidence(edge.confidence),
        "source_segment_uids": sorted(edge.source_segment_uids),
        "source_object_uid": object_uids.get(edge.source_object_id),
        "target_object_uid": object_uids.get(edge.target_object_id),
        "primary_content_segment_uid": segment_uids[edge.primary_content_segment_id],
    }


def _correction_record(
    correction: ProjectGraphCorrectionRecord,
    object_uids: Mapping[int, str],
) -> dict[str, object]:
    return {
        "correction_uid": correction.correction_uid,
        "object_uid": object_uids[correction.project_graph_object_id],
        "correction_action": correction.correction_action,
        "before_json": correction.before_json,
        "after_json": correction.after_json,
        "rationale": correction.rationale,
        "source_segment_uids": sorted(correction.source_segment_uids),
        "created_at": _utc_text(correction.created_at),
    }


async def export_tenant_provenance(
    session: AsyncSession, scope: TenantProvenanceScope
) -> bytes:
    """Export the exact signed-scope project-evidence closure."""
    _validate_scope(scope)
    project_objects = list(
        (
            await session.scalars(
                select(ProjectGraphObjectRecord)
                .where(*_scope_filters(ProjectGraphObjectRecord, scope, workspace=True))
                .order_by(ProjectGraphObjectRecord.object_uid)
            )
        ).all()
    )
    email_ids = {record.email_id for record in project_objects}
    emails = list(
        (
            await session.scalars(
                select(Email)
                .where(
                    Email.id.in_(email_ids),
                    *_scope_filters(Email, scope, workspace=False),
                )
                .order_by(Email.message_id)
            )
        ).all()
    )
    if len(emails) != len(email_ids):
        _fail()
    email_uids = {email.id: email.message_id for email in emails}

    async def descendants(model: Any, order_column: Any) -> list[Any]:
        return list(
            (
                await session.scalars(
                    select(model)
                    .where(model.email_id.in_(email_ids))
                    .order_by(order_column)
                )
            ).all()
        )

    attachments = await descendants(Attachment, Attachment.id)
    nodes = await descendants(ContentNodeRecord, ContentNodeRecord.content_node_uid)
    segments = await descendants(
        ContentSegmentRecord, ContentSegmentRecord.content_segment_uid
    )
    structural_edges = await descendants(
        KnowledgeGraphEdgeRecord, KnowledgeGraphEdgeRecord.edge_uid
    )
    project_edges = list(
        (
            await session.scalars(
                select(ProjectGraphEdgeRecord)
                .where(*_scope_filters(ProjectGraphEdgeRecord, scope, workspace=True))
                .order_by(ProjectGraphEdgeRecord.edge_uid)
            )
        ).all()
    )
    corrections = list(
        (
            await session.scalars(
                select(ProjectGraphCorrectionRecord)
                .where(
                    *_scope_filters(ProjectGraphCorrectionRecord, scope, workspace=True)
                )
                .order_by(ProjectGraphCorrectionRecord.correction_uid)
            )
        ).all()
    )

    attachment_records, attachment_uids = _attachment_records(attachments, email_uids)
    node_uids = {node.content_node_id: node.content_node_uid for node in nodes}
    segment_uids = {
        segment.content_segment_id: segment.content_segment_uid for segment in segments
    }
    object_uids = {
        project_object.project_graph_object_id: project_object.object_uid
        for project_object in project_objects
    }
    payload = {
        "source_scope": {
            "organization_uid": scope.organization_id or "unscoped",
            "workspace_uid": scope.workspace_id,
        },
        "emails": [_email_record(email) for email in emails],
        "attachments": attachment_records,
        "content_nodes": [
            _node_record(node, email_uids, attachment_uids) for node in nodes
        ],
        "content_segments": [
            _segment_record(segment, email_uids, attachment_uids, node_uids)
            for segment in segments
        ],
        "structural_edges": [
            _structural_edge_record(
                edge, email_uids, attachment_uids, node_uids, segment_uids
            )
            for edge in structural_edges
        ],
        "project_objects": [
            _project_object_record(
                project_object, email_uids, attachment_uids, segment_uids
            )
            for project_object in project_objects
        ],
        "project_edges": [
            _project_edge_record(edge, object_uids, segment_uids)
            for edge in project_edges
        ],
        "corrections": [
            _correction_record(correction, object_uids) for correction in corrections
        ],
    }
    content_digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    records = {
        "profile": "naruon-tenant-provenance/v1",
        "schema_version": 1,
        "bundle_uid": f"bundle-{content_digest}",
        **payload,
        "export_activity": {
            "activity_uid": f"export-{content_digest}",
            "date_published": "1980-01-01T00:00:00Z",
        },
    }
    _validate_record_graph(records)
    return build_provenance_archive(records)


def _validate_scope(scope: TenantProvenanceScope) -> None:
    if not isinstance(scope, TenantProvenanceScope):
        _fail()
    _safe_identifier(scope.user_id)
    if scope.organization_id is not None:
        _safe_identifier(scope.organization_id)
    _safe_identifier(scope.workspace_id)


def _record_mapping(value: object, expected_keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        _fail()
    return value


def _required_text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        _fail()
    return value


def _optional_text(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    if value is not None and not isinstance(value, str):
        _fail()
    return value


def _uid(
    record: Mapping[str, object], key: str, *, optional: bool = False
) -> str | None:
    value = _optional_text(record, key) if optional else _required_text(record, key)
    return None if value is None else _safe_identifier(value)


def _integer(record: Mapping[str, object], key: str, *, minimum: int = 0) -> int:
    value = record.get(key)
    if type(value) is not int or value < minimum:
        _fail()
    return value


def _uid_list(record: Mapping[str, object], key: str) -> list[str]:
    value = record.get(key)
    if not isinstance(value, list):
        _fail()
    validated = [_safe_identifier(item) for item in value]
    if validated != sorted(set(validated)):
        _fail()
    return validated


def _collection_records(
    records: Mapping[str, object], collection: str, uid_key: str
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    values = records.get(collection)
    if not isinstance(values, list):
        _fail()
    validated = [_record_mapping(value, _RECORD_KEYS[collection]) for value in values]
    keys = [_safe_identifier(value.get(uid_key)) for value in validated]
    if keys != sorted(set(keys)):
        _fail()
    return validated, dict(zip(keys, validated, strict=True))


def _validate_record_scalars(
    collections: Mapping[str, list[dict[str, object]]],
) -> None:
    for email in collections["emails"]:
        _uid(email, "email_uid")
        for key in (
            "thread_uid",
            "fingerprint",
            "reply_to",
            "recipients",
            "subject",
            "in_reply_to",
            "references",
        ):
            _optional_text(email, key)
        for key in ("sender", "body"):
            _required_text(email, key)
        _parse_datetime(email.get("date"))
        if type(email.get("is_read")) is not bool:
            _fail()

    for attachment in collections["attachments"]:
        _uid(attachment, "attachment_uid")
        _uid(attachment, "email_uid")
        for key in (
            "filename",
            "content",
            "content_type",
            "parse_status",
            "parse_content_type",
            "parser_key",
        ):
            _required_text(attachment, key)
        _optional_text(attachment, "parse_error_code")
        if (
            attachment["parse_status"] != "parsed"
            or attachment["parser_key"] not in _TEXTUAL_PARSER_KEYS
        ):
            _fail()

    for node in collections["content_nodes"]:
        for key in ("content_node_uid", "email_uid"):
            _uid(node, key)
        for key in ("attachment_uid", "parent_node_uid"):
            _uid(node, key, optional=True)
        for key in (
            "source_kind",
            "source_record_uid",
            "node_kind",
            "node_path",
            "safe_text_content",
            "content_hash",
        ):
            _required_text(node, key)
        _optional_text(node, "display_label")
        _integer(node, "ordinal_index")

    for segment in collections["content_segments"]:
        for key in ("content_segment_uid", "email_uid", "content_node_uid"):
            _uid(segment, key)
        _uid(segment, "attachment_uid", optional=True)
        for key in (
            "source_kind",
            "source_record_uid",
            "segment_kind",
            "segment_path",
            "safe_text_content",
            "content_hash",
        ):
            _required_text(segment, key)
        _optional_text(segment, "heading_path")
        _integer(segment, "ordinal_index")
        _integer(segment, "word_count")

    for edge in collections["structural_edges"]:
        for key in ("edge_uid", "email_uid"):
            _uid(edge, key)
        for key in (
            "attachment_uid",
            "source_node_uid",
            "target_node_uid",
            "source_segment_uid",
            "target_segment_uid",
        ):
            _uid(edge, key, optional=True)
        for key in ("source_kind", "source_record_uid", "edge_kind", "edge_path"):
            _required_text(edge, key)
        _integer(edge, "ordinal_index")

    for project_object in collections["project_objects"]:
        for key in (
            "object_uid",
            "email_uid",
            "primary_content_segment_uid",
        ):
            _uid(project_object, key)
        _uid(project_object, "attachment_uid", optional=True)
        for key in (
            "object_type",
            "title",
            "summary",
            "status_code",
            "extractor_name",
            "extractor_version",
        ):
            _required_text(project_object, key)
        _parse_confidence(project_object.get("confidence"))
        _uid_list(project_object, "source_segment_uids")
        if not isinstance(project_object.get("attributes_json"), dict):
            _fail()

    for edge in collections["project_edges"]:
        for key in (
            "edge_uid",
            "source_uid",
            "target_uid",
            "primary_content_segment_uid",
        ):
            _uid(edge, key)
        for key in ("source_object_uid", "target_object_uid"):
            _uid(edge, key, optional=True)
        _required_text(edge, "edge_type")
        _parse_confidence(edge.get("confidence"))
        _uid_list(edge, "source_segment_uids")

    for correction in collections["corrections"]:
        for key in ("correction_uid", "object_uid"):
            _uid(correction, key)
        _required_text(correction, "correction_action")
        _optional_text(correction, "rationale")
        _uid_list(correction, "source_segment_uids")
        if not isinstance(correction.get("before_json"), dict) or not isinstance(
            correction.get("after_json"), dict
        ):
            _fail()
        _parse_datetime(correction.get("created_at"))


def _validate_record_graph(records: Mapping[str, object]) -> None:
    expected_top_level = {
        "profile",
        "schema_version",
        "bundle_uid",
        "source_scope",
        "export_activity",
        *_COLLECTIONS,
    }
    if set(records) != expected_top_level:
        _fail()
    _records_bundle_uid(records)
    source_scope = records.get("source_scope")
    if not isinstance(source_scope, dict) or set(source_scope) != {
        "organization_uid",
        "workspace_uid",
    }:
        _fail()
    _safe_identifier(source_scope.get("organization_uid"))
    _safe_identifier(source_scope.get("workspace_uid"))
    activity = records.get("export_activity")
    if not isinstance(activity, dict) or set(activity) != {
        "activity_uid",
        "date_published",
    }:
        _fail()
    _safe_identifier(activity.get("activity_uid"))
    _iso8601_date_or_datetime(activity.get("date_published"))

    uid_keys = {
        "emails": "email_uid",
        "attachments": "attachment_uid",
        "content_nodes": "content_node_uid",
        "content_segments": "content_segment_uid",
        "structural_edges": "edge_uid",
        "project_objects": "object_uid",
        "project_edges": "edge_uid",
        "corrections": "correction_uid",
    }
    collections: dict[str, list[dict[str, object]]] = {}
    indexed: dict[str, dict[str, dict[str, object]]] = {}
    for collection, uid_key in uid_keys.items():
        collections[collection], indexed[collection] = _collection_records(
            records, collection, uid_key
        )
    _validate_record_scalars(collections)

    email_uids = set(indexed["emails"])
    attachment_uids = set(indexed["attachments"])
    node_uids = set(indexed["content_nodes"])
    segment_uids = set(indexed["content_segments"])
    object_uids = set(indexed["project_objects"])
    attachment_email = {
        record["attachment_uid"]: record["email_uid"]
        for record in collections["attachments"]
    }
    attachment_groups: dict[bytes, list[str]] = {}
    for record in collections["attachments"]:
        canonical = _canonical_json(
            {key: value for key, value in record.items() if key != "attachment_uid"}
        )
        attachment_groups.setdefault(canonical, []).append(record["attachment_uid"])
    for canonical, actual_uids in attachment_groups.items():
        expected_uids = {
            "attachment-"
            + hashlib.sha256(
                canonical + b":" + str(occurrence).encode("ascii")
            ).hexdigest()
            for occurrence in range(1, len(actual_uids) + 1)
        }
        if set(actual_uids) != expected_uids:
            _fail()
    node_email = {
        record["content_node_uid"]: record["email_uid"]
        for record in collections["content_nodes"]
    }
    segment_email = {
        record["content_segment_uid"]: record["email_uid"]
        for record in collections["content_segments"]
    }

    def require_reference(value: object, available: set[str]) -> None:
        if value is not None and value not in available:
            _fail()

    for record in collections["attachments"]:
        require_reference(record["email_uid"], email_uids)
    for record in collections["content_nodes"]:
        email_uid = record["email_uid"]
        require_reference(email_uid, email_uids)
        require_reference(record["attachment_uid"], attachment_uids)
        require_reference(record["parent_node_uid"], node_uids)
        if (
            record["attachment_uid"] is not None
            and attachment_email[record["attachment_uid"]] != email_uid
        ):
            _fail()
        if (
            record["parent_node_uid"] is not None
            and node_email[record["parent_node_uid"]] != email_uid
        ):
            _fail()
    for record in collections["content_segments"]:
        email_uid = record["email_uid"]
        require_reference(email_uid, email_uids)
        require_reference(record["attachment_uid"], attachment_uids)
        require_reference(record["content_node_uid"], node_uids)
        if node_email[record["content_node_uid"]] != email_uid:
            _fail()
        if (
            record["attachment_uid"] is not None
            and attachment_email[record["attachment_uid"]] != email_uid
        ):
            _fail()
    for record in collections["structural_edges"]:
        email_uid = record["email_uid"]
        require_reference(email_uid, email_uids)
        require_reference(record["attachment_uid"], attachment_uids)
        for key in ("source_node_uid", "target_node_uid"):
            require_reference(record[key], node_uids)
            if record[key] is not None and node_email[record[key]] != email_uid:
                _fail()
        for key in ("source_segment_uid", "target_segment_uid"):
            require_reference(record[key], segment_uids)
            if record[key] is not None and segment_email[record[key]] != email_uid:
                _fail()
    for record in collections["project_objects"]:
        require_reference(record["email_uid"], email_uids)
        require_reference(record["attachment_uid"], attachment_uids)
        require_reference(record["primary_content_segment_uid"], segment_uids)
        if segment_email[record["primary_content_segment_uid"]] != record["email_uid"]:
            _fail()
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)
    for record in collections["project_edges"]:
        require_reference(record["source_object_uid"], object_uids)
        require_reference(record["target_object_uid"], object_uids)
        require_reference(record["primary_content_segment_uid"], segment_uids)
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)
    for record in collections["corrections"]:
        require_reference(record["object_uid"], object_uids)
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)


async def _matching_models(
    session: AsyncSession,
    model: Any,
    column: Any,
    values: set[str],
    key_attribute: str,
) -> dict[str, Any]:
    if not values:
        return {}
    rows = list((await session.scalars(select(model).where(column.in_(values)))).all())
    return {getattr(row, key_attribute): row for row in rows}


async def _preflight_existing(
    session: AsyncSession,
    scope: TenantProvenanceScope,
    records: Mapping[str, object],
) -> dict[str, dict[str, Any]]:
    payload = {
        collection: {
            record[
                {
                    "emails": "email_uid",
                    "attachments": "attachment_uid",
                    "content_nodes": "content_node_uid",
                    "content_segments": "content_segment_uid",
                    "structural_edges": "edge_uid",
                    "project_objects": "object_uid",
                    "project_edges": "edge_uid",
                    "corrections": "correction_uid",
                }[collection]
            ]: record
            for record in records[collection]
        }
        for collection in _COLLECTIONS
    }
    email_values = set(payload["emails"])
    email_rows = list(
        (
            await session.scalars(
                select(Email).where(
                    Email.message_id.in_(email_values),
                    *_scope_filters(Email, scope, workspace=False),
                )
            )
        ).all()
    )
    models: dict[str, dict[str, Any]] = {
        "emails": {row.message_id: row for row in email_rows}
    }
    email_uids = {row.id: row.message_id for row in email_rows}
    attachment_rows = (
        list(
            (
                await session.scalars(
                    select(Attachment).where(Attachment.email_id.in_(email_uids))
                )
            ).all()
        )
        if email_uids
        else []
    )
    attachment_records, attachment_uids = _attachment_records(
        attachment_rows, email_uids
    )
    attachments_by_id = {row.id: row for row in attachment_rows}
    models["attachments"] = {
        uid: attachments_by_id[attachment_id]
        for attachment_id, uid in attachment_uids.items()
        if uid in payload["attachments"]
    }
    existing_serialized: dict[str, dict[str, dict[str, object]]] = {
        "emails": {uid: _email_record(row) for uid, row in models["emails"].items()},
        "attachments": {
            record["attachment_uid"]: record
            for record in attachment_records
            if record["attachment_uid"] in payload["attachments"]
        },
    }

    models["content_nodes"] = await _matching_models(
        session,
        ContentNodeRecord,
        ContentNodeRecord.content_node_uid,
        set(payload["content_nodes"]),
        "content_node_uid",
    )
    node_uids = {
        row.content_node_id: row.content_node_uid
        for row in models["content_nodes"].values()
    }
    models["content_segments"] = await _matching_models(
        session,
        ContentSegmentRecord,
        ContentSegmentRecord.content_segment_uid,
        set(payload["content_segments"]),
        "content_segment_uid",
    )
    segment_uids = {
        row.content_segment_id: row.content_segment_uid
        for row in models["content_segments"].values()
    }
    models["structural_edges"] = await _matching_models(
        session,
        KnowledgeGraphEdgeRecord,
        KnowledgeGraphEdgeRecord.edge_uid,
        set(payload["structural_edges"]),
        "edge_uid",
    )
    models["project_objects"] = await _matching_models(
        session,
        ProjectGraphObjectRecord,
        ProjectGraphObjectRecord.object_uid,
        set(payload["project_objects"]),
        "object_uid",
    )
    object_uids = {
        row.project_graph_object_id: row.object_uid
        for row in models["project_objects"].values()
    }
    models["project_edges"] = await _matching_models(
        session,
        ProjectGraphEdgeRecord,
        ProjectGraphEdgeRecord.edge_uid,
        set(payload["project_edges"]),
        "edge_uid",
    )
    models["corrections"] = await _matching_models(
        session,
        ProjectGraphCorrectionRecord,
        ProjectGraphCorrectionRecord.correction_uid,
        set(payload["corrections"]),
        "correction_uid",
    )

    try:
        existing_serialized["content_nodes"] = {
            uid: _node_record(row, email_uids, attachment_uids)
            for uid, row in models["content_nodes"].items()
        }
        existing_serialized["content_segments"] = {
            uid: _segment_record(row, email_uids, attachment_uids, node_uids)
            for uid, row in models["content_segments"].items()
        }
        existing_serialized["structural_edges"] = {
            uid: _structural_edge_record(
                row, email_uids, attachment_uids, node_uids, segment_uids
            )
            for uid, row in models["structural_edges"].items()
        }
        existing_serialized["project_objects"] = {
            uid: _project_object_record(row, email_uids, attachment_uids, segment_uids)
            for uid, row in models["project_objects"].items()
        }
        existing_serialized["project_edges"] = {
            uid: _project_edge_record(row, object_uids, segment_uids)
            for uid, row in models["project_edges"].items()
        }
        existing_serialized["corrections"] = {
            uid: _correction_record(row, object_uids)
            for uid, row in models["corrections"].items()
        }
    except KeyError:
        _fail()

    scoped_models = (
        models["project_objects"].values(),
        models["project_edges"].values(),
        models["corrections"].values(),
    )
    for rows in scoped_models:
        for row in rows:
            if (
                row.user_id != scope.user_id
                or row.organization_id != scope.organization_id
                or row.workspace_id != scope.workspace_id
            ):
                _fail()
    if any(
        row.actor_user_id != scope.user_id for row in models["corrections"].values()
    ):
        _fail()
    for collection in _COLLECTIONS:
        for uid, existing in existing_serialized[collection].items():
            if existing != payload[collection].get(uid):
                _fail()
    return models


async def _insert_records(
    session: AsyncSession,
    scope: TenantProvenanceScope,
    records: Mapping[str, object],
    models: dict[str, dict[str, Any]],
    created: dict[str, int],
) -> None:
    for record in records["emails"]:
        uid = record["email_uid"]
        if uid in models["emails"]:
            continue
        email = Email(
            user_id=scope.user_id,
            organization_id=scope.organization_id,
            message_id=uid,
            thread_id=record["thread_uid"],
            fingerprint=record["fingerprint"],
            sender=record["sender"],
            reply_to=record["reply_to"],
            recipients=record["recipients"],
            subject=record["subject"],
            in_reply_to=record["in_reply_to"],
            references=record["references"],
            date=_parse_datetime(record["date"]),
            body=record["body"],
            is_read=record["is_read"],
            embedding=None,
        )
        session.add(email)
        models["emails"][uid] = email
        created["emails"] += 1
    await session.flush()

    for record in records["attachments"]:
        uid = record["attachment_uid"]
        if uid in models["attachments"]:
            continue
        attachment = Attachment(
            email=models["emails"][record["email_uid"]],
            filename=record["filename"],
            content=record["content"],
            content_type=record["content_type"],
            parse_status=record["parse_status"],
            parse_content_type=record["parse_content_type"],
            parser_key=record["parser_key"],
            parse_error_code=record["parse_error_code"],
            embedding=None,
        )
        session.add(attachment)
        models["attachments"][uid] = attachment
        created["attachments"] += 1
    await session.flush()

    for record in records["content_nodes"]:
        uid = record["content_node_uid"]
        if uid in models["content_nodes"]:
            continue
        node = ContentNodeRecord(
            content_node_uid=uid,
            email=models["emails"][record["email_uid"]],
            attachment=(
                models["attachments"].get(record["attachment_uid"])
                if record["attachment_uid"] is not None
                else None
            ),
            source_kind=record["source_kind"],
            source_record_uid=record["source_record_uid"],
            parent_node_uid=record["parent_node_uid"],
            node_kind=record["node_kind"],
            node_path=record["node_path"],
            ordinal_index=record["ordinal_index"],
            display_label=record["display_label"],
            safe_text_content=record["safe_text_content"],
            content_hash=record["content_hash"],
        )
        session.add(node)
        models["content_nodes"][uid] = node
        created["content_nodes"] += 1
    await session.flush()

    for record in records["content_segments"]:
        uid = record["content_segment_uid"]
        if uid in models["content_segments"]:
            continue
        segment = ContentSegmentRecord(
            content_segment_uid=uid,
            email=models["emails"][record["email_uid"]],
            attachment=(
                models["attachments"].get(record["attachment_uid"])
                if record["attachment_uid"] is not None
                else None
            ),
            content_node=models["content_nodes"][record["content_node_uid"]],
            source_kind=record["source_kind"],
            source_record_uid=record["source_record_uid"],
            segment_kind=record["segment_kind"],
            segment_path=record["segment_path"],
            ordinal_index=record["ordinal_index"],
            heading_path=record["heading_path"],
            safe_text_content=record["safe_text_content"],
            content_hash=record["content_hash"],
            word_count=record["word_count"],
        )
        session.add(segment)
        models["content_segments"][uid] = segment
        created["content_segments"] += 1
    await session.flush()

    for record in records["structural_edges"]:
        uid = record["edge_uid"]
        if uid in models["structural_edges"]:
            continue
        edge = KnowledgeGraphEdgeRecord(
            edge_uid=uid,
            email=models["emails"][record["email_uid"]],
            attachment=(
                models["attachments"].get(record["attachment_uid"])
                if record["attachment_uid"] is not None
                else None
            ),
            source_node=models["content_nodes"].get(record["source_node_uid"]),
            target_node=models["content_nodes"].get(record["target_node_uid"]),
            source_segment=models["content_segments"].get(record["source_segment_uid"]),
            target_segment=models["content_segments"].get(record["target_segment_uid"]),
            source_kind=record["source_kind"],
            source_record_uid=record["source_record_uid"],
            edge_kind=record["edge_kind"],
            edge_path=record["edge_path"],
            ordinal_index=record["ordinal_index"],
        )
        session.add(edge)
        models["structural_edges"][uid] = edge
        created["structural_edges"] += 1
    await session.flush()

    for record in records["project_objects"]:
        uid = record["object_uid"]
        if uid in models["project_objects"]:
            continue
        project_object = ProjectGraphObjectRecord(
            object_uid=uid,
            user_id=scope.user_id,
            organization_id=scope.organization_id,
            workspace_id=scope.workspace_id,
            email=models["emails"][record["email_uid"]],
            attachment=(
                models["attachments"].get(record["attachment_uid"])
                if record["attachment_uid"] is not None
                else None
            ),
            primary_content_segment=models["content_segments"][
                record["primary_content_segment_uid"]
            ],
            object_type=record["object_type"],
            title=record["title"],
            summary=record["summary"],
            status_code=record["status_code"],
            confidence=_parse_confidence(record["confidence"]),
            source_segment_uids=record["source_segment_uids"],
            attributes_json=record["attributes_json"],
            extractor_name=record["extractor_name"],
            extractor_version=record["extractor_version"],
        )
        session.add(project_object)
        models["project_objects"][uid] = project_object
        created["project_objects"] += 1
    await session.flush()

    for record in records["project_edges"]:
        uid = record["edge_uid"]
        if uid in models["project_edges"]:
            continue
        edge = ProjectGraphEdgeRecord(
            edge_uid=uid,
            user_id=scope.user_id,
            organization_id=scope.organization_id,
            workspace_id=scope.workspace_id,
            source_uid=record["source_uid"],
            target_uid=record["target_uid"],
            edge_type=record["edge_type"],
            confidence=_parse_confidence(record["confidence"]),
            source_segment_uids=record["source_segment_uids"],
            source_object=models["project_objects"].get(record["source_object_uid"]),
            target_object=models["project_objects"].get(record["target_object_uid"]),
            primary_content_segment=models["content_segments"][
                record["primary_content_segment_uid"]
            ],
        )
        session.add(edge)
        models["project_edges"][uid] = edge
        created["project_edges"] += 1
    await session.flush()

    for record in records["corrections"]:
        uid = record["correction_uid"]
        if uid in models["corrections"]:
            continue
        correction = ProjectGraphCorrectionRecord(
            correction_uid=uid,
            project_object=models["project_objects"][record["object_uid"]],
            user_id=scope.user_id,
            organization_id=scope.organization_id,
            workspace_id=scope.workspace_id,
            actor_user_id=scope.user_id,
            correction_action=record["correction_action"],
            before_json=record["before_json"],
            after_json=record["after_json"],
            rationale=record["rationale"],
            source_segment_uids=record["source_segment_uids"],
            created_at=_parse_datetime(record["created_at"]),
        )
        session.add(correction)
        models["corrections"][uid] = correction
        created["corrections"] += 1
    await session.flush()


async def import_tenant_provenance(
    session: AsyncSession,
    scope: TenantProvenanceScope,
    archive_bytes: bytes,
) -> ImportReceipt:
    """Validate all closure and conflict rules before one transactional restore."""
    _validate_scope(scope)
    records = parse_provenance_archive(archive_bytes)
    _validate_record_graph(records)
    if scope.organization_id is None and records["emails"]:
        _fail()
    created = {collection: 0 for collection in _COLLECTIONS}
    try:
        async with session.begin():
            models = await _preflight_existing(session, scope, records)
            skipped = {
                collection: len(models[collection]) for collection in _COLLECTIONS
            }
            await _insert_records(session, scope, records, models, created)
    except ProvenanceArchiveError:
        raise
    except (DataError, IntegrityError, StatementError, TypeError, ValueError) as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    return ImportReceipt(
        bundle_uid=_safe_identifier(records.get("bundle_uid")),
        manifest_digest=hashlib.sha512(_canonical_json(records)).hexdigest(),
        created=created,
        skipped=skipped,
    )
