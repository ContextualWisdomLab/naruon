"""Deterministic, bounded BagIt/RO-Crate envelopes for tenant provenance."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import struct
import zipfile
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any


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


class ProvenanceArchiveError(ValueError):
    """Raised when a provenance envelope is malformed or outside this profile."""


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
