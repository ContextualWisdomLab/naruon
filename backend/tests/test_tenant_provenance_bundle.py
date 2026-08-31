import hashlib
import io
import json
import warnings
import zipfile

import pytest

from services.tenant_provenance_bundle import (
    ARCHIVE_MAX_BYTES,
    ARCHIVE_MAX_ENTRIES,
    ProvenanceArchiveError,
    build_provenance_archive,
    parse_provenance_archive,
)


RECORDS = {
    "profile": "naruon-tenant-provenance/v1",
    "schema_version": 1,
    "bundle_uid": "bundle-01HZZ",
    "source_scope": {"organization_uid": "org-01", "workspace_uid": "ws-01"},
    "export_activity": {"activity_uid": "activity-01"},
    "emails": [{"email_uid": "email-01", "subject": "Evidence"}],
    "attachments": [],
    "content_nodes": [],
    "content_segments": [],
    "structural_edges": [],
    "project_objects": [],
    "project_edges": [],
    "corrections": [],
}

EXPECTED_ENTRIES = (
    "bag-info.txt",
    "bagit.txt",
    "data/records.json",
    "manifest-sha512.txt",
    "ro-crate-metadata.json",
    "tagmanifest-sha512.txt",
)


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _replace_entries(archive, replacements, *, extra=()):
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {
            info.filename: source.read(info)
            for info in source.infolist()
            if not info.is_dir()
        }
    entries.update(replacements)
    return _archive_with_entries(entries, extra=extra)


def _rebuild_manifests(entries):
    payload_names = ("data/records.json",)
    entries["manifest-sha512.txt"] = b"".join(
        f"{hashlib.sha512(entries[name]).hexdigest()}  {name}\n".encode("ascii")
        for name in payload_names
    )
    tag_names = ("bag-info.txt", "bagit.txt", "manifest-sha512.txt", "ro-crate-metadata.json")
    entries["tagmanifest-sha512.txt"] = b"".join(
        f"{hashlib.sha512(entries[name]).hexdigest()}  {name}\n".encode("ascii")
        for name in tag_names
    )
    return entries


def _archive_with_entries(entries, *, extra=(), fixed_metadata=True):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, content in sorted(entries.items()):
            if fixed_metadata:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            else:
                target.writestr(name, content)
        for name, content in extra:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                target.writestr(name, content)
    return output.getvalue()


def test_build_is_deterministic_and_has_exact_fixed_entries():
    first = build_provenance_archive(RECORDS)
    second = build_provenance_archive(dict(RECORDS))

    assert first == second
    with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
        assert tuple(sorted(archive.namelist())) == EXPECTED_ENTRIES
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert all((info.external_attr >> 16) & 0o777 == 0o644 for info in archive.infolist())
        assert archive.read("data/records.json") == _canonical_json(RECORDS)


def test_parse_round_trips_records_and_verifies_ro_crate_metadata():
    archive = build_provenance_archive(RECORDS)

    assert parse_provenance_archive(archive) == RECORDS
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        crate = json.loads(source.read("ro-crate-metadata.json"))
    assert crate["@context"] == "https://w3id.org/ro/crate/1.3/context"
    assert {node["@type"] for node in crate["@graph"]} >= {"Dataset", "File", "CreateAction", "SoftwareApplication"}


def test_parse_rejects_payload_tampering():
    archive = build_provenance_archive(RECORDS)
    tampered = _replace_entries(archive, {"data/records.json": b'{"tampered":true}'})

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(tampered)


@pytest.mark.parametrize("name", ("../data/records.json", "data\\records.json"))
def test_parse_rejects_unsafe_paths(name):
    archive = build_provenance_archive(RECORDS)
    unsafe = _replace_entries(archive, {}, extra=((name, b"{}"),))

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(unsafe)


def test_parse_rejects_colliding_paths():
    archive = build_provenance_archive(RECORDS)
    collision = _replace_entries(archive, {}, extra=(("data/records.json", b"{}"),))

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(collision)


@pytest.mark.parametrize("missing_or_extra", ("bagit.txt", "unexpected.txt"))
def test_parse_rejects_missing_or_extra_entries(missing_or_extra):
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}
    if missing_or_extra in entries:
        del entries[missing_or_extra]
    else:
        entries[missing_or_extra] = b"unexpected"

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries))


def test_parse_rejects_duplicate_json_keys_even_with_valid_manifests():
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}
    entries["data/records.json"] = b'{"profile":"first","profile":"second"}'

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(_rebuild_manifests(entries)))


def test_build_rejects_non_finite_json_numbers():
    records = {**RECORDS, "export_activity": {"score": float("nan")}}

    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive(records)


def test_build_rejects_an_unknown_profile():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "profile": "unknown"})


def test_parse_rejects_nonfixed_zip_metadata():
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries, fixed_metadata=False))


def test_parse_enforces_total_uncompressed_bound(monkeypatch):
    archive = build_provenance_archive({**RECORDS, "padding": "x" * 10_000})
    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", len(archive) + 1)

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(archive)


def test_parse_rejects_archive_bounds(monkeypatch):
    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", 1)
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(build_provenance_archive(RECORDS))

    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", ARCHIVE_MAX_BYTES)
    monkeypatch.setattr("services.tenant_provenance_bundle.ENTRY_MAX_BYTES", 1)
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(build_provenance_archive(RECORDS))


def test_parse_rejects_entry_count_and_compression_ratio(monkeypatch):
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}

    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_ENTRIES", 1)
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries))

    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_ENTRIES", ARCHIVE_MAX_ENTRIES)
    records = _canonical_json({**RECORDS, "padding": "x" * 10_000})
    entries["data/records.json"] = records
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(_rebuild_manifests(entries)))
