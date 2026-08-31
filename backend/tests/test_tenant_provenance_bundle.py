import hashlib
import io
import json
import warnings
import zipfile

import pytest

from services.tenant_provenance_bundle import (
    ARCHIVE_MAX_BYTES,
    ARCHIVE_MAX_ENTRIES,
    ENTRY_MAX_BYTES,
    JSON_SAFE_INTEGER_MAX,
    MAX_COMPRESSION_RATIO,
    ProvenanceArchiveError,
    _within_archive_bounds,
    build_provenance_archive,
    parse_provenance_archive,
)


RECORDS = {
    "profile": "naruon-tenant-provenance/v1",
    "schema_version": 1,
    "bundle_uid": "bundle-01HZZ",
    "source_scope": {"organization_uid": "org-01", "workspace_uid": "ws-01"},
    "export_activity": {
        "activity_uid": "activity-01",
        "date_published": "1980-01-01T00:00:00Z",
    },
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
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


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
    tag_names = (
        "bag-info.txt",
        "bagit.txt",
        "manifest-sha512.txt",
        "ro-crate-metadata.json",
    )
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
                target.writestr(
                    info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
                )
            else:
                target.writestr(name, content)
        for name, content in extra:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                target.writestr(name, content)
    return output.getvalue()


def _archive_with_zip_metadata(
    entries, *, archive_comment=b"", member_extra=b"", member_comment=b""
):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.extra = member_extra
            info.comment = member_comment
            target.writestr(
                info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
            )
        target.comment = archive_comment
    return output.getvalue()


def test_build_is_deterministic_and_has_exact_fixed_entries():
    first = build_provenance_archive(RECORDS)
    second = build_provenance_archive(dict(RECORDS))

    assert first == second
    with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
        assert tuple(sorted(archive.namelist())) == EXPECTED_ENTRIES
        assert all(
            info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()
        )
        assert all(
            (info.external_attr >> 16) & 0o777 == 0o644 for info in archive.infolist()
        )
        assert archive.read("data/records.json") == _canonical_json(RECORDS)


def test_parse_round_trips_records_and_verifies_ro_crate_metadata():
    archive = build_provenance_archive(RECORDS)

    assert parse_provenance_archive(archive) == RECORDS
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        crate = json.loads(source.read("ro-crate-metadata.json"))
    assert crate["@context"] == [
        "https://w3id.org/ro/crate/1.3/context",
        {"prov": "http://www.w3.org/ns/prov#"},
    ]
    nodes = {node["@id"]: node for node in crate["@graph"]}
    assert nodes["ro-crate-metadata.json"] == {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "about": {"@id": "./"},
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.3"},
    }
    assert nodes["./"]["datePublished"] == RECORDS["export_activity"]["date_published"]
    assert nodes["#activity-01"]["prov:wasAssociatedWith"] == {"@id": "#naruon"}
    assert "prov:SoftwareAgent" in nodes["#naruon"]["@type"]


@pytest.mark.parametrize("date_published", ("not-a-date", "2026-02-30"))
def test_build_rejects_non_iso_ro_crate_date_published(date_published):
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive(
            {
                **RECORDS,
                "export_activity": {
                    **RECORDS["export_activity"],
                    "date_published": date_published,
                },
            }
        )


def test_build_preserves_valid_iso_ro_crate_date_published():
    archive = build_provenance_archive(RECORDS)

    assert (
        parse_provenance_archive(archive)["export_activity"]["date_published"]
        == "1980-01-01T00:00:00Z"
    )


def test_parse_rejects_payload_tampering():
    archive = build_provenance_archive(RECORDS)
    tampered = _replace_entries(archive, {"data/records.json": b'{"tampered":true}'})

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(tampered)


@pytest.mark.parametrize(
    "name",
    ("manifest-sha512.txt", "tagmanifest-sha512.txt", "ro-crate-metadata.json"),
)
def test_parse_rejects_direct_tag_and_metadata_tampering(name):
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}
    entries[name] += b"x"

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries))


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


@pytest.mark.parametrize(
    "value",
    (-0.0, 1e-7, 1.0, JSON_SAFE_INTEGER_MAX + 1),
)
def test_build_rejects_values_outside_the_stdlib_jcs_subset(value):
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "unsupported": value})


def test_build_rejects_non_ascii_object_keys():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "\ufffd": "bmp", "\U0001f600": "non-bmp"})


def test_build_rejects_an_unknown_profile():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "profile": "unknown"})


def test_profile_rejects_boolean_schema_version_and_tag_injection():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "schema_version": True})
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "bundle_uid": "bundle\nInjected: value"})
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive(
            {
                **RECORDS,
                "export_activity": {
                    **RECORDS["export_activity"],
                    "activity_uid": "bad\ruid",
                },
            }
        )


