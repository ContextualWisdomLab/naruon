import copy
import asyncio
import datetime
import hashlib
import importlib.util
import io
import json
import struct
import uuid
import warnings
import zipfile
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import (
    Attachment,
    Base,
    ContentNodeRecord,
    ContentSegmentRecord,
    Email,
    KnowledgeGraphEdgeRecord,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
    ProvenanceIdentityMapping,
)
from services.project_graph.repository import ProjectGraphRepository
from services import tenant_provenance_bundle as provenance_service

from services.tenant_provenance_bundle import (
    ARCHIVE_MAX_BYTES,
    ARCHIVE_MAX_ENTRIES,
    ENTRY_MAX_BYTES,
    JSON_SAFE_INTEGER_MAX,
    MAX_COMPRESSION_RATIO,
    ImportReceipt,
    ProvenanceArchiveError,
    TenantProvenanceScope,
    _within_archive_bounds,
    build_provenance_archive,
    export_tenant_provenance,
    import_tenant_provenance,
    parse_provenance_archive,
)


RECORDS = {
    "profile": "naruon-tenant-provenance/v1",
    "schema_version": 1,
    "bundle_uid": "bundle-01HZZ",
    "source_scope": {
        "user_uid": "0" * 64,
        "organization_uid": "org-01",
        "workspace_uid": "ws-01",
    },
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


@pytest.mark.parametrize(
    "date_published",
    (
        "not-a-date",
        "2026-02-30",
        "1980-01-01",
        "1980-01-01T09:00:00+09:00",
        "1980-01-01T00:00:00+00:00",
        "1980-01-01T00:00:00.000000Z",
    ),
)
def test_build_rejects_noncanonical_ro_crate_date_published(date_published):
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


@pytest.mark.parametrize(
    "date_published",
    (
        "1980-01-01",
        "1980-01-01T09:00:00+09:00",
        "1980-01-01T00:00:00+00:00",
        "1980-01-01T00:00:00.000000Z",
    ),
)
@pytest.mark.asyncio
async def test_import_rejects_noncanonical_activity_timestamp_before_transaction(
    date_published,
):
    valid_archive = build_provenance_archive(RECORDS)
    with zipfile.ZipFile(io.BytesIO(valid_archive), "r") as archive:
        entries = {info.filename: archive.read(info) for info in archive.infolist()}
    records = copy.deepcopy(RECORDS)
    records["export_activity"]["date_published"] = date_published
    payload = _canonical_json(records)
    crate = json.loads(entries["ro-crate-metadata.json"])
    crate_nodes = {node["@id"]: node for node in crate["@graph"]}
    crate_nodes["./"]["datePublished"] = date_published
    crate_nodes["data/records.json"]["sha512"] = hashlib.sha512(payload).hexdigest()
    entries["data/records.json"] = payload
    entries["ro-crate-metadata.json"] = _canonical_json(crate)
    invalid_archive = _archive_with_entries(_rebuild_manifests(entries))

    class NoTransactionSession:
        def in_transaction(self):
            return False

        def begin(self):
            raise AssertionError("transaction must not start")

        async def flush(self):
            raise AssertionError("flush must not run")

    with pytest.raises(ProvenanceArchiveError):
        await import_tenant_provenance(
            NoTransactionSession(),
            TenantProvenanceScope("target-user", "target-org", "target-workspace"),
            invalid_archive,
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


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_build_rejects_non_finite_json_numbers(value):
    records = {**RECORDS, "export_activity": {"score": value}}

    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive(records)


def test_build_rejects_integer_outside_the_json_safe_range():
    with pytest.raises(ProvenanceArchiveError):
        build_provenance_archive({**RECORDS, "unsupported": JSON_SAFE_INTEGER_MAX + 1})


@pytest.mark.parametrize("value", (-0.0, 1e-7, 1.0, 0.73))
def test_build_round_trips_finite_json_floats(value):
    records = {**RECORDS, "finite_value": value}

    assert parse_provenance_archive(build_provenance_archive(records)) == records


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


def test_parse_rejects_gap_before_central_directory():
    archive = build_provenance_archive(RECORDS)
    assert parse_provenance_archive(archive) == RECORDS
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        start_dir = source.start_dir
    gap = b"unaccounted-gap"
    candidate = bytearray(archive[:start_dir] + gap + archive[start_dir:])
    struct.pack_into("<L", candidate, len(candidate) - 22 + 16, start_dir + len(gap))

    with pytest.raises(ProvenanceArchiveError):
        parse_provenance_archive(candidate)


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


@pytest_asyncio.fixture
async def provenance_sessionmaker():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                yield async_sessionmaker(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    except (
        ConnectionRefusedError,
        OSError,
        OperationalError,
        asyncpg.CannotConnectNowError,
        asyncpg.InvalidAuthorizationSpecificationError,
        asyncpg.InvalidCatalogNameError,
        asyncpg.InvalidPasswordError,
    ):
        pytest.skip("PostgreSQL smoke path unavailable")
    finally:
        await engine.dispose()


async def _seed_provenance_closure(
    session,
    *,
    scope: TenantProvenanceScope,
    token: str,
) -> dict[str, object]:
    now = datetime.datetime(2026, 8, 31, 12, 0, tzinfo=datetime.timezone.utc)
    email = Email(
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        message_id=f"<{token}@example.com>",
        thread_id=f"thread-{token}",
        fingerprint=f"sha256:{token}",
        sender="source@example.com",
        reply_to="reply@example.com",
        recipients="owner@example.com",
        subject=f"Evidence {token}",
        in_reply_to=None,
        references=None,
        date=now,
        body="Grounded source evidence",
        is_read=False,
        embedding=[0.125] * 1536,
    )
    session.add(email)
    await session.flush()

    attachment = Attachment(
        email=email,
        filename="evidence.txt",
        content="Parser-confirmed attachment evidence",
        content_type="text/plain",
        parse_status="parsed",
        parse_content_type="text/plain",
        parser_key="plain_text",
        embedding=[0.25] * 1536,
    )
    binary_attachment = Attachment(
        email=email,
        filename="source.pdf",
        content="binary-payload-must-not-export",
        content_type="application/pdf",
        parse_status="pdf_dom_recognition_pending",
        parse_content_type="application/pdf",
        parser_key="pdf",
        embedding=[0.5] * 1536,
    )
    session.add_all([attachment, binary_attachment])
    await session.flush()

    node = ContentNodeRecord(
        content_node_uid=f"node-{token}",
        email=email,
        attachment=attachment,
        source_kind="attachment",
        source_record_uid=f"attachment-source-{token}",
        parent_node_uid=None,
        node_kind="document",
        node_path="/document[1]",
        ordinal_index=1,
        display_label="Evidence",
        safe_text_content="Parser-confirmed attachment evidence",
        content_hash=f"nodehash-{token}",
        created_at=now,
    )
    session.add(node)
    await session.flush()

    segment = ContentSegmentRecord(
        content_segment_uid=f"segment-{token}",
        email=email,
        attachment=attachment,
        content_node=node,
        source_kind="attachment",
        source_record_uid=f"attachment-source-{token}",
        segment_kind="paragraph",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=1,
        heading_path="Evidence",
        safe_text_content="Parser-confirmed attachment evidence",
        content_hash=f"segmenthash-{token}",
        word_count=3,
        created_at=now,
    )
    session.add(segment)
    await session.flush()

    structural_edge = KnowledgeGraphEdgeRecord(
        edge_uid=f"structural-edge-{token}",
        email=email,
        attachment=attachment,
        source_node=node,
        target_segment=segment,
        source_kind="attachment",
        source_record_uid=f"attachment-source-{token}",
        edge_kind="contains",
        edge_path="/document[1]->/document[1]/paragraph[1]",
        ordinal_index=1,
        created_at=now,
    )
    source_object = ProjectGraphObjectRecord(
        object_uid=f"project-object-source-{token}",
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        email=email,
        attachment=attachment,
        primary_content_segment=segment,
        object_type="requirement",
        title="Portable requirement",
        summary="Grounded requirement",
        status_code="accepted",
        confidence=0.91,
        source_segment_uids=[segment.content_segment_uid],
        attributes_json={"rank_value": 1, "source_label": "mail"},
        extractor_name="test-extractor",
        extractor_version="1",
        created_at=now,
        updated_at=now,
    )
    target_object = ProjectGraphObjectRecord(
        object_uid=f"project-object-target-{token}",
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        email=email,
        attachment=attachment,
        primary_content_segment=segment,
        object_type="decision",
        title="Portable decision",
        summary="Grounded decision",
        status_code="accepted",
        confidence=0.87,
        source_segment_uids=[segment.content_segment_uid],
        attributes_json={"decision_state": "approved"},
        extractor_name="test-extractor",
        extractor_version="1",
        created_at=now,
        updated_at=now,
    )
    session.add_all([structural_edge, source_object, target_object])
    await session.flush()

    project_edge = ProjectGraphEdgeRecord(
        edge_uid=f"project-edge-{token}",
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        source_uid=source_object.object_uid,
        target_uid=target_object.object_uid,
        edge_type="supports",
        confidence=0.89,
        source_segment_uids=[segment.content_segment_uid],
        source_object=source_object,
        target_object=target_object,
        primary_content_segment=segment,
        created_at=now,
    )
    correction = ProjectGraphCorrectionRecord(
        correction_uid=f"correction-{token}",
        project_object=source_object,
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        actor_user_id=scope.user_id,
        correction_action="accept",
        before_json={"status_code": "candidate", "rank_value": 0},
        after_json={"status_code": "accepted", "rank_value": 1},
        rationale="Verified against source",
        source_segment_uids=[segment.content_segment_uid],
        created_at=now,
    )
    session.add_all([project_edge, correction])
    await session.commit()
    return {
        "email_id": email.id,
        "attachment_id": attachment.id,
        "node_id": node.content_node_id,
        "segment_id": segment.content_segment_id,
        "project_object_id": source_object.project_graph_object_id,
        "email_uid": email.message_id,
        "object_uids": [source_object.object_uid, target_object.object_uid],
    }


async def _delete_exported_closure(session, records: dict[str, object]) -> None:
    emails = records["emails"]
    email_uids = [record["email_uid"] for record in emails]
    email_ids = list(
        (
            await session.scalars(
                select(Email.id).where(Email.message_id.in_(email_uids))
            )
        ).all()
    )
    await session.execute(
        delete(ProjectGraphCorrectionRecord).where(
            ProjectGraphCorrectionRecord.correction_uid.in_(
                [record["correction_uid"] for record in records["corrections"]]
            )
        )
    )
    await session.execute(
        delete(ProjectGraphEdgeRecord).where(
            ProjectGraphEdgeRecord.edge_uid.in_(
                [record["edge_uid"] for record in records["project_edges"]]
            )
        )
    )
    await session.execute(
        delete(ProjectGraphObjectRecord).where(
            ProjectGraphObjectRecord.object_uid.in_(
                [record["object_uid"] for record in records["project_objects"]]
            )
        )
    )
    await session.execute(
        delete(KnowledgeGraphEdgeRecord).where(
            KnowledgeGraphEdgeRecord.email_id.in_(email_ids)
        )
    )
    await session.execute(
        delete(ContentSegmentRecord).where(ContentSegmentRecord.email_id.in_(email_ids))
    )
    await session.execute(
        delete(ContentNodeRecord).where(ContentNodeRecord.email_id.in_(email_ids))
    )
    await session.execute(delete(Attachment).where(Attachment.email_id.in_(email_ids)))
    await session.execute(delete(Email).where(Email.id.in_(email_ids)))
    await session.commit()


async def _add_duplicate_text_attachments(
    session,
    *,
    email_uid: str,
    token: str,
    count: int = 5,
) -> None:
    email = await session.scalar(select(Email).where(Email.message_id == email_uid))
    now = datetime.datetime(2026, 8, 31, 12, 0, tzinfo=datetime.timezone.utc)
    for index in range(1, count + 1):
        attachment = Attachment(
            email=email,
            filename="evidence.txt",
            content="Parser-confirmed attachment evidence",
            content_type="text/plain",
            parse_status="parsed",
            parse_content_type="text/plain",
            parser_key="plain_text",
            embedding=[0.25] * 1536,
        )
        session.add(attachment)
        await session.flush()
        node = ContentNodeRecord(
            content_node_uid=f"duplicate-node-{index}-{token}",
            email=email,
            attachment=attachment,
            source_kind="attachment",
            source_record_uid=f"duplicate-source-{index}-{token}",
            parent_node_uid=None,
            node_kind="document",
            node_path=f"/document[{index + 1}]",
            ordinal_index=index + 1,
            display_label=f"Evidence {index}",
            safe_text_content=f"Duplicate evidence {index}",
            content_hash=f"duplicate-node-hash-{index}-{token}",
            created_at=now,
        )
        session.add(node)
        await session.flush()
        session.add(
            ContentSegmentRecord(
                content_segment_uid=f"duplicate-segment-{index}-{token}",
                email=email,
                attachment=attachment,
                content_node=node,
                source_kind="attachment",
                source_record_uid=f"duplicate-source-{index}-{token}",
                segment_kind="paragraph",
                segment_path=f"/document[{index + 1}]/paragraph[1]",
                ordinal_index=index + 1,
                heading_path=f"Evidence {index}",
                safe_text_content=f"Duplicate evidence {index}",
                content_hash=f"duplicate-segment-hash-{index}-{token}",
                word_count=3,
                created_at=now,
            )
        )
    await session.commit()


async def _seed_email_graph_without_project_rows(
    session,
    *,
    scope: TenantProvenanceScope,
    token: str,
) -> dict[str, object]:
    seeded = await _seed_provenance_closure(session, scope=scope, token=token)
    await session.execute(
        delete(ProjectGraphCorrectionRecord).where(
            ProjectGraphCorrectionRecord.workspace_id == scope.workspace_id,
            ProjectGraphCorrectionRecord.correction_uid == f"correction-{token}",
        )
    )
    await session.execute(
        delete(ProjectGraphEdgeRecord).where(
            ProjectGraphEdgeRecord.workspace_id == scope.workspace_id,
            ProjectGraphEdgeRecord.edge_uid == f"project-edge-{token}",
        )
    )
    await session.execute(
        delete(ProjectGraphObjectRecord).where(
            ProjectGraphObjectRecord.object_uid.in_(seeded["object_uids"])
        )
    )
    await session.commit()
    return seeded


async def _two_email_rooted_archive(
    session,
    *,
    scope: TenantProvenanceScope,
    token: str,
) -> bytes:
    source = await _seed_provenance_closure(session, scope=scope, token=token)
    cited = await _seed_provenance_closure(
        session,
        scope=scope,
        token=f"cited-{token}",
    )
    session.add(
        Attachment(
            email_id=source["email_id"],
            filename="alternate-evidence.txt",
            content="Alternate parser-confirmed attachment evidence",
            content_type="text/plain",
            parse_status="parsed",
            parse_content_type="text/plain",
            parser_key="plain_text",
            embedding=None,
        )
    )
    await session.commit()
    archive = await export_tenant_provenance(session, scope)
    records = parse_provenance_archive(archive)
    assert cited["email_uid"] in {record["email_uid"] for record in records["emails"]}
    return archive


def _scope(token: str) -> TenantProvenanceScope:
    return TenantProvenanceScope(
        user_id=f"user-{token}",
        organization_id=f"org-{token}",
        workspace_id=f"workspace-{token}",
    )


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_postgres_round_trip_preserves_stable_evidence_with_fresh_keys(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        source_keys = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    source_records = parse_provenance_archive(archive)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, source_records)
    async with provenance_sessionmaker() as session:
        receipt = await import_tenant_provenance(session, target_scope, archive)

    assert isinstance(receipt, ImportReceipt)
    assert receipt.created == {
        "emails": 1,
        "attachments": 1,
        "content_nodes": 1,
        "content_segments": 1,
        "structural_edges": 1,
        "project_objects": 2,
        "project_edges": 1,
        "corrections": 1,
    }
    async with provenance_sessionmaker() as session:
        restored_archive = await export_tenant_provenance(session, target_scope)
        restored_email = await session.scalar(
            select(Email).where(Email.message_id == source_keys["email_uid"])
        )
        restored_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source_keys["object_uids"][0]
            )
        )
        restored_correction = await session.scalar(
            select(ProjectGraphCorrectionRecord).where(
                ProjectGraphCorrectionRecord.correction_uid == f"correction-{token}"
            )
        )
        restored_attachment = await session.scalar(
            select(Attachment).where(Attachment.email_id == restored_email.id)
        )
        restored_node = await session.scalar(
            select(ContentNodeRecord).where(
                ContentNodeRecord.content_node_uid == f"node-{token}"
            )
        )
        restored_segment = await session.scalar(
            select(ContentSegmentRecord).where(
                ContentSegmentRecord.content_segment_uid == f"segment-{token}"
            )
        )
    restored_records = parse_provenance_archive(restored_archive)
    for collection in (
        "emails",
        "attachments",
        "content_nodes",
        "content_segments",
        "structural_edges",
        "project_objects",
        "project_edges",
        "corrections",
    ):
        assert restored_records[collection] == source_records[collection]
    assert restored_email.id != source_keys["email_id"]
    assert restored_attachment.id != source_keys["attachment_id"]
    assert restored_node.content_node_id != source_keys["node_id"]
    assert restored_segment.content_segment_id != source_keys["segment_id"]
    assert restored_email.user_id == target_scope.user_id
    assert restored_email.organization_id == target_scope.organization_id
    assert restored_object.project_graph_object_id != source_keys["project_object_id"]
    assert restored_object.user_id == target_scope.user_id
    assert restored_object.organization_id == target_scope.organization_id
    assert restored_object.workspace_id == target_scope.workspace_id
    assert restored_correction.actor_user_id == target_scope.user_id
    assert restored_correction.before_json == {
        "status_code": "candidate",
        "rank_value": 0,
    }
    assert restored_correction.after_json == {
        "status_code": "accepted",
        "rank_value": 1,
    }


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_composes_with_transaction_started_by_prior_select(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"active-source-{token}")
    target_scope = _scope(f"active-target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)

    async with provenance_sessionmaker() as session:
        await session.execute(select(func.count()).select_from(Email))
        assert session.in_transaction()
        receipt = await import_tenant_provenance(session, target_scope, archive)
        assert sum(receipt.created.values()) == 9
        assert await session.scalar(
            select(func.count()).select_from(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.workspace_id == target_scope.workspace_id
            )
        ) == 2


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_active_transaction_import_failure_rolls_back_only_import_savepoint(
    provenance_sessionmaker,
    monkeypatch,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"rollback-source-{token}")
    target_scope = _scope(f"rollback-target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)

    original_insert = provenance_service._insert_records

    async def fail_after_insert(*args, **kwargs):
        await original_insert(*args, **kwargs)
        raise IntegrityError("forced import failure", {}, RuntimeError())

    monkeypatch.setattr(provenance_service, "_insert_records", fail_after_insert)
    async with provenance_sessionmaker() as session:
        baseline_count = await session.scalar(select(func.count()).select_from(Email))
        assert session.in_transaction()
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, archive)
        assert session.in_transaction()
        assert await session.scalar(select(func.count()).select_from(Email)) == baseline_count
        assert await session.scalar(
            select(func.count()).select_from(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.workspace_id == target_scope.workspace_id
            )
        ) == 0


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_same_database_cross_workspace_import_keeps_portable_identity(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = TenantProvenanceScope(
        user_id=source_scope.user_id,
        organization_id=source_scope.organization_id,
        workspace_id=f"target-workspace-{token}",
    )
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
        source_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
            )
        )
        source_correction = await session.scalar(
            select(ProjectGraphCorrectionRecord).where(
                ProjectGraphCorrectionRecord.workspace_id == source_scope.workspace_id
            )
        )
        portable_object_uid = source["object_uids"][0]
        portable_segment_uid = f"segment-{token}"
        source_object.attributes_json = {
            "nested": [
                {
                    "source_object_uid": portable_object_uid,
                    "source_segment_uids": [portable_segment_uid],
                    "plain_text": portable_object_uid,
                }
            ]
        }
        source_correction.before_json = {
            "object_uid": portable_object_uid,
            "source_segment_uid": portable_segment_uid,
        }
        source_correction.after_json = {
            "target_object_uid": portable_object_uid,
            "primary_segment_uid": portable_segment_uid,
        }
        await session.commit()
    async with provenance_sessionmaker() as session:
        source_archive = await export_tenant_provenance(session, source_scope)
    source_records = parse_provenance_archive(source_archive)

    async with provenance_sessionmaker() as session:
        first = await import_tenant_provenance(session, target_scope, source_archive)
    async with provenance_sessionmaker() as session:
        second = await import_tenant_provenance(session, target_scope, source_archive)
    async with provenance_sessionmaker() as session:
        source_after = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
        target_after = parse_provenance_archive(
            await export_tenant_provenance(session, target_scope)
        )
        source_objects = list(
            (
                await session.scalars(
                    select(ProjectGraphObjectRecord).where(
                        ProjectGraphObjectRecord.workspace_id
                        == source_scope.workspace_id
                    )
                )
            ).all()
        )
        target_objects = list(
            (
                await session.scalars(
                    select(ProjectGraphObjectRecord).where(
                        ProjectGraphObjectRecord.workspace_id
                        == target_scope.workspace_id
                    )
                )
            ).all()
        )
        target_edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == target_scope.workspace_id
            )
        )
        target_correction = await session.scalar(
            select(ProjectGraphCorrectionRecord).where(
                ProjectGraphCorrectionRecord.workspace_id == target_scope.workspace_id
            )
        )
        identity_mappings = list(
            (
                await session.scalars(
                    select(ProvenanceIdentityMapping).where(
                        ProvenanceIdentityMapping.target_workspace_id
                        == target_scope.workspace_id
                    )
                )
            ).all()
        )
        target_segment = await session.scalar(
            select(ContentSegmentRecord).where(
                ContentSegmentRecord.content_segment_uid
                == target_edge.source_segment_uids[0]
            )
        )

    assert first.created == {
        "emails": 0,
        "attachments": 0,
        "content_nodes": 1,
        "content_segments": 1,
        "structural_edges": 1,
        "project_objects": 2,
        "project_edges": 1,
        "corrections": 1,
    }
    assert sum(second.created.values()) == 0
    assert second.skipped == {
        collection: len(source_records[collection])
        for collection in (
            "emails",
            "attachments",
            "content_nodes",
            "content_segments",
            "structural_edges",
            "project_objects",
            "project_edges",
            "corrections",
        )
    }
    for collection in (
        "emails",
        "attachments",
        "content_nodes",
        "content_segments",
        "structural_edges",
        "project_objects",
        "project_edges",
        "corrections",
    ):
        assert source_after[collection] == source_records[collection]
        assert target_after[collection] == source_records[collection]
    assert {record.object_uid for record in source_objects} == set(
        source["object_uids"]
    )
    assert {record.object_uid for record in source_objects}.isdisjoint(
        {record.object_uid for record in target_objects}
    )
    target_object_uids = {record.object_uid for record in target_objects}
    assert target_edge.source_uid in target_object_uids
    assert target_edge.target_uid in target_object_uids
    assert target_edge.source_object_id in {
        record.project_graph_object_id for record in target_objects
    }
    assert target_edge.target_object_id in {
        record.project_graph_object_id for record in target_objects
    }
    assert target_correction.project_graph_object_id in {
        record.project_graph_object_id for record in target_objects
    }
    assert all(
        record.primary_content_segment_id == target_edge.primary_content_segment_id
        for record in target_objects
    )
    assert len(identity_mappings) == 7
    assert {row.entity_kind for row in identity_mappings} == {
        "content_nodes",
        "content_segments",
        "structural_edges",
        "project_objects",
        "project_edges",
        "corrections",
    }
    assert all(
        record.source_segment_uids == [target_edge.source_segment_uids[0]]
        for record in target_objects
    )
    assert target_correction.source_segment_uids == target_edge.source_segment_uids
    target_object = next(
        record
        for record in target_objects
        if record.object_uid == target_edge.source_uid
    )
    nested_metadata = target_object.attributes_json["nested"][0]
    assert nested_metadata["source_object_uid"] == target_object.object_uid
    assert nested_metadata["source_segment_uids"] == [
        target_segment.content_segment_uid
    ]
    assert nested_metadata["plain_text"] == portable_object_uid
    assert target_correction.before_json == {
        "object_uid": target_object.object_uid,
        "source_segment_uid": target_segment.content_segment_uid,
    }
    assert target_correction.after_json == {
        "target_object_uid": target_object.object_uid,
        "primary_segment_uid": target_segment.content_segment_uid,
    }


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_mixed_native_and_multiple_import_origins_export_as_target_scope(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    target_scope = _scope(f"target-{token}")
    source_scopes = [_scope(f"source-{index}-{token}") for index in range(2)]
    async with provenance_sessionmaker() as session:
        native = await _seed_provenance_closure(
            session, scope=target_scope, token=f"native-{token}"
        )
        native_node = await session.get(ContentNodeRecord, native["node_id"])
        parent_uid = f"parent-node-native-{token}"
        session.add(
            ContentNodeRecord(
                content_node_uid=parent_uid,
                email_id=native["email_id"],
                attachment_id=native["attachment_id"],
                source_kind="attachment",
                source_record_uid=f"attachment-source-native-{token}",
                parent_node_uid=None,
                node_kind="document",
                node_path="/",
                ordinal_index=0,
                display_label="Parent",
                safe_text_content="Parent evidence",
                content_hash=f"parenthash-{token}",
            )
        )
        native_node.parent_node_uid = parent_uid
        await session.commit()
        sources = [
            await _seed_provenance_closure(
                session, scope=scope, token=f"source-{index}-{token}"
            )
            for index, scope in enumerate(source_scopes)
        ]
    archives = []
    async with provenance_sessionmaker() as session:
        for scope in source_scopes:
            archives.append(await export_tenant_provenance(session, scope))
    for archive in archives:
        async with provenance_sessionmaker() as session:
            await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, target_scope)
        )

    assert records["source_scope"] == {
        "user_uid": hashlib.sha256(target_scope.user_id.encode()).hexdigest(),
        "organization_uid": target_scope.organization_id,
        "workspace_uid": target_scope.workspace_id,
    }
    assert {
        collection: len(records[collection])
        for collection in (
            "emails",
            "attachments",
            "content_nodes",
            "content_segments",
            "structural_edges",
            "project_objects",
            "project_edges",
            "corrections",
        )
    } == {
        "emails": 3,
        "attachments": 3,
        "content_nodes": 4,
        "content_segments": 3,
        "structural_edges": 3,
        "project_objects": 6,
        "project_edges": 3,
        "corrections": 3,
    }
    serialized = json.dumps(records, sort_keys=True)
    assert native["email_uid"] in serialized
    assert parent_uid in serialized
    assert all(source["email_uid"] in serialized for source in sources)


