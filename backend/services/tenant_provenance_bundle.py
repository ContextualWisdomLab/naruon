"""Deterministic, bounded BagIt/RO-Crate envelopes for tenant provenance."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import stat
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Text, cast, func, select
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
    ProvenanceIdentityMapping,
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

_EXPORT_TEXT_COLUMNS = {
    Email: (
        Email.message_id,
        Email.thread_id,
        Email.fingerprint,
        Email.sender,
        Email.reply_to,
        Email.recipients,
        Email.subject,
        Email.in_reply_to,
        Email.references,
        Email.body,
    ),
    Attachment: (
        Attachment.filename,
        Attachment.content,
        Attachment.content_type,
        Attachment.parse_status,
        Attachment.parse_content_type,
        Attachment.parser_key,
        Attachment.parse_error_code,
    ),
    ContentNodeRecord: (
        ContentNodeRecord.source_record_uid,
        ContentNodeRecord.parent_node_uid,
        ContentNodeRecord.display_label,
        ContentNodeRecord.safe_text_content,
    ),
    ContentSegmentRecord: (
        ContentSegmentRecord.source_record_uid,
        ContentSegmentRecord.heading_path,
        ContentSegmentRecord.safe_text_content,
    ),
    KnowledgeGraphEdgeRecord: (
        KnowledgeGraphEdgeRecord.source_record_uid,
        KnowledgeGraphEdgeRecord.edge_path,
    ),
    ProjectGraphObjectRecord: (
        ProjectGraphObjectRecord.title,
        ProjectGraphObjectRecord.summary,
        ProjectGraphObjectRecord.source_segment_uids,
        ProjectGraphObjectRecord.attributes_json,
    ),
    ProjectGraphEdgeRecord: (ProjectGraphEdgeRecord.source_segment_uids,),
    ProjectGraphCorrectionRecord: (
        ProjectGraphCorrectionRecord.before_json,
        ProjectGraphCorrectionRecord.after_json,
        ProjectGraphCorrectionRecord.rationale,
        ProjectGraphCorrectionRecord.source_segment_uids,
    ),
}
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
_REMAPPED_COLLECTIONS = (
    "content_nodes",
    "content_segments",
    "structural_edges",
    "project_objects",
    "project_edges",
    "corrections",
)
_UID_KEYS = {
    "content_nodes": "content_node_uid",
    "content_segments": "content_segment_uid",
    "structural_edges": "edge_uid",
    "project_objects": "object_uid",
    "project_edges": "edge_uid",
    "corrections": "correction_uid",
}
_UID_PREFIXES = {
    "content_nodes": "tpn-",
    "content_segments": "tps-",
    "structural_edges": "tpk-",
    "project_objects": "tpo-",
    "project_edges": "tpe-",
    "corrections": "tpc-",
}
_TYPED_METADATA_UIDS = {
    "object_uid": "project_objects",
    "source_object_uid": "project_objects",
    "target_object_uid": "project_objects",
    "content_node_uid": "content_nodes",
    "parent_node_uid": "content_nodes",
    "source_node_uid": "content_nodes",
    "target_node_uid": "content_nodes",
    "content_segment_uid": "content_segments",
    "segment_uid": "content_segments",
    "source_segment_uid": "content_segments",
    "target_segment_uid": "content_segments",
    "primary_segment_uid": "content_segments",
    "primary_content_segment_uid": "content_segments",
}
_TYPED_METADATA_UID_LISTS = {"source_segment_uids": "content_segments"}
_TYPED_METADATA_ATTACHMENT_REFERENCES = frozenset(
    {"attachment_uid", "source_record_uid"}
)
_TEXTUAL_PARSER_KEYS = frozenset(
    {"plain_text", "html", "markdown", "json", "csv", "xml", "calendar", "pdf"}
)
_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "api_secret",
        "attachment_id",
        "auth_token",
        "base_url",
        "bearer_token",
        "client_secret",
        "connection_string",
        "content_node_id",
        "content_segment_id",
        "credential",
        "credentials",
        "credentials_encrypted",
        "database_id",
        "database_url",
        "db_id",
        "dsn",
        "email_id",
        "id",
        "knowledge_graph_edge_id",
        "openai_api_key",
        "password",
        "primary_key",
        "private_key",
        "project_graph_correction_id",
        "project_graph_edge_id",
        "project_graph_object_id",
        "provider_base_url",
        "provider_endpoint",
        "provider_url",
        "refresh_token",
        "row_id",
        "secret",
        "secrets",
        "token",
    }
)
_SENSITIVE_METADATA_TOKENS = frozenset(
    {"credential", "credentials", "password", "secret", "secrets", "token"}
)
_METADATA_KEY_TOKEN_PATTERN = re.compile(
    r"[A-Z]+(?=[A-Z][a-z]|[0-9]|[^A-Za-z0-9]|$)"
    r"|[A-Z]?[a-z]+|[A-Z]+|[0-9]+"
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
        if not math.isfinite(value):
            _fail()
        return
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


def _metadata_key_is_forbidden(key: str) -> bool:
    tokens = tuple(
        match.group(0).lower() for match in _METADATA_KEY_TOKEN_PATTERN.finditer(key)
    )
    normalized_key = "_".join(tokens)
    token_set = frozenset(tokens)
    token_pairs = set(zip(tokens, tokens[1:]))
    return (
        normalized_key in _FORBIDDEN_METADATA_KEYS
        or bool(token_set & _SENSITIVE_METADATA_TOKENS)
        or ("api", "key") in token_pairs
        or ("provider" in token_set and bool({"endpoint", "url", "uri"} & token_set))
        or (bool(tokens) and tokens[-1] == "id")
        or (bool({"database", "db"} & token_set) and bool({"id", "key"} & token_set))
    )


def _validate_safe_metadata(value: object, depth: int = 0) -> None:
    if depth > JSON_MAX_DEPTH:
        _fail()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail()
            if _metadata_key_is_forbidden(key):
                _fail()
            _validate_safe_metadata(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_safe_metadata(item, depth + 1)


def _portable_metadata(
    value: object, attachment_references: Mapping[str, str]
) -> object:
    if isinstance(value, list):
        return [_portable_metadata(item, attachment_references) for item in value]
    if isinstance(value, Mapping):
        portable = {}
        for key, item in value.items():
            if key in _TYPED_METADATA_ATTACHMENT_REFERENCES and isinstance(item, str):
                portable[key] = attachment_references.get(item, item)
            else:
                portable[key] = _portable_metadata(item, attachment_references)
        return portable
    return value


def _source_user_uid(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _target_database_uid(
    scope: TenantProvenanceScope,
    source_scope: Mapping[str, str],
    collection: str,
    portable_uid: str,
) -> str:
    digest = hashlib.sha256(
        _canonical_json(
            {
                "collection": collection,
                "portable_uid": portable_uid,
                "source_scope": dict(source_scope),
                "target_scope": {
                    "organization_uid": scope.organization_id,
                    "user_uid": scope.user_id,
                    "workspace_uid": scope.workspace_id,
                },
            }
        )
    ).hexdigest()
    return f"{_UID_PREFIXES[collection]}{digest[:60]}"


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


def _segment_endpoint_uid(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("segment:"):
        _fail()
    segment_uid = value.removeprefix("segment:")
    if not segment_uid:
        _fail()
    return segment_uid


def _translate_identity_records(
    records: Mapping[str, object], maps: Mapping[str, Mapping[str, str]]
) -> dict[str, object]:
    translated = copy.deepcopy(records)

    def replace(record: dict[str, object], field: str, collection: str) -> None:
        value = record[field]
        if value is not None:
            record[field] = maps[collection].get(value, value)

    def replace_list(record: dict[str, object], field: str, collection: str) -> None:
        record[field] = sorted(
            maps[collection].get(value, value) for value in record[field]
        )

    def replace_project_endpoint(
        record: dict[str, object], field: str, object_field: str
    ) -> None:
        value = record[field]
        if record[object_field] is not None:
            mapped_uid = maps["project_objects"].get(value)
            if mapped_uid is None:
                _fail()
            record[field] = mapped_uid
            return
        segment_uid = _segment_endpoint_uid(value)
        mapped_uid = maps["content_segments"].get(segment_uid)
        if mapped_uid is None:
            _fail()
        record[field] = f"segment:{mapped_uid}"

    def translate_metadata(value: object) -> object:
        if isinstance(value, dict):
            translated_mapping = {
                key: translate_metadata(item) for key, item in value.items()
            }
            for key, collection in _TYPED_METADATA_UIDS.items():
                item = translated_mapping.get(key)
                if isinstance(item, str):
                    translated_mapping[key] = maps[collection].get(item, item)
            for key, collection in _TYPED_METADATA_UID_LISTS.items():
                item = translated_mapping.get(key)
                if isinstance(item, list) and all(isinstance(uid, str) for uid in item):
                    translated_mapping[key] = [
                        maps[collection].get(uid, uid) for uid in item
                    ]
            return translated_mapping
        if isinstance(value, list):
            return [translate_metadata(item) for item in value]
        return value

    for record in translated["content_nodes"]:
        replace(record, "content_node_uid", "content_nodes")
        replace(record, "parent_node_uid", "content_nodes")
    for record in translated["content_segments"]:
        replace(record, "content_segment_uid", "content_segments")
        replace(record, "content_node_uid", "content_nodes")
    for record in translated["structural_edges"]:
        replace(record, "edge_uid", "structural_edges")
        for field in ("source_node_uid", "target_node_uid"):
            replace(record, field, "content_nodes")
        for field in ("source_segment_uid", "target_segment_uid"):
            replace(record, field, "content_segments")
    for record in translated["project_objects"]:
        replace(record, "object_uid", "project_objects")
        replace(record, "primary_content_segment_uid", "content_segments")
        replace_list(record, "source_segment_uids", "content_segments")
        record["attributes_json"] = translate_metadata(record["attributes_json"])
    for record in translated["project_edges"]:
        replace(record, "edge_uid", "project_edges")
        replace_project_endpoint(record, "source_uid", "source_object_uid")
        replace_project_endpoint(record, "target_uid", "target_object_uid")
        replace(record, "source_object_uid", "project_objects")
        replace(record, "target_object_uid", "project_objects")
        replace(record, "primary_content_segment_uid", "content_segments")
        replace_list(record, "source_segment_uids", "content_segments")
    for record in translated["corrections"]:
        replace(record, "correction_uid", "corrections")
        replace(record, "object_uid", "project_objects")
        replace_list(record, "source_segment_uids", "content_segments")
        record["before_json"] = translate_metadata(record["before_json"])
        record["after_json"] = translate_metadata(record["after_json"])
    for collection in _REMAPPED_COLLECTIONS:
        translated[collection].sort(key=lambda record: record[_UID_KEYS[collection]])
    return translated


def _records_bundle_uid(records: Mapping[str, object]) -> str:
    schema_version = records.get("schema_version")
    if (
        records.get("profile") != "naruon-tenant-provenance/v1"
        or type(schema_version) is not int
        or schema_version != 1
    ):
        _fail()
    return _safe_identifier(records.get("bundle_uid"))


def _content_identity_digest(records: Mapping[str, object]) -> str:
    activity = records.get("export_activity")
    if not isinstance(activity, Mapping):
        _fail()
    identity = {
        "profile": records.get("profile"),
        "schema_version": records.get("schema_version"),
        "source_scope": records.get("source_scope"),
        **{collection: records.get(collection) for collection in _COLLECTIONS},
        "export_activity": {"date_published": activity.get("date_published")},
    }
    return hashlib.sha256(_canonical_json(identity)).hexdigest()


def _validate_content_bound_identifiers(records: Mapping[str, object]) -> str:
    content_digest = _content_identity_digest(records)
    if _records_bundle_uid(records) != f"bundle-{content_digest}":
        _fail()
    activity = records.get("export_activity")
    if not isinstance(activity, Mapping) or _safe_identifier(
        activity.get("activity_uid")
    ) != f"export-{content_digest}":
        _fail()
    return content_digest


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
    return _utc_text(_parse_datetime(date_published))


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
    _validate_content_bound_identifiers(records)
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
    activity = records.get("export_activity")
    if not isinstance(activity, Mapping):
        _fail()
    _records_bundle_uid(records)
    _safe_identifier(activity.get("activity_uid"))
    bound_records = {
        **records,
        "export_activity": dict(activity),
    }
    content_digest = _content_identity_digest(bound_records)
    bound_records["bundle_uid"] = f"bundle-{content_digest}"
    bound_records["export_activity"]["activity_uid"] = f"export-{content_digest}"
    entries = _archive_entries(bound_records)
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


async def _preflight_export_rows(
    session: AsyncSession,
    model: Any,
    filters: tuple[Any, ...] | list[Any],
    consumed_bytes: int,
) -> int:
    bind = session.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return consumed_bytes
    text_bytes = sum(
        (
            func.coalesce(func.octet_length(cast(column, Text)), 0)
            for column in _EXPORT_TEXT_COLUMNS[model]
        ),
        start=0,
    )
    row_bytes = func.pg_column_size(model.__table__.table_valued()) + text_bytes
    stored_bytes = int(
        await session.scalar(
            select(func.coalesce(func.sum(row_bytes), 0)).where(*filters)
        )
        or 0
    )
    total_bytes = consumed_bytes + stored_bytes
    if total_bytes > ENTRY_MAX_BYTES:
        _fail()
    return total_bytes


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
    if parsed.tzinfo is None or _utc_text(parsed) != text_value:
        _fail()
    return parsed


def _confidence(value: float) -> str:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        _fail()
    return repr(value)


def _parse_confidence(value: object) -> float:
    if not isinstance(value, str):
        _fail()
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ProvenanceArchiveError("Invalid provenance archive") from exc
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
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


def _attachment_payload_core(record: Mapping[str, object]) -> bytes:
    return _canonical_json(
        {key: value for key, value in record.items() if key != "attachment_uid"}
    )


def _attachment_uid(canonical: bytes, occurrence: int) -> str:
    return (
        "attachment-"
        + hashlib.sha256(canonical + b":" + str(occurrence).encode("ascii")).hexdigest()
    )


def _attachments_in_occurrence_order(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    groups: dict[bytes, list[dict[str, object]]] = {}
    for record in records:
        groups.setdefault(_attachment_payload_core(record), []).append(record)
    ordered: list[dict[str, object]] = []
    for canonical, group in sorted(groups.items()):
        occurrences = {
            _attachment_uid(canonical, occurrence): occurrence
            for occurrence in range(1, len(group) + 1)
        }
        if set(occurrences) != {record["attachment_uid"] for record in group}:
            _fail()
        ordered.extend(
            sorted(group, key=lambda record: occurrences[record["attachment_uid"]])
        )
    return ordered


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
        uid = _attachment_uid(canonical, occurrence[canonical])
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


def _portable_source_record_uid(
    source_record_uid: str,
    attachment_id: int | None,
    attachment_uids: Mapping[int, str],
) -> str:
    if attachment_id is None:
        return source_record_uid
    attachment_uid = attachment_uids.get(attachment_id)
    if attachment_uid is None:
        _fail()
    return f"attachment:{attachment_uid}"


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
        "source_record_uid": _portable_source_record_uid(
            node.source_record_uid, node.attachment_id, attachment_uids
        ),
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
        "source_record_uid": _portable_source_record_uid(
            segment.source_record_uid, segment.attachment_id, attachment_uids
        ),
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
        "source_record_uid": _portable_source_record_uid(
            edge.source_record_uid, edge.attachment_id, attachment_uids
        ),
        "edge_kind": edge.edge_kind,
        "edge_path": edge.edge_path,
        "ordinal_index": edge.ordinal_index,
    }


def _project_object_record(
    project_object: ProjectGraphObjectRecord,
    email_uids: Mapping[int, str],
    attachment_uids: Mapping[int, str],
    segment_uids: Mapping[int, str],
    attachment_references: Mapping[str, str],
) -> dict[str, object]:
    attributes_json = _portable_metadata(
        project_object.attributes_json, attachment_references
    )
    _validate_safe_metadata(attributes_json)
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
        "attributes_json": attributes_json,
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
    attachment_references: Mapping[str, str],
) -> dict[str, object]:
    before_json = _portable_metadata(correction.before_json, attachment_references)
    after_json = _portable_metadata(correction.after_json, attachment_references)
    _validate_safe_metadata(before_json)
    _validate_safe_metadata(after_json)
    return {
        "correction_uid": correction.correction_uid,
        "object_uid": object_uids[correction.project_graph_object_id],
        "correction_action": correction.correction_action,
        "before_json": before_json,
        "after_json": after_json,
        "rationale": correction.rationale,
        "source_segment_uids": sorted(correction.source_segment_uids),
        "created_at": _utc_text(correction.created_at),
    }


async def export_tenant_provenance(
    session: AsyncSession, scope: TenantProvenanceScope
) -> bytes:
    """Export the exact signed-scope project-evidence closure."""
    _validate_scope(scope)
    consumed_bytes = 0
    for model in (
        ProjectGraphObjectRecord,
        ProjectGraphEdgeRecord,
        ProjectGraphCorrectionRecord,
    ):
        consumed_bytes = await _preflight_export_rows(
            session,
            model,
            _scope_filters(model, scope, workspace=True),
            consumed_bytes,
        )
    project_objects = list(
        (
            await session.scalars(
                select(ProjectGraphObjectRecord)
                .where(*_scope_filters(ProjectGraphObjectRecord, scope, workspace=True))
                .order_by(ProjectGraphObjectRecord.object_uid)
            )
        ).all()
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
    cited_segment_uids = {
        segment_uid
        for record in (*project_objects, *project_edges, *corrections)
        for segment_uid in record.source_segment_uids
    }
    for record in project_edges:
        for endpoint_uid, endpoint_object_id in (
            (record.source_uid, record.source_object_id),
            (record.target_uid, record.target_object_id),
        ):
            if endpoint_object_id is None:
                cited_segment_uids.add(_segment_endpoint_uid(endpoint_uid))
    primary_segment_ids = {
        record.primary_content_segment_id
        for record in (*project_objects, *project_edges)
    }
    cited_size_filters = (
        (ContentSegmentRecord.content_segment_uid.in_(cited_segment_uids))
        | (ContentSegmentRecord.content_segment_id.in_(primary_segment_ids)),
    )
    cited_segment_filters = (
        *cited_size_filters,
        *_scope_filters(Email, scope, workspace=False),
    )
    consumed_bytes = await _preflight_export_rows(
        session,
        ContentSegmentRecord,
        cited_size_filters,
        consumed_bytes,
    )
    cited_segments = list(
        (
            await session.scalars(
                select(ContentSegmentRecord)
                .join(Email, ContentSegmentRecord.email_id == Email.id)
                .where(*cited_segment_filters)
            )
        ).all()
    )
    if not cited_segment_uids.issubset(
        {segment.content_segment_uid for segment in cited_segments}
    ) or not primary_segment_ids.issubset(
        {segment.content_segment_id for segment in cited_segments}
    ):
        _fail()
    segments_by_uid = {
        segment.content_segment_uid: segment for segment in cited_segments
    }
    segments_by_id = {segment.content_segment_id: segment for segment in cited_segments}
    objects_by_id = {
        record.project_graph_object_id: record for record in project_objects
    }
    for record in project_objects:
        if segments_by_id[
            record.primary_content_segment_id
        ].email_id != record.email_id or any(
            segments_by_uid[segment_uid].email_id != record.email_id
            for segment_uid in record.source_segment_uids
        ):
            _fail()
    for record in project_edges:
        endpoint_objects = []
        for endpoint_id in (record.source_object_id, record.target_object_id):
            if endpoint_id is None:
                continue
            endpoint_object = objects_by_id.get(endpoint_id)
            if endpoint_object is None:
                _fail()
            endpoint_objects.append(endpoint_object)
        if not endpoint_objects:
            _fail()
        endpoint_email_ids = {endpoint.email_id for endpoint in endpoint_objects}
        for endpoint_uid, endpoint_object_id in (
            (record.source_uid, record.source_object_id),
            (record.target_uid, record.target_object_id),
        ):
            if endpoint_object_id is None:
                segment_uid = _segment_endpoint_uid(endpoint_uid)
                if segments_by_uid[segment_uid].email_id not in endpoint_email_ids:
                    _fail()
        if segments_by_id[
            record.primary_content_segment_id
        ].email_id not in endpoint_email_ids or any(
            segments_by_uid[segment_uid].email_id not in endpoint_email_ids
            for segment_uid in record.source_segment_uids
        ):
            _fail()
    for record in corrections:
        project_object = objects_by_id.get(record.project_graph_object_id)
        if project_object is None or any(
            segments_by_uid[segment_uid].email_id != project_object.email_id
            for segment_uid in record.source_segment_uids
        ):
            _fail()
    email_ids = {record.email_id for record in project_objects} | {
        segment.email_id for segment in cited_segments
    }
    email_filters = (
        Email.id.in_(email_ids),
        *_scope_filters(Email, scope, workspace=False),
    )
    consumed_bytes = await _preflight_export_rows(
        session, Email, email_filters, consumed_bytes
    )
    emails = list(
        (
            await session.scalars(
                select(Email)
                .where(*email_filters)
                .order_by(Email.message_id)
            )
        ).all()
    )
    if len(emails) != len(email_ids):
        _fail()
    email_uids = {email.id: email.message_id for email in emails}

    async def descendants(
        model: Any, order_column: Any, *admission_filters: Any
    ) -> list[Any]:
        nonlocal consumed_bytes
        descendant_filters = (model.email_id.in_(email_ids), *admission_filters)
        consumed_bytes = await _preflight_export_rows(
            session, model, descendant_filters, consumed_bytes
        )
        return list(
            (
                await session.scalars(
                    select(model)
                    .where(*descendant_filters)
                    .order_by(order_column)
                )
            ).all()
        )

    attachments = await descendants(
        Attachment,
        Attachment.id,
        Attachment.parse_status == "parsed",
        Attachment.parser_key.in_(_TEXTUAL_PARSER_KEYS),
    )
    nodes = await descendants(ContentNodeRecord, ContentNodeRecord.content_node_uid)
    segments = await descendants(
        ContentSegmentRecord, ContentSegmentRecord.content_segment_uid
    )
    structural_edges = await descendants(
        KnowledgeGraphEdgeRecord, KnowledgeGraphEdgeRecord.edge_uid
    )
    candidate_uids = {
        *(row.content_node_uid for row in nodes),
        *(row.content_segment_uid for row in segments),
        *(row.edge_uid for row in structural_edges),
        *(row.object_uid for row in project_objects),
        *(row.edge_uid for row in project_edges),
        *(row.correction_uid for row in corrections),
    }
    candidate_identity_rows = list(
        (
            await session.scalars(
                select(ProvenanceIdentityMapping).where(
                    ProvenanceIdentityMapping.target_database_uid.in_(candidate_uids)
                )
            )
        ).all()
    )
    identity_rows = [
        row
        for row in candidate_identity_rows
        if row.target_user_id == scope.user_id
        and row.target_organization_id == scope.organization_id
        and row.target_workspace_id == scope.workspace_id
    ]
    mapped_uids = {
        collection: {
            row.target_database_uid
            for row in candidate_identity_rows
            if row.entity_kind == collection
        }
        for collection in _REMAPPED_COLLECTIONS
    }
    target_mapped_uids = {
        collection: {
            row.target_database_uid
            for row in identity_rows
            if row.entity_kind == collection
        }
        for collection in _REMAPPED_COLLECTIONS
    }
    if identity_rows:
        nodes_by_id = {row.content_node_id: row for row in nodes}
        nodes_by_uid = {row.content_node_uid: row for row in nodes}
        selected_node_uids = {
            row.content_node_uid
            for row in nodes
            if row.content_node_uid in target_mapped_uids["content_nodes"]
        } | {nodes_by_id[row.content_node_id].content_node_uid for row in cited_segments}
        pending_node_uids = list(selected_node_uids)
        while pending_node_uids:
            parent_uid = nodes_by_uid[pending_node_uids.pop()].parent_node_uid
            if parent_uid is not None and parent_uid not in selected_node_uids:
                selected_node_uids.add(parent_uid)
                pending_node_uids.append(parent_uid)
        cited_segment_uid_set = {row.content_segment_uid for row in cited_segments}
        nodes = [row for row in nodes if row.content_node_uid in selected_node_uids]
        segments = [
            row
            for row in segments
            if row.content_segment_uid in target_mapped_uids["content_segments"]
            or row.content_segment_uid in cited_segment_uid_set
        ]
        selected_node_ids = {row.content_node_id for row in nodes}
        selected_segment_ids = {row.content_segment_id for row in segments}
        structural_edges = [
            row
            for row in structural_edges
            if row.edge_uid in target_mapped_uids["structural_edges"]
            or (
                (row.source_node_id is None or row.source_node_id in selected_node_ids)
                and (
                    row.target_node_id is None or row.target_node_id in selected_node_ids
                )
                and (
                    row.source_segment_id is None
                    or row.source_segment_id in selected_segment_ids
                )
                and (
                    row.target_segment_id is None
                    or row.target_segment_id in selected_segment_ids
                )
                and any(
                    value is not None
                    for value in (
                        row.source_node_id,
                        row.target_node_id,
                        row.source_segment_id,
                        row.target_segment_id,
                    )
                )
            )
        ]
    else:
        nodes = [
            row
            for row in nodes
            if row.content_node_uid not in mapped_uids["content_nodes"]
        ]
        segments = [
            row
            for row in segments
            if row.content_segment_uid not in mapped_uids["content_segments"]
        ]
        structural_edges = [
            row
            for row in structural_edges
            if row.edge_uid not in mapped_uids["structural_edges"]
        ]
    database_uids = {
        "content_nodes": {row.content_node_uid for row in nodes},
        "content_segments": {row.content_segment_uid for row in segments},
        "structural_edges": {row.edge_uid for row in structural_edges},
        "project_objects": {row.object_uid for row in project_objects},
        "project_edges": {row.edge_uid for row in project_edges},
        "corrections": {row.correction_uid for row in corrections},
    }
    relevant_identity_rows = [
        row
        for row in identity_rows
        if row.entity_kind in database_uids
        and row.target_database_uid in database_uids[row.entity_kind]
    ]
    reverse_maps = {collection: {} for collection in _REMAPPED_COLLECTIONS}
    source_scopes = {
        (
            row.source_user_uid,
            row.source_organization_uid,
            row.source_workspace_uid,
        )
        for row in relevant_identity_rows
    }
    can_restore_source_identity = bool(relevant_identity_rows) and len(
        source_scopes
    ) == 1
    if can_restore_source_identity:
        for collection in _REMAPPED_COLLECTIONS:
            collection_rows = [
                row for row in relevant_identity_rows if row.entity_kind == collection
            ]
            if {row.target_database_uid for row in collection_rows} != database_uids[
                collection
            ]:
                can_restore_source_identity = False
                break
            reverse_maps[collection] = {
                row.target_database_uid: row.portable_uid for row in collection_rows
            }

    if can_restore_source_identity:
        source_user_uid, source_organization_uid, source_workspace_uid = next(
            iter(source_scopes)
        )
    else:
        source_user_uid = _source_user_uid(scope.user_id)
        source_organization_uid = scope.organization_id or "unscoped"
        source_workspace_uid = scope.workspace_id
    attachment_records, attachment_uids = _attachment_records(attachments, email_uids)
    attachment_references = {
        f"attachment-{attachment_id}": f"attachment:{attachment_uid}"
        for attachment_id, attachment_uid in attachment_uids.items()
    }
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
            "user_uid": source_user_uid,
            "organization_uid": source_organization_uid,
            "workspace_uid": source_workspace_uid,
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
                project_object,
                email_uids,
                attachment_uids,
                segment_uids,
                attachment_references,
            )
            for project_object in project_objects
        ],
        "project_edges": [
            _project_edge_record(edge, object_uids, segment_uids)
            for edge in project_edges
        ],
        "corrections": [
            _correction_record(correction, object_uids, attachment_references)
            for correction in corrections
        ],
    }
    if can_restore_source_identity:
        payload = _translate_identity_records(payload, reverse_maps)
    records = {
        "profile": "naruon-tenant-provenance/v1",
        "schema_version": 1,
        **payload,
        "export_activity": {
            "date_published": "1980-01-01T00:00:00Z",
        },
    }
    content_digest = _content_identity_digest(records)
    records["bundle_uid"] = f"bundle-{content_digest}"
    records["export_activity"]["activity_uid"] = f"export-{content_digest}"
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


def _bounded_text(
    record: Mapping[str, object],
    key: str,
    maximum: int,
    *,
    optional: bool = False,
) -> str | None:
    value = _optional_text(record, key) if optional else _required_text(record, key)
    if value is not None and len(value) > maximum:
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
        _bounded_text(attachment, "content_type", 120)
        _bounded_text(attachment, "parse_status", 64)
        _bounded_text(attachment, "parse_content_type", 120)
        _bounded_text(attachment, "parser_key", 64)
        _bounded_text(attachment, "parse_error_code", 120, optional=True)
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
        _bounded_text(node, "content_node_uid", 64)
        _bounded_text(node, "source_kind", 64)
        _bounded_text(node, "source_record_uid", 256)
        _bounded_text(node, "parent_node_uid", 64, optional=True)
        _bounded_text(node, "node_kind", 64)
        _bounded_text(node, "node_path", 512)
        _bounded_text(node, "display_label", 240, optional=True)
        _bounded_text(node, "content_hash", 64)
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
        _bounded_text(segment, "content_segment_uid", 64)
        _bounded_text(segment, "source_kind", 64)
        _bounded_text(segment, "source_record_uid", 256)
        _bounded_text(segment, "segment_kind", 64)
        _bounded_text(segment, "segment_path", 512)
        _bounded_text(segment, "heading_path", 512, optional=True)
        _bounded_text(segment, "content_hash", 64)
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
        _bounded_text(edge, "edge_uid", 64)
        _bounded_text(edge, "source_kind", 64)
        _bounded_text(edge, "source_record_uid", 256)
        _bounded_text(edge, "edge_kind", 64)
        _bounded_text(edge, "edge_path", 512)
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
        _bounded_text(project_object, "object_uid", 96)
        _bounded_text(project_object, "object_type", 64)
        _bounded_text(project_object, "title", 240)
        _bounded_text(project_object, "status_code", 64)
        _bounded_text(project_object, "extractor_name", 120)
        _bounded_text(project_object, "extractor_version", 64)
        _parse_confidence(project_object.get("confidence"))
        _uid_list(project_object, "source_segment_uids")
        if not isinstance(project_object.get("attributes_json"), dict):
            _fail()
        _validate_safe_metadata(project_object["attributes_json"])

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
        _bounded_text(edge, "edge_uid", 96)
        _bounded_text(edge, "source_uid", 160)
        _bounded_text(edge, "target_uid", 160)
        _bounded_text(edge, "edge_type", 80)
        _parse_confidence(edge.get("confidence"))
        _uid_list(edge, "source_segment_uids")

    for correction in collections["corrections"]:
        for key in ("correction_uid", "object_uid"):
            _uid(correction, key)
        _required_text(correction, "correction_action")
        _bounded_text(correction, "correction_uid", 96)
        _bounded_text(correction, "correction_action", 64)
        _optional_text(correction, "rationale")
        _uid_list(correction, "source_segment_uids")
        if not isinstance(correction.get("before_json"), dict) or not isinstance(
            correction.get("after_json"), dict
        ):
            _fail()
        _validate_safe_metadata(correction["before_json"])
        _validate_safe_metadata(correction["after_json"])
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
        "user_uid",
        "organization_uid",
        "workspace_uid",
    }:
        _fail()
    source_user_uid = source_scope.get("user_uid")
    if (
        not isinstance(source_user_uid, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_user_uid) is None
    ):
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
    _attachments_in_occurrence_order(collections["attachments"])
    node_email = {
        record["content_node_uid"]: record["email_uid"]
        for record in collections["content_nodes"]
    }
    segment_email = {
        record["content_segment_uid"]: record["email_uid"]
        for record in collections["content_segments"]
    }
    segment_attachment = {
        record["content_segment_uid"]: record["attachment_uid"]
        for record in collections["content_segments"]
    }
    object_email = {
        record["object_uid"]: record["email_uid"]
        for record in collections["project_objects"]
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
            record["attachment_uid"] is not None
            and record["source_record_uid"] != f"attachment:{record['attachment_uid']}"
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
        if (
            record["attachment_uid"] is not None
            and record["source_record_uid"] != f"attachment:{record['attachment_uid']}"
        ):
            _fail()
    for record in collections["structural_edges"]:
        email_uid = record["email_uid"]
        require_reference(email_uid, email_uids)
        require_reference(record["attachment_uid"], attachment_uids)
        if (
            record["attachment_uid"] is not None
            and attachment_email[record["attachment_uid"]] != email_uid
        ):
            _fail()
        if (
            record["attachment_uid"] is not None
            and record["source_record_uid"] != f"attachment:{record['attachment_uid']}"
        ):
            _fail()
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
        if (
            record["attachment_uid"] is not None
            and attachment_email[record["attachment_uid"]] != record["email_uid"]
        ):
            _fail()
        if (
            segment_attachment[record["primary_content_segment_uid"]]
            != record["attachment_uid"]
        ):
            _fail()
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)
            if segment_email[segment_uid] != record["email_uid"]:
                _fail()
    for record in collections["project_edges"]:
        require_reference(record["source_object_uid"], object_uids)
        require_reference(record["target_object_uid"], object_uids)
        endpoint_uids = {
            endpoint_uid
            for endpoint_uid in (
                record["source_object_uid"],
                record["target_object_uid"],
            )
            if endpoint_uid is not None
        }
        if not endpoint_uids:
            _fail()
        endpoint_email_uids = {
            object_email[endpoint_uid] for endpoint_uid in endpoint_uids
        }
        for field, object_field in (
            ("source_uid", "source_object_uid"),
            ("target_uid", "target_object_uid"),
        ):
            if record[object_field] is not None:
                if record[field] != record[object_field]:
                    _fail()
                continue
            segment_uid = _segment_endpoint_uid(record[field])
            require_reference(segment_uid, segment_uids)
            if segment_email[segment_uid] not in endpoint_email_uids:
                _fail()
        require_reference(record["primary_content_segment_uid"], segment_uids)
        if (
            segment_email[record["primary_content_segment_uid"]]
            not in endpoint_email_uids
        ):
            _fail()
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)
            if segment_email[segment_uid] not in endpoint_email_uids:
                _fail()
    for record in collections["corrections"]:
        require_reference(record["object_uid"], object_uids)
        for segment_uid in record["source_segment_uids"]:
            require_reference(segment_uid, segment_uids)
            if segment_email[segment_uid] != object_email[record["object_uid"]]:
                _fail()

    rooted_email_uids = {
        record["email_uid"] for record in collections["project_objects"]
    }
    for record in collections["project_objects"]:
        rooted_email_uids.add(segment_email[record["primary_content_segment_uid"]])
        rooted_email_uids.update(
            segment_email[segment_uid] for segment_uid in record["source_segment_uids"]
        )
    for record in collections["project_edges"]:
        rooted_email_uids.add(segment_email[record["primary_content_segment_uid"]])
        rooted_email_uids.update(
            segment_email[segment_uid] for segment_uid in record["source_segment_uids"]
        )
    for record in collections["corrections"]:
        rooted_email_uids.update(
            segment_email[segment_uid] for segment_uid in record["source_segment_uids"]
        )
    if email_uids and rooted_email_uids != email_uids:
        _fail()


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


async def _prepare_identity_import(
    session: AsyncSession,
    scope: TenantProvenanceScope,
    records: Mapping[str, object],
) -> tuple[dict[str, object], list[ProvenanceIdentityMapping]]:
    source_scope = records["source_scope"]
    same_scope = (
        source_scope["user_uid"] == _source_user_uid(scope.user_id)
        and source_scope["organization_uid"] == (scope.organization_id or "unscoped")
        and source_scope["workspace_uid"] == scope.workspace_id
    )
    if same_scope:
        return copy.deepcopy(records), []

    forward_maps = {collection: {} for collection in _REMAPPED_COLLECTIONS}
    for collection in _REMAPPED_COLLECTIONS:
        for record in records[collection]:
            portable_uid = record[_UID_KEYS[collection]]
            forward_maps[collection][portable_uid] = _target_database_uid(
                scope, source_scope, collection, portable_uid
            )
    expected_mapping_keys = {
        (collection, portable_uid)
        for collection, collection_map in forward_maps.items()
        for portable_uid in collection_map
    }
    organization_filter = (
        ProvenanceIdentityMapping.target_organization_id == scope.organization_id
        if scope.organization_id is not None
        else ProvenanceIdentityMapping.target_organization_id.is_(None)
    )
    scoped_mapping_rows = list(
        (
            await session.scalars(
                select(ProvenanceIdentityMapping).where(
                    ProvenanceIdentityMapping.target_user_id == scope.user_id,
                    organization_filter,
                    ProvenanceIdentityMapping.target_workspace_id == scope.workspace_id,
                    ProvenanceIdentityMapping.source_user_uid
                    == source_scope["user_uid"],
                    ProvenanceIdentityMapping.source_organization_uid
                    == source_scope["organization_uid"],
                    ProvenanceIdentityMapping.source_workspace_uid
                    == source_scope["workspace_uid"],
                    ProvenanceIdentityMapping.entity_kind.in_(_REMAPPED_COLLECTIONS),
                )
            )
        ).all()
    )
    scoped_mappings = {
        (row.entity_kind, row.portable_uid): row
        for row in scoped_mapping_rows
        if (row.entity_kind, row.portable_uid) in expected_mapping_keys
    }
    if scoped_mappings:
        if set(scoped_mappings) != expected_mapping_keys:
            _fail()
        for (collection, portable_uid), row in scoped_mappings.items():
            if row.target_database_uid not in {
                portable_uid,
                forward_maps[collection][portable_uid],
            }:
                _fail()
            forward_maps[collection][portable_uid] = row.target_database_uid
        return _translate_identity_records(records, forward_maps), []

    scoped_collisions: list[tuple[str, Any, str]] = []
    for model, column, collection in (
        (
            ProjectGraphObjectRecord,
            ProjectGraphObjectRecord.object_uid,
            "project_objects",
        ),
        (ProjectGraphEdgeRecord, ProjectGraphEdgeRecord.edge_uid, "project_edges"),
        (
            ProjectGraphCorrectionRecord,
            ProjectGraphCorrectionRecord.correction_uid,
            "corrections",
        ),
    ):
        portable_uids = {
            record[_UID_KEYS[collection]] for record in records[collection]
        }
        if portable_uids:
            scoped_collisions.extend(
                (collection, row, getattr(row, _UID_KEYS[collection]))
                for row in (
                    await session.scalars(select(model).where(column.in_(portable_uids)))
                ).all()
            )
    if not scoped_collisions:
        return copy.deepcopy(records), [
            ProvenanceIdentityMapping(
                target_user_id=scope.user_id,
                target_organization_id=scope.organization_id,
                target_workspace_id=scope.workspace_id,
                source_user_uid=source_scope["user_uid"],
                source_organization_uid=source_scope["organization_uid"],
                source_workspace_uid=source_scope["workspace_uid"],
                entity_kind=collection,
                portable_uid=portable_uid,
                target_database_uid=portable_uid,
            )
            for collection in _REMAPPED_COLLECTIONS
            for portable_uid in forward_maps[collection]
        ]
    if any(
        row.user_id == scope.user_id
        and row.organization_id == scope.organization_id
        and row.workspace_id == scope.workspace_id
        for _, row, _ in scoped_collisions
    ):
        return copy.deepcopy(records), []
    native_source = all(
        _source_user_uid(row.user_id) == source_scope["user_uid"]
        and (row.organization_id or "unscoped") == source_scope["organization_uid"]
        and row.workspace_id == source_scope["workspace_uid"]
        for _, row, _ in scoped_collisions
    )
    if not native_source:
        collision_keys = {
            (collection, portable_uid)
            for collection, _, portable_uid in scoped_collisions
        }
        origin_rows = list(
            (
                await session.scalars(
                    select(ProvenanceIdentityMapping).where(
                        ProvenanceIdentityMapping.target_database_uid.in_(
                            {portable_uid for _, portable_uid in collision_keys}
                        )
                    )
                )
            ).all()
        )
        origins = {
            (row.entity_kind, row.target_database_uid): row
            for row in origin_rows
            if (row.entity_kind, row.target_database_uid) in collision_keys
        }
        if set(origins) != collision_keys or any(
            row.source_user_uid != source_scope["user_uid"]
            or row.source_organization_uid != source_scope["organization_uid"]
            or row.source_workspace_uid != source_scope["workspace_uid"]
            for row in origins.values()
        ):
            _fail()

    target_uids = {
        database_uid
        for collection_map in forward_maps.values()
        for database_uid in collection_map.values()
    }
    existing_rows = list(
        (
            await session.scalars(
                select(ProvenanceIdentityMapping).where(
                    ProvenanceIdentityMapping.target_database_uid.in_(target_uids)
                )
            )
        ).all()
    )
    existing = {(row.entity_kind, row.portable_uid): row for row in existing_rows}
    new_rows: list[ProvenanceIdentityMapping] = []
    for collection, collection_map in forward_maps.items():
        for portable_uid, database_uid in collection_map.items():
            row = existing.get((collection, portable_uid))
            expected = (
                scope.user_id,
                scope.organization_id,
                scope.workspace_id,
                source_scope["user_uid"],
                source_scope["organization_uid"],
                source_scope["workspace_uid"],
                database_uid,
            )
            if row is not None:
                actual = (
                    row.target_user_id,
                    row.target_organization_id,
                    row.target_workspace_id,
                    row.source_user_uid,
                    row.source_organization_uid,
                    row.source_workspace_uid,
                    row.target_database_uid,
                )
                if actual != expected:
                    _fail()
                continue
            new_rows.append(
                ProvenanceIdentityMapping(
                    target_user_id=scope.user_id,
                    target_organization_id=scope.organization_id,
                    target_workspace_id=scope.workspace_id,
                    source_user_uid=source_scope["user_uid"],
                    source_organization_uid=source_scope["organization_uid"],
                    source_workspace_uid=source_scope["workspace_uid"],
                    entity_kind=collection,
                    portable_uid=portable_uid,
                    target_database_uid=database_uid,
                )
            )
    return _translate_identity_records(records, forward_maps), new_rows


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
    attachment_references = {
        f"attachment-{attachment_id}": f"attachment:{attachment_uid}"
        for attachment_id, attachment_uid in attachment_uids.items()
    }
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
            uid: _project_object_record(
                row,
                email_uids,
                attachment_uids,
                segment_uids,
                attachment_references,
            )
            for uid, row in models["project_objects"].items()
        }
        existing_serialized["project_edges"] = {
            uid: _project_edge_record(row, object_uids, segment_uids)
            for uid, row in models["project_edges"].items()
        }
        existing_serialized["corrections"] = {
            uid: _correction_record(row, object_uids, attachment_references)
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

    for record in _attachments_in_occurrence_order(records["attachments"]):
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
        transaction = (
            session.begin_nested() if session.in_transaction() else session.begin()
        )
        async with transaction:
            bind = session.get_bind()
            if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
                for email_uid in sorted(
                    record["email_uid"] for record in records["emails"]
                ):
                    lock_digest = hashlib.sha256(
                        _canonical_json(
                            {
                                "namespace": "tenant-provenance-email-import-v1",
                                "target_owner": {
                                    "user_uid": _source_user_uid(scope.user_id),
                                    "organization_uid": scope.organization_id,
                                },
                                "email_uid": email_uid,
                            }
                        )
                    ).digest()
                    lock_key = int.from_bytes(lock_digest[:8], "big", signed=True)
                    await session.execute(
                        select(func.pg_advisory_xact_lock(lock_key))
                    )
            database_records, identity_rows = await _prepare_identity_import(
                session, scope, records
            )
            models = await _preflight_existing(session, scope, database_records)
            skipped = {
                collection: len(models[collection]) for collection in _COLLECTIONS
            }
            await _insert_records(session, scope, database_records, models, created)
            session.add_all(identity_rows)
            await session.flush()
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