@pytest.mark.parametrize(
    "records_json",
    (
        b'{ "profile":"naruon-tenant-provenance/v1"}',
        b'{"profile":"naruon-tenant-provenance/v1","schema_version":NaN}',
        _canonical_json({**RECORDS, "profile": "unknown"}),
    ),
)
def test_parse_rejects_noncanonical_nonfinite_and_unknown_profile(records_json):
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}
    entries["data/records.json"] = records_json

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries))


def test_parse_rejects_nonfixed_zip_metadata():
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(entries, fixed_metadata=False))


@pytest.mark.parametrize(
    "metadata",
    (
        {"archive_comment": b"archive-comment"},
        {"member_extra": b"\x01\x00\x00\x00"},
        {"member_comment": b"member-comment"},
    ),
)
def test_parse_rejects_zip_comments_and_extra_fields(metadata):
    archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        entries = {info.filename: source.read(info) for info in source.infolist()}

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_zip_metadata(entries, **metadata))


@pytest.mark.parametrize(
    "container_bytes", (b"leading-", b"trailing-unvalidated-bytes")
)
def test_parse_rejects_leading_and_trailing_container_bytes(container_bytes):
    archive = build_provenance_archive(RECORDS)
    candidate = (
        container_bytes + archive
        if container_bytes == b"leading-"
        else archive + container_bytes
    )

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(candidate)


@pytest.mark.parametrize(
    "archive",
    (
        lambda value: value[:-1],
        lambda value: value[:-22] + b"truncated",
        lambda value: value[:-22] + b"gap" + value[-22:],
    ),
)
def test_parse_rejects_truncated_or_malformed_eocd(archive):
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(archive(build_provenance_archive(RECORDS)))


def test_production_archive_limits_are_fixed():
    assert ARCHIVE_MAX_BYTES == 64 * 1024 * 1024
    assert ARCHIVE_MAX_ENTRIES == 64
    assert ENTRY_MAX_BYTES == 32 * 1024 * 1024
    assert MAX_COMPRESSION_RATIO == 100


@pytest.mark.parametrize(
    (
        "archive_bytes",
        "entry_count",
        "total_bytes",
        "entry_bytes",
        "compressed_bytes",
        "expected",
    ),
    (
        (ARCHIVE_MAX_BYTES - 1, 0, 0, 0, 0, True),
        (ARCHIVE_MAX_BYTES, 0, 0, 0, 0, True),
        (ARCHIVE_MAX_BYTES + 1, 0, 0, 0, 0, False),
        (0, ARCHIVE_MAX_ENTRIES - 1, 0, 0, 0, True),
        (0, ARCHIVE_MAX_ENTRIES, 0, 0, 0, True),
        (0, ARCHIVE_MAX_ENTRIES + 1, 0, 0, 0, False),
        (0, 0, ARCHIVE_MAX_BYTES - 1, 0, 0, True),
        (0, 0, ARCHIVE_MAX_BYTES, 0, 0, True),
        (0, 0, ARCHIVE_MAX_BYTES + 1, 0, 0, False),
        (0, 0, 0, ENTRY_MAX_BYTES - 1, ENTRY_MAX_BYTES, True),
        (0, 0, 0, ENTRY_MAX_BYTES, ENTRY_MAX_BYTES, True),
        (0, 0, 0, ENTRY_MAX_BYTES + 1, ENTRY_MAX_BYTES + 1, False),
        (0, 0, 0, MAX_COMPRESSION_RATIO - 1, 1, True),
        (0, 0, 0, MAX_COMPRESSION_RATIO, 1, True),
        (0, 0, 0, MAX_COMPRESSION_RATIO + 1, 1, False),
    ),
)
def test_production_archive_limits_boundary(
    archive_bytes, entry_count, total_bytes, entry_bytes, compressed_bytes, expected
):
    assert (
        _within_archive_bounds(
            archive_bytes=archive_bytes,
            entry_count=entry_count,
            total_bytes=total_bytes,
            entry_bytes=entry_bytes,
            compressed_bytes=compressed_bytes,
        )
        is expected
    )


def test_build_output_always_passes_parser_bounds():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "padding": "x" * 1_000_000})


def test_parse_enforces_total_uncompressed_bound(monkeypatch):
    archive = build_provenance_archive({**RECORDS, "padding": "x" * 10_000})
    monkeypatch.setattr(
        "services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", len(archive) + 1
    )

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(archive)


def test_parse_rejects_archive_bounds(monkeypatch):
    monkeypatch.setattr("services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", 1)
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(build_provenance_archive(RECORDS))

    monkeypatch.setattr(
        "services.tenant_provenance_bundle.ARCHIVE_MAX_BYTES", ARCHIVE_MAX_BYTES
    )
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

    monkeypatch.setattr(
        "services.tenant_provenance_bundle.ARCHIVE_MAX_ENTRIES", ARCHIVE_MAX_ENTRIES
    )
    records = _canonical_json({**RECORDS, "padding": "x" * 10_000})
    entries["data/records.json"] = records
    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(_archive_with_entries(_rebuild_manifests(entries)))