@pytest.mark.parametrize(
    "source_user_uid",
    ("a" * 63, "A" * 64, "g" * 64, "0" * 65),
)
@pytest.mark.asyncio
async def test_import_rejects_invalid_source_user_uid_before_transaction(
    source_user_uid,
):
    records = copy.deepcopy(RECORDS)
    records["source_scope"]["user_uid"] = source_user_uid
    archive = build_provenance_archive(records)
    flush_count = 0

    class NoTransactionSession:
        def begin(self):
            raise AssertionError("transaction must not start")

        async def flush(self):
            nonlocal flush_count
            flush_count += 1

    with pytest.raises(ProvenanceArchiveError):
        await import_tenant_provenance(
            NoTransactionSession(),
            TenantProvenanceScope("target-user", "target-org", "target-workspace"),
            archive,
        )
    assert flush_count == 0


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_concurrent_identical_same_database_imports_are_idempotent():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"concurrent-source-{token}")
    target_scope = TenantProvenanceScope(
        user_id=source_scope.user_id,
        organization_id=source_scope.organization_id,
        workspace_id=f"concurrent-target-{token}",
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            await _seed_provenance_closure(session, scope=source_scope, token=token)
        async with session_factory() as session:
            archive = await export_tenant_provenance(session, source_scope)

        async def run_import():
            async with session_factory() as session:
                return await import_tenant_provenance(session, target_scope, archive)

        first, second = await asyncio.gather(run_import(), run_import())
        created_totals = sorted(
            (sum(first.created.values()), sum(second.created.values()))
        )
        assert created_totals == [0, 7]
        assert sorted((sum(first.skipped.values()), sum(second.skipped.values()))) == [
            2,
            9,
        ]
    finally:
        async with session_factory.begin() as session:
            email = await session.scalar(
                select(Email).where(Email.message_id == f"<{token}@example.com>")
            )
            if email is not None:
                await session.execute(
                    delete(ProjectGraphCorrectionRecord).where(
                        ProjectGraphCorrectionRecord.workspace_id.in_(
                            [source_scope.workspace_id, target_scope.workspace_id]
                        )
                    )
                )
                await session.execute(
                    delete(ProjectGraphEdgeRecord).where(
                        ProjectGraphEdgeRecord.workspace_id.in_(
                            [source_scope.workspace_id, target_scope.workspace_id]
                        )
                    )
                )
                await session.execute(
                    delete(ProjectGraphObjectRecord).where(
                        ProjectGraphObjectRecord.workspace_id.in_(
                            [source_scope.workspace_id, target_scope.workspace_id]
                        )
                    )
                )
                await session.execute(
                    delete(ProvenanceIdentityMapping).where(
                        ProvenanceIdentityMapping.target_workspace_id
                        == target_scope.workspace_id
                    )
                )
                await session.execute(
                    delete(KnowledgeGraphEdgeRecord).where(
                        KnowledgeGraphEdgeRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(ContentSegmentRecord).where(
                        ContentSegmentRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(ContentNodeRecord).where(
                        ContentNodeRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(Attachment).where(Attachment.email_id == email.id)
                )
                await session.delete(email)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_concurrent_imports_across_workspaces_reuse_owner_email():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"parallel-workspaces-source-{token}")
    target_user_id = f"parallel-target-user-{token}"
    target_organization_id = f"parallel-target-org-{token}"
    target_scopes = tuple(
        TenantProvenanceScope(
            user_id=target_user_id,
            organization_id=target_organization_id,
            workspace_id=f"parallel-workspace-{index}-{token}",
        )
        for index in range(2)
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            archive = await _two_email_rooted_archive(
                session, scope=source_scope, token=token
            )
        first_records = parse_provenance_archive(archive)
        second_records = copy.deepcopy(first_records)
        shared_email_uid, distinct_email_uid = sorted(
            record["email_uid"] for record in first_records["emails"]
        )
        replacement_email_uid = f"<partial-distinct-{token}@example.com>"

        def replace_email_uid(value):
            if isinstance(value, dict):
                return {key: replace_email_uid(item) for key, item in value.items()}
            if isinstance(value, list):
                return [replace_email_uid(item) for item in value]
            return replacement_email_uid if value == distinct_email_uid else value

        second_records = replace_email_uid(second_records)
        attachment_uid_replacements = {}
        for attachment in second_records["attachments"]:
            if attachment["email_uid"] != replacement_email_uid:
                continue
            canonical = provenance_service._attachment_payload_core(attachment)
            attachment_uid_replacements[attachment["attachment_uid"]] = (
                provenance_service._attachment_uid(canonical, 1)
            )

        def replace_attachment_uid(value):
            if isinstance(value, dict):
                return {
                    key: replace_attachment_uid(item) for key, item in value.items()
                }
            if isinstance(value, list):
                return [replace_attachment_uid(item) for item in value]
            if isinstance(value, str) and value.startswith("attachment:"):
                attachment_uid = value.removeprefix("attachment:")
                return "attachment:" + attachment_uid_replacements.get(
                    attachment_uid, attachment_uid
                )
            return attachment_uid_replacements.get(value, value)

        second_records = replace_attachment_uid(second_records)
        uid_keys = {
            "emails": "email_uid",
            "attachments": "attachment_uid",
            **provenance_service._UID_KEYS,
        }
        for collection, uid_key in uid_keys.items():
            second_records[collection].sort(key=lambda record: record[uid_key])
        second_archive = build_provenance_archive(second_records)

        async def run_import(target_scope, target_archive):
            async with session_factory() as session:
                return await import_tenant_provenance(
                    session, target_scope, target_archive
                )

        receipts = await asyncio.gather(
            run_import(target_scopes[0], archive),
            run_import(target_scopes[1], second_archive),
        )
        assert all(sum(receipt.created.values()) > 0 for receipt in receipts)
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(Email)
                    .where(
                        Email.user_id == target_user_id,
                        Email.organization_id == target_organization_id,
                        Email.message_id == shared_email_uid,
                    )
                )
                == 1
            )
    finally:
        async with session_factory.begin() as session:
            workspace_ids = [
                source_scope.workspace_id,
                *(scope.workspace_id for scope in target_scopes),
            ]
            await session.execute(
                delete(ProjectGraphCorrectionRecord).where(
                    ProjectGraphCorrectionRecord.workspace_id.in_(workspace_ids)
                )
            )
            await session.execute(
                delete(ProjectGraphEdgeRecord).where(
                    ProjectGraphEdgeRecord.workspace_id.in_(workspace_ids)
                )
            )
            await session.execute(
                delete(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.workspace_id.in_(workspace_ids)
                )
            )
            await session.execute(
                delete(ProvenanceIdentityMapping).where(
                    ProvenanceIdentityMapping.target_workspace_id.in_(workspace_ids)
                )
            )
            emails = list(
                (
                    await session.scalars(
                        select(Email).where(
                            Email.user_id.in_([source_scope.user_id, target_user_id])
                        )
                    )
                ).all()
            )
            for email in emails:
                await session.execute(
                    delete(KnowledgeGraphEdgeRecord).where(
                        KnowledgeGraphEdgeRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(ContentSegmentRecord).where(
                        ContentSegmentRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(ContentNodeRecord).where(
                        ContentNodeRecord.email_id == email.id
                    )
                )
                await session.execute(
                    delete(Attachment).where(Attachment.email_id == email.id)
                )
                await session.delete(email)
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_final_migration_upgrade_is_safe_after_fresh_metadata_bootstrap(
    provenance_sessionmaker,
):
    revision_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0018_provenance_identity_mappings.py"
    )
    spec = importlib.util.spec_from_file_location(
        "provenance_identity_revision", revision_path
    )
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    original_op = revision.op

    def run_upgrade(sync_connection):
        revision.op = Operations(MigrationContext.configure(sync_connection))
        revision.upgrade()
        revision.upgrade()
        assert sync_connection.dialect.has_table(
            sync_connection, "provenance_identity_mappings"
        )

    try:
        async with provenance_sessionmaker() as session:
            connection = await session.connection()
            await connection.run_sync(run_upgrade)
    finally:
        revision.op = original_op


@pytest.mark.parametrize(
    ("model", "value"),
    (
        (ProjectGraphObjectRecord, -0.01),
        (ProjectGraphObjectRecord, 1.01),
        (ProjectGraphEdgeRecord, -0.01),
        (ProjectGraphEdgeRecord, 1.01),
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_rejects_confidence_outside_unit_interval(
    provenance_sessionmaker,
    model,
    value,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(f"confidence-export-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=scope, token=token)
        record = await session.scalar(
            select(model).where(model.workspace_id == scope.workspace_id)
        )
        record.confidence = value
        await session.commit()

    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await export_tenant_provenance(session, scope)


@pytest.mark.parametrize(
    ("collection", "value"),
    (
        ("project_objects", "-0.01"),
        ("project_objects", "1.01"),
        ("project_edges", "-0.01"),
        ("project_edges", "1.01"),
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_rejects_confidence_outside_unit_interval_before_flush(
    provenance_sessionmaker,
    monkeypatch,
    collection,
    value,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"confidence-source-{token}")
    target_scope = _scope(f"confidence-target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    records[collection][0]["confidence"] = value
    invalid_archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)

    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, invalid_archive)
        assert flush_count == 0


@pytest.mark.parametrize(
    ("collection", "timestamp_field"),
    (("emails", "date"), ("corrections", "created_at")),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_rejects_equivalent_offset_timestamps_before_flush_on_retry(
    provenance_sessionmaker,
    monkeypatch,
    collection,
    timestamp_field,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"timestamp-source-{token}")
    target_scope = _scope(f"timestamp-target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    valid_archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, valid_archive)

    offset_records = copy.deepcopy(records)
    utc_timestamp = datetime.datetime.fromisoformat(
        offset_records[collection][0][timestamp_field]
    )
    offset_records[collection][0][timestamp_field] = utc_timestamp.astimezone(
        datetime.timezone(datetime.timedelta(hours=9))
    ).isoformat()
    offset_archive = build_provenance_archive(offset_records)

    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        for _ in range(2):
            with pytest.raises(ProvenanceArchiveError):
                await import_tenant_provenance(
                    session,
                    target_scope,
                    offset_archive,
                )
        assert flush_count == 0


@pytest.mark.parametrize(
    "reference_field",
    (
        "object_source",
        "object_primary",
        "edge_source",
        "edge_primary",
        "correction_source",
        "edge_without_object_anchors",
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_rejects_cross_email_project_references_before_flush(
    provenance_sessionmaker,
    monkeypatch,
    reference_field,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"citation-source-{token}")
    target_scope = _scope(f"citation-target-{token}")
    async with provenance_sessionmaker() as session:
        archive = await _two_email_rooted_archive(
            session,
            scope=source_scope,
            token=token,
        )
    records = parse_provenance_archive(archive)
    object_email = {
        record["object_uid"]: record["email_uid"]
        for record in records["project_objects"]
    }
    segment_email = {
        record["content_segment_uid"]: record["email_uid"]
        for record in records["content_segments"]
    }
    if reference_field.startswith("object_"):
        record = records["project_objects"][0]
        anchor_email_uid = record["email_uid"]
    elif reference_field.startswith("edge_"):
        record = records["project_edges"][0]
        anchor_email_uid = object_email[
            record["source_object_uid"] or record["target_object_uid"]
        ]
    else:
        record = records["corrections"][0]
        anchor_email_uid = object_email[record["object_uid"]]
    foreign_segment_uid = next(
        segment_uid
        for segment_uid, email_uid in segment_email.items()
        if email_uid != anchor_email_uid
    )
    if reference_field == "edge_without_object_anchors":
        record["source_object_uid"] = None
        record["target_object_uid"] = None
    elif reference_field.endswith("_primary"):
        record["primary_content_segment_uid"] = foreign_segment_uid
    else:
        record["source_segment_uids"] = [foreign_segment_uid]
    invalid_archive = build_provenance_archive(records)

    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, invalid_archive)
        assert flush_count == 0


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_round_trip_remaps_nullable_segment_evidence_endpoint(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"nullable-source-{token}")
    target_scope = TenantProvenanceScope(
        user_id=source_scope.user_id,
        organization_id=source_scope.organization_id,
        workspace_id=f"nullable-target-workspace-{token}",
    )
    portable_segment_uid = f"segment-{token}"
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
        source_edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == source_scope.workspace_id
            )
        )
        source_edge.source_object_id = None
        source_edge.source_uid = f"segment:{portable_segment_uid}"
        await session.commit()
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)

    async with provenance_sessionmaker() as session:
        receipt = await import_tenant_provenance(
            session,
            target_scope,
            archive,
        )
        target_edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == target_scope.workspace_id
            )
        )
        segment_mapping = await session.scalar(
            select(ProvenanceIdentityMapping).where(
                ProvenanceIdentityMapping.target_workspace_id
                == target_scope.workspace_id,
                ProvenanceIdentityMapping.entity_kind == "content_segments",
                ProvenanceIdentityMapping.portable_uid == portable_segment_uid,
            )
        )
        target_source_uid = target_edge.source_uid
        target_source_object_id = target_edge.source_object_id
    async with provenance_sessionmaker() as session:
        reexported = parse_provenance_archive(
            await export_tenant_provenance(session, target_scope)
        )

    assert receipt.created["project_edges"] == 1
    assert target_source_object_id is None
    assert target_source_uid == f"segment:{segment_mapping.target_database_uid}"
    assert reexported["project_edges"][0]["source_object_uid"] is None
    assert reexported["project_edges"][0]["source_uid"] == (
        f"segment:{portable_segment_uid}"
    )


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_confidence_unit_interval_boundaries_round_trip(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"confidence-source-{token}")
    target_scope = _scope(f"confidence-target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
        project_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.workspace_id == source_scope.workspace_id
            )
        )
        project_edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == source_scope.workspace_id
            )
        )
        project_object.confidence = 0.0
        project_edge.confidence = 1.0
        await session.commit()
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    records = parse_provenance_archive(archive)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, archive)
        restored_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.workspace_id == target_scope.workspace_id,
                ProjectGraphObjectRecord.confidence == 0.0,
            )
        )
        restored_edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == target_scope.workspace_id
            )
        )

    assert restored_object is not None
    assert restored_edge.confidence == 1.0


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_is_exact_workspace_scoped(provenance_sessionmaker):
    token = uuid.uuid4().hex[:12]
    shared_scope = _scope(f"shared-{token}")
    other_scope = TenantProvenanceScope(
        user_id=shared_scope.user_id,
        organization_id=shared_scope.organization_id,
        workspace_id=f"other-workspace-{token}",
    )
    async with provenance_sessionmaker() as session:
        expected = await _seed_provenance_closure(
            session, scope=shared_scope, token=f"selected-{token}"
        )
        excluded = await _seed_provenance_closure(
            session, scope=other_scope, token=f"excluded-{token}"
        )
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, shared_scope)
        )

    assert [record["email_uid"] for record in records["emails"]] == [
        expected["email_uid"]
    ]
    assert excluded["email_uid"] not in json.dumps(records)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_dangling_reference_rolls_back_without_mutation(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        source_archive = await export_tenant_provenance(session, source_scope)
    records = copy.deepcopy(parse_provenance_archive(source_archive))
    records["project_objects"][0]["source_segment_uids"] = ["missing-segment"]
    invalid_archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, invalid_archive)
    async with provenance_sessionmaker() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Email)
                .where(
                    *Email.owner_filters(
                        target_scope.user_id, target_scope.organization_id
                    )
                )
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_late_conflict_fails_before_creating_email(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    records = parse_provenance_archive(archive)
    imported_email_uid = records["emails"][0]["email_uid"]
    conflict_uid = records["project_objects"][0]["object_uid"]
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
        target_seed = await _seed_provenance_closure(
            session, scope=target_scope, token=f"conflict-{token}"
        )
        existing = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == target_seed["object_uids"][0]
            )
        )
        existing.object_uid = conflict_uid
        existing.title = "Conflicting target record"
        await session.commit()

    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Email)
                .where(Email.message_id == imported_email_uid)
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_admits_only_parser_confirmed_text_and_omits_sensitive_fields(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(token)
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=scope, token=token)
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, scope)
    records = parse_provenance_archive(archive)
    serialized = json.dumps(records, sort_keys=True)

    assert [record["filename"] for record in records["attachments"]] == ["evidence.txt"]
    assert "binary-payload-must-not-export" not in serialized
    for forbidden in (
        "embedding",
        "credential",
        "secret",
        "api_key",
        "provider_url",
        "token",
        "email_id",
        "attachment_id",
        "content_node_id",
        "content_segment_id",
        "project_graph_object_id",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_is_idempotent_for_exact_target_records(provenance_sessionmaker):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    records = parse_provenance_archive(archive)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        first = await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        second = await import_tenant_provenance(session, target_scope, archive)

    assert sum(first.created.values()) == 9
    assert sum(first.skipped.values()) == 0
    assert sum(second.created.values()) == 0
    assert second.skipped == first.created


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_cross_workspace_retry_uses_mappings_after_source_graph_deletion(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"deleted-source-{token}")
    target_scope = TenantProvenanceScope(
        user_id=source_scope.user_id,
        organization_id=source_scope.organization_id,
        workspace_id=f"retained-target-{token}",
    )
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    async with provenance_sessionmaker() as session:
        first = await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        await session.execute(
            delete(ProjectGraphCorrectionRecord).where(
                ProjectGraphCorrectionRecord.workspace_id == source_scope.workspace_id
            )
        )
        await session.execute(
            delete(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == source_scope.workspace_id
            )
        )
        await session.execute(
            delete(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.workspace_id == source_scope.workspace_id
            )
        )
        await session.commit()
    async with provenance_sessionmaker() as session:
        second = await import_tenant_provenance(session, target_scope, archive)
        target_counts = (
            await session.scalar(
                select(func.count()).select_from(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.workspace_id == target_scope.workspace_id
                )
            ),
            await session.scalar(
                select(func.count()).select_from(ProjectGraphEdgeRecord).where(
                    ProjectGraphEdgeRecord.workspace_id == target_scope.workspace_id
                )
            ),
            await session.scalar(
                select(func.count()).select_from(ProjectGraphCorrectionRecord).where(
                    ProjectGraphCorrectionRecord.workspace_id == target_scope.workspace_id
                )
            ),
        )

    assert sum(first.created.values()) > 0
    assert sum(second.created.values()) == 0
    assert sum(second.skipped.values()) == sum(first.created.values()) + sum(
        first.skipped.values()
    )
    assert target_counts == (2, 1, 1)


@pytest.mark.parametrize("citation_owner", ("object", "edge", "correction"))
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_rejects_cross_email_citation_source_closure(
    provenance_sessionmaker,
    citation_owner,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(f"source-{token}")
    cited_scope = TenantProvenanceScope(
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=f"cited-workspace-{token}",
    )
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(session, scope=scope, token=token)
        await _seed_provenance_closure(
            session,
            scope=cited_scope,
            token=f"cited-{token}",
        )
        cited_segment_uid = f"segment-cited-{token}"
        if citation_owner == "object":
            record = await session.scalar(
                select(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
                )
            )
        elif citation_owner == "edge":
            record = await session.scalar(
                select(ProjectGraphEdgeRecord).where(
                    ProjectGraphEdgeRecord.edge_uid == f"project-edge-{token}"
                )
            )
        else:
            record = await session.scalar(
                select(ProjectGraphCorrectionRecord).where(
                    ProjectGraphCorrectionRecord.correction_uid == f"correction-{token}"
                )
            )
        record.source_segment_uids = sorted(
            [*record.source_segment_uids, cited_segment_uid]
        )
        await session.commit()
    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await export_tenant_provenance(session, scope)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_duplicate_canonical_attachments_keep_node_and_segment_identity(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
        await _add_duplicate_text_attachments(
            session,
            email_uid=source["email_uid"],
            token=token,
        )
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    source_records = parse_provenance_archive(archive)
    source_node_attachments = {
        record["content_node_uid"]: record["attachment_uid"]
        for record in source_records["content_nodes"]
        if record["content_node_uid"].startswith("duplicate-node-")
    }
    source_segment_attachments = {
        record["content_segment_uid"]: record["attachment_uid"]
        for record in source_records["content_segments"]
        if record["content_segment_uid"].startswith("duplicate-segment-")
    }
    assert len(source_node_attachments) == 5
    assert len(set(source_node_attachments.values())) == 5
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, source_records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        restored = parse_provenance_archive(
            await export_tenant_provenance(session, target_scope)
        )

    assert {
        record["content_node_uid"]: record["attachment_uid"]
        for record in restored["content_nodes"]
        if record["content_node_uid"].startswith("duplicate-node-")
    } == source_node_attachments
    assert {
        record["content_segment_uid"]: record["attachment_uid"]
        for record in restored["content_segments"]
        if record["content_segment_uid"].startswith("duplicate-segment-")
    } == source_segment_attachments


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_recognized_pdf_omits_integer_keys_and_round_trips_graph_references(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
        attachment = await session.get(Attachment, source["attachment_id"])
        attachment.content = "Recognized PDF evidence"
        attachment.content_type = "application/pdf"
        attachment.parse_status = "parsed"
        attachment.parse_content_type = "application/pdf"
        attachment.parser_key = "pdf"
        legacy_source_uid = f"attachment-{attachment.id}"
        node = await session.scalar(
            select(ContentNodeRecord).where(
                ContentNodeRecord.content_node_uid == f"node-{token}"
            )
        )
        segment = await session.scalar(
            select(ContentSegmentRecord).where(
                ContentSegmentRecord.content_segment_uid == f"segment-{token}"
            )
        )
        structural_edge = await session.scalar(
            select(KnowledgeGraphEdgeRecord).where(
                KnowledgeGraphEdgeRecord.edge_uid == f"structural-edge-{token}"
            )
        )
        project_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
            )
        )
        node.source_record_uid = legacy_source_uid
        segment.source_record_uid = legacy_source_uid
        structural_edge.source_record_uid = legacy_source_uid
        project_object.attributes_json = {
            "source_record_uid": legacy_source_uid,
            "source_object_uid": project_object.object_uid,
            "nested": {
                "attachment_uid": legacy_source_uid,
                "free_text": legacy_source_uid,
            },
        }
        await session.commit()
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    records = parse_provenance_archive(archive)
    attachment_uid = records["attachments"][0]["attachment_uid"]
    portable_source_uid = f"attachment:{attachment_uid}"
    serialized = json.dumps(records, sort_keys=True)

    assert serialized.count(legacy_source_uid) == 1
    assert {
        records["content_nodes"][0]["source_record_uid"],
        records["content_segments"][0]["source_record_uid"],
        records["structural_edges"][0]["source_record_uid"],
    } == {portable_source_uid}
    assert (
        records["project_objects"][0]["attributes_json"]["source_record_uid"]
        == portable_source_uid
    )
    assert records["project_objects"][0]["attributes_json"]["nested"] == {
        "attachment_uid": portable_source_uid,
        "free_text": legacy_source_uid,
    }

    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        restored = parse_provenance_archive(
            await export_tenant_provenance(session, target_scope)
        )
        restored_node = await session.scalar(
            select(ContentNodeRecord).where(
                ContentNodeRecord.content_node_uid == f"node-{token}"
            )
        )

    assert restored_node.source_record_uid == portable_source_uid
    assert restored["content_nodes"][0]["attachment_uid"] == attachment_uid
    assert restored["content_nodes"][0]["source_record_uid"] == portable_source_uid
    assert restored["project_objects"][0]["attributes_json"]["nested"] == {
        "attachment_uid": portable_source_uid,
        "free_text": legacy_source_uid,
    }


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_production_correction_float_round_trip(provenance_sessionmaker):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
        correction = await ProjectGraphRepository(session).apply_correction(
            object_uid=source["object_uids"][0],
            user_id=source_scope.user_id,
            organization_id=source_scope.organization_id,
            workspace_id=source_scope.workspace_id,
            actor_user_id=source_scope.user_id,
            correction_action="adjust_confidence",
            after_json={"confidence": 0.73},
            rationale="Production correction path",
        )
        correction_uid = correction.correction_uid
        await session.commit()
    async with provenance_sessionmaker() as session:
        archive = await export_tenant_provenance(session, source_scope)
    records = parse_provenance_archive(archive)
    correction_record = next(
        record
        for record in records["corrections"]
        if record["correction_uid"] == correction_uid
    )

    assert correction_record["before_json"]["confidence"] == 0.91
    assert correction_record["after_json"]["confidence"] == 0.73
    assert isinstance(correction_record["before_json"]["confidence"], float)
    assert isinstance(correction_record["after_json"]["confidence"], float)

    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        restored = await session.scalar(
            select(ProjectGraphCorrectionRecord).where(
                ProjectGraphCorrectionRecord.correction_uid == correction_uid
            )
        )

    assert restored.before_json["confidence"] == 0.91
    assert restored.after_json["confidence"] == 0.73
    assert isinstance(restored.before_json["confidence"], float)
    assert isinstance(restored.after_json["confidence"], float)


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    (
        ("api_key", "key-material"),
        ("provider_url", "https://provider.example/v1"),
        ("access_token", "token-material"),
        ("email_id", 123),
        ("smtp_password", "password-material"),
        ("backup_api_key", "key-material"),
        ("provider_auth_token", "token-material"),
        ("mail_credentials_blob", "credential-material"),
        ("backup_provider_endpoint_url", "https://provider.example/v1"),
        ("legacy_attachment_id", 123),
        ("smtpPassword", "password-material"),
        ("backupApiKey", "key-material"),
        ("providerAuthToken", "token-material"),
        ("provider.endpoint.url", "https://provider.example/v1"),
        ("legacyAttachmentId", 123),
        ("smtp/password", "password-material"),
        ("APIKey", "key-material"),
        ("OAuthToken", "token-material"),
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_rejects_nested_sensitive_metadata(
    provenance_sessionmaker,
    forbidden_key,
    forbidden_value,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(token)
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(session, scope=scope, token=token)
        project_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
            )
        )
        project_object.attributes_json = {
            "source_object_uid": project_object.object_uid,
            "source_segment_uids": [f"segment-{token}"],
            "nested_metadata": {forbidden_key: forbidden_value},
        }
        await session.commit()
    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await export_tenant_provenance(session, scope)


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    (
        ("client_secret", "secret-material"),
        ("provider_endpoint", "https://provider.example/v1"),
        ("refresh_token", "token-material"),
        ("attachment_id", 456),
        ("smtp_password", "password-material"),
        ("backup_api_key", "key-material"),
        ("provider_auth_token", "token-material"),
        ("mail_credentials_blob", "credential-material"),
        ("backup_provider_endpoint_url", "https://provider.example/v1"),
        ("legacy_attachment_id", 456),
        ("smtpPassword", "password-material"),
        ("backupApiKey", "key-material"),
        ("providerAuthToken", "token-material"),
        ("provider.endpoint.url", "https://provider.example/v1"),
        ("legacyAttachmentId", 456),
        ("smtp/password", "password-material"),
        ("APIKey", "key-material"),
        ("OAuthToken", "token-material"),
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_import_rejects_nested_sensitive_metadata_before_flush(
    provenance_sessionmaker,
    monkeypatch,
    forbidden_key,
    forbidden_value,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    records["corrections"][0]["after_json"] = {
        "confidence": 1,
        "source_object_uid": records["corrections"][0]["object_uid"],
        "nested_metadata": {forbidden_key: forbidden_value},
    }
    archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, archive)
        assert flush_count == 0


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_nested_benign_metadata_and_stable_uids_round_trip(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    allowed_metadata = {
        "confidence": 0.73,
        "source_object_uid": f"project-object-source-{token}",
        "source_segment_uids": [f"segment-{token}"],
        "tokenization_strategy": "bounded",
        "passwordless_mode": "enabled",
        "credentialed_source": "oidc",
        "secretary_note": "benign domain text",
        "identifier_kind": "stable",
    }
    async with provenance_sessionmaker() as session:
        source = await _seed_provenance_closure(
            session, scope=source_scope, token=token
        )
        project_object = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
            )
        )
        project_object.attributes_json = allowed_metadata
        await session.commit()
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        await import_tenant_provenance(session, target_scope, archive)
    async with provenance_sessionmaker() as session:
        restored = await session.scalar(
            select(ProjectGraphObjectRecord).where(
                ProjectGraphObjectRecord.object_uid == source["object_uids"][0]
            )
        )

    assert restored.attributes_json == allowed_metadata


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_unrooted_email_rejected_without_mutation_and_empty_allowed(
    provenance_sessionmaker,
    monkeypatch,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        rooted = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    unrooted = copy.deepcopy(rooted)
    unrooted["project_objects"] = []
    unrooted["project_edges"] = []
    unrooted["corrections"] = []
    unrooted_archive = build_provenance_archive(unrooted)
    empty = copy.deepcopy(rooted)
    for collection in (
        "emails",
        "attachments",
        "content_nodes",
        "content_segments",
        "structural_edges",
        "project_objects",
        "project_edges",
        "corrections",
    ):
        empty[collection] = []
    empty_archive = build_provenance_archive(empty)

    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, rooted)

    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, unrooted_archive)
        assert flush_count == 0
    async with provenance_sessionmaker() as session:
        receipt = await import_tenant_provenance(session, target_scope, empty_archive)

    assert sum(receipt.created.values()) == 0
    assert sum(receipt.skipped.values()) == 0


@pytest.mark.parametrize(
    "conflict_kind",
    (
        "structural_attachment_email",
        "object_attachment_email",
        "object_attachment_primary",
        "edge_source_endpoint",
        "edge_target_endpoint",
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_cross_field_conflict_rejected_before_flush(
    provenance_sessionmaker,
    monkeypatch,
    conflict_kind,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        archive = await _two_email_rooted_archive(
            session, scope=source_scope, token=token
        )
    records = parse_provenance_archive(archive)
    source_email_uid = f"<{token}@example.com>"
    foreign_attachment_uid = next(
        record["attachment_uid"]
        for record in records["attachments"]
        if record["email_uid"] != source_email_uid
    )
    same_email_attachment_uid = next(
        record["attachment_uid"]
        for record in records["attachments"]
        if record["email_uid"] == source_email_uid
        and record["attachment_uid"] != records["project_objects"][0]["attachment_uid"]
    )
    if conflict_kind == "structural_attachment_email":
        source_structural_edge = next(
            record
            for record in records["structural_edges"]
            if record["email_uid"] == source_email_uid
        )
        source_structural_edge["attachment_uid"] = foreign_attachment_uid
    elif conflict_kind == "object_attachment_email":
        records["project_objects"][0]["attachment_uid"] = foreign_attachment_uid
    elif conflict_kind == "object_attachment_primary":
        records["project_objects"][0]["attachment_uid"] = same_email_attachment_uid
    elif conflict_kind == "edge_source_endpoint":
        records["project_edges"][0]["source_uid"] = "mismatched-logical-endpoint"
    else:
        records["project_edges"][0]["target_uid"] = "mismatched-logical-endpoint"
    invalid_archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, invalid_archive)
        assert flush_count == 0


@pytest.mark.parametrize("bound_kind", ("node_uid", "object_title", "edge_source"))
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_column_bound_preflight_rejects_before_flush(
    provenance_sessionmaker,
    monkeypatch,
    bound_kind,
):
    token = uuid.uuid4().hex[:12]
    source_scope = _scope(f"source-{token}")
    target_scope = _scope(f"target-{token}")
    async with provenance_sessionmaker() as session:
        await _seed_provenance_closure(session, scope=source_scope, token=token)
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, source_scope)
        )
    if bound_kind == "node_uid":
        old_node_uid = records["content_nodes"][0]["content_node_uid"]
        oversized_node_uid = "n" * 65
        records["content_nodes"][0]["content_node_uid"] = oversized_node_uid
        for segment in records["content_segments"]:
            if segment["content_node_uid"] == old_node_uid:
                segment["content_node_uid"] = oversized_node_uid
        for edge in records["structural_edges"]:
            if edge["source_node_uid"] == old_node_uid:
                edge["source_node_uid"] = oversized_node_uid
            if edge["target_node_uid"] == old_node_uid:
                edge["target_node_uid"] = oversized_node_uid
    elif bound_kind == "object_title":
        records["project_objects"][0]["title"] = "t" * 241
    else:
        records["project_edges"][0]["source_uid"] = "s" * 161
    invalid_archive = build_provenance_archive(records)
    async with provenance_sessionmaker() as session:
        await _delete_exported_closure(session, records)
    async with provenance_sessionmaker() as session:
        flush_count = 0
        original_flush = session.flush

        async def counting_flush(*args, **kwargs):
            nonlocal flush_count
            flush_count += 1
            return await original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", counting_flush)
        with pytest.raises(ProvenanceArchiveError):
            await import_tenant_provenance(session, target_scope, invalid_archive)
        assert flush_count == 0


@pytest.mark.parametrize("scope_dimension", ("user", "organization"))
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_excludes_separate_user_and_organization_scope(
    provenance_sessionmaker,
    scope_dimension,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(f"selected-{token}")
    rival_scope = TenantProvenanceScope(
        user_id=f"rival-user-{token}" if scope_dimension == "user" else scope.user_id,
        organization_id=(
            f"rival-org-{token}"
            if scope_dimension == "organization"
            else scope.organization_id
        ),
        workspace_id=scope.workspace_id,
    )
    async with provenance_sessionmaker() as session:
        selected = await _seed_provenance_closure(
            session, scope=scope, token=f"selected-{token}"
        )
        rival = await _seed_provenance_closure(
            session, scope=rival_scope, token=f"rival-{token}"
        )
    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, scope)
        )

    assert {record["email_uid"] for record in records["emails"]} == {
        selected["email_uid"]
    }
    assert rival["email_uid"] not in json.dumps(records)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_allows_segment_evidence_edge_with_nullable_source_object(
    provenance_sessionmaker,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(f"segment-edge-{token}")
    async with provenance_sessionmaker() as session:
        selected = await _seed_provenance_closure(session, scope=scope, token=token)
        edge = await session.scalar(
            select(ProjectGraphEdgeRecord).where(
                ProjectGraphEdgeRecord.workspace_id == scope.workspace_id
            )
        )
        edge.source_uid = f"segment-{token}"
        edge.source_object_id = None
        await session.commit()

    async with provenance_sessionmaker() as session:
        records = parse_provenance_archive(
            await export_tenant_provenance(session, scope)
        )

    exported_edge = records["project_edges"][0]
    assert exported_edge["source_uid"] == f"segment-{token}"
    assert exported_edge["source_object_uid"] is None
    assert exported_edge["target_object_uid"] in selected["object_uids"]


@pytest.mark.parametrize(
    "reference_field",
    (
        "object_source",
        "object_primary",
        "edge_source",
        "edge_primary",
        "correction_source",
        "edge_source_object",
        "edge_target_object",
        "correction_object",
        "edge_without_object_anchors",
    ),
)
@pytest.mark.asyncio
@pytest.mark.postgres
async def test_export_rejects_cross_workspace_segment_references_before_email_closure(
    provenance_sessionmaker,
    reference_field,
):
    token = uuid.uuid4().hex[:12]
    scope = _scope(f"selected-{token}")
    foreign_scope = TenantProvenanceScope(
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=f"workspace-foreign-{token}",
    )
    async with provenance_sessionmaker() as session:
        selected = await _seed_provenance_closure(
            session, scope=scope, token=f"selected-{token}"
        )
        foreign = await _seed_provenance_closure(
            session, scope=foreign_scope, token=f"foreign-{token}"
        )
        foreign_segment = await session.scalar(
            select(ContentSegmentRecord).where(
                ContentSegmentRecord.email_id == foreign["email_id"]
            )
        )
        if reference_field.startswith("object_"):
            record = await session.scalar(
                select(ProjectGraphObjectRecord).where(
                    ProjectGraphObjectRecord.project_graph_object_id
                    == selected["project_object_id"]
                )
            )
        elif reference_field.startswith("edge_"):
            record = await session.scalar(
                select(ProjectGraphEdgeRecord).where(
                    ProjectGraphEdgeRecord.workspace_id == scope.workspace_id
                )
            )
        else:
            record = await session.scalar(
                select(ProjectGraphCorrectionRecord).where(
                    ProjectGraphCorrectionRecord.workspace_id == scope.workspace_id
                )
            )
        if reference_field == "edge_without_object_anchors":
            record.source_object_id = None
            record.target_object_id = None
        elif reference_field == "edge_source_object":
            record.source_object_id = foreign["project_object_id"]
        elif reference_field == "edge_target_object":
            record.target_object_id = foreign["project_object_id"]
        elif reference_field == "correction_object":
            record.project_graph_object_id = foreign["project_object_id"]
        elif reference_field.endswith("_primary"):
            record.primary_content_segment_id = foreign_segment.content_segment_id
        else:
            record.source_segment_uids = [foreign_segment.content_segment_uid]
        await session.commit()

    async with provenance_sessionmaker() as session:
        with pytest.raises(ProvenanceArchiveError):
            await export_tenant_provenance(session, scope)
