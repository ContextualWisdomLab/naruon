"""Deterministic, bounded BagIt/RO-Crate envelopes for tenant provenance."""

from __future__ import annotations

import hashlib
import io
import json
import math
import stat
import zipfile
from collections.abc import Mapping
from typing import Any


ARCHIVE_MAX_BYTES = 64 * 1024 * 1024
ARCHIVE_MAX_ENTRIES = 64
ENTRY_MAX_BYTES = 32 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
JSON_MAX_DEPTH = 64
_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_PAYLOAD_NAME = "data/records.json"
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
    if value is None or isinstance(value, (str, bool, int)):
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
    if records.get("profile") != "naruon-tenant-provenance/v1" or records.get(
        "schema_version"
    ) != 1:
        _fail()
    bundle_uid = records.get("bundle_uid")
    if not isinstance(bundle_uid, str) or not bundle_uid:
        _fail()
    return bundle_uid


def _bag_info(bundle_uid: str) -> bytes:
    return (
        "Bag-Software-Agent: naruon\n"
        "Bagging-Date: 1980-01-01\n"
        f"External-Identifier: {bundle_uid}\n"
    ).encode("utf-8")


def _ro_crate(records: Mapping[str, object], payload_digest: str) -> bytes:
    activity = records.get("export_activity")
    activity_uid = activity.get("activity_uid") if isinstance(activity, Mapping) else None
    if not isinstance(activity_uid, str) or not activity_uid:
        _fail()
    crate = {
        "@context": "https://w3id.org/ro/crate/1.3/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "conformsTo": "naruon-tenant-provenance/v1",
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
                "@type": "CreateAction",
                "instrument": {"@id": "#naruon"},
                "object": {"@id": _PAYLOAD_NAME},
            },
            {
                "@id": "#naruon",
                "@type": "SoftwareApplication",
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
        "ro-crate-metadata.json": _ro_crate(records, hashlib.sha512(payload).hexdigest()),
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
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def build_provenance_archive(records: Mapping[str, object]) -> bytes:
    """Build the fixed deterministic ZIP envelope for a validated record payload."""
    if not isinstance(records, Mapping):
        _fail()
    entries = _archive_entries(records)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            archive.writestr(_zip_info(name), entries[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    archive_bytes = output.getvalue()
    if len(archive_bytes) > ARCHIVE_MAX_BYTES:
        _fail()
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


def _read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > ENTRY_MAX_BYTES:
        _fail()
    if info.file_size and (not info.compress_size or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO):
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
    if not isinstance(archive_bytes, (bytes, bytearray)) or len(archive_bytes) > ARCHIVE_MAX_BYTES:
        _fail()
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            if (
                len(infos) > ARCHIVE_MAX_ENTRIES
                or sum(info.file_size for info in infos) > ARCHIVE_MAX_BYTES
                or any(
                    _is_unsafe_member(info)
                    or info.date_time != _FIXED_TIMESTAMP
                    or info.create_system != 3
                    or (info.external_attr >> 16) & 0o777 != 0o644
                    or info.compress_type != zipfile.ZIP_DEFLATED
                    for info in infos
                )
            ):
                _fail()
            names = [info.filename for info in infos]
            if (
                names != sorted(names)
                or len(set(names)) != len(names)
                or set(names) != _EXPECTED_ENTRIES
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
