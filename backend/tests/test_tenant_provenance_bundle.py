import copy
import datetime
import hashlib
import io
import json
import struct
import uuid
import warnings
import zipfile

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError
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
)

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
