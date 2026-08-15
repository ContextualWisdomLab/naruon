#!/usr/bin/env python3
"""Apply the reviewed S3 object-storage implementation to existing source files."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    """Replace exactly one source fragment and fail on drift."""
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one anchor in {path}, found {count}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


def prepend_after(path: str, marker: str, addition: str) -> None:
    """Insert content after one marker unless it is already present."""
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    if addition.strip() in content:
        return
    if content.count(marker) != 1:
        raise RuntimeError(f"Expected one marker in {path}")
    target.write_text(content.replace(marker, marker + addition, 1), encoding="utf-8")


def append_once(path: str, addition: str) -> None:
    """Append content unless it is already present."""
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    if addition.strip() in content:
        return
    target.write_text(content.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Settings: fail-closed backend selection and S3 operator contract.
# ---------------------------------------------------------------------------
replace_once(
    "backend/core/config.py",
    '''    CLEARFOLIO_BASE_URL: str | None = None

    # Hybrid search fusion''',
    '''    CLEARFOLIO_BASE_URL: str | None = None

    # Raw workspace-document persistence. PostgreSQL remains authoritative for
    # metadata and parsed text; S3 stores immutable raw binary payloads only.
    OBJECT_STORAGE_BACKEND: str = "database"
    OBJECT_STORAGE_S3_BUCKET_NAME: str | None = None
    OBJECT_STORAGE_S3_REGION_NAME: str = "us-east-1"
    OBJECT_STORAGE_S3_ENDPOINT_URL: str | None = None
    OBJECT_STORAGE_S3_ALLOWED_HOSTS: str = ""
    OBJECT_STORAGE_S3_ADDRESSING_STYLE: str = "virtual"
    OBJECT_STORAGE_S3_ACCESS_KEY_ID: SecretStr | None = None
    OBJECT_STORAGE_S3_SECRET_ACCESS_KEY: SecretStr | None = None
    OBJECT_STORAGE_S3_SESSION_TOKEN: SecretStr | None = None
    OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION: str = "AES256"
    OBJECT_STORAGE_S3_KMS_KEY_ID: str | None = None
    OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER: str | None = None
    OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Hybrid search fusion''',
)
replace_once(
    "backend/core/config.py",
    '''        parse_allowed_cors_origins(self.ALLOWED_CORS_ORIGINS)

        configured = self.AUTH_SESSION_HMAC_SECRET''',
    '''        parse_allowed_cors_origins(self.ALLOWED_CORS_ORIGINS)

        self.OBJECT_STORAGE_BACKEND = self.OBJECT_STORAGE_BACKEND.strip().lower()
        self.OBJECT_STORAGE_S3_ADDRESSING_STYLE = (
            self.OBJECT_STORAGE_S3_ADDRESSING_STYLE.strip().lower()
        )
        self.OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION = (
            self.OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION.strip()
        )
        if self.OBJECT_STORAGE_BACKEND not in {"database", "s3"}:
            raise ValueError("OBJECT_STORAGE_BACKEND must be database or s3")
        if self.OBJECT_STORAGE_S3_ADDRESSING_STYLE not in {"virtual", "path"}:
            raise ValueError(
                "OBJECT_STORAGE_S3_ADDRESSING_STYLE must be virtual or path"
            )
        if self.OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION not in {
            "AES256",
            "aws:kms",
        }:
            raise ValueError(
                "OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION must be AES256 or aws:kms"
            )
        if not 0 < self.OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS <= 300:
            raise ValueError(
                "OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS must be between 0 and 300"
            )
        expected_owner = self.OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER
        if expected_owner is not None and (
            len(expected_owner) != 12 or not expected_owner.isdigit()
        ):
            raise ValueError(
                "OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER must be a 12-digit account ID"
            )
        if (
            self.OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION == "aws:kms"
            and not (self.OBJECT_STORAGE_S3_KMS_KEY_ID or "").strip()
        ):
            raise ValueError(
                "OBJECT_STORAGE_S3_KMS_KEY_ID is required for aws:kms encryption"
            )
        if self.OBJECT_STORAGE_BACKEND == "s3":
            bucket_name = (self.OBJECT_STORAGE_S3_BUCKET_NAME or "").strip()
            if not bucket_name:
                raise ValueError(
                    "OBJECT_STORAGE_S3_BUCKET_NAME is required for the s3 backend"
                )
            if (
                len(bucket_name) < 3
                or len(bucket_name) > 63
                or bucket_name[0] in ".-"
                or bucket_name[-1] in ".-"
                or any(
                    character not in "abcdefghijklmnopqrstuvwxyz0123456789.-"
                    for character in bucket_name
                )
            ):
                raise ValueError("OBJECT_STORAGE_S3_BUCKET_NAME is invalid")
            region_name = self.OBJECT_STORAGE_S3_REGION_NAME.strip().lower()
            if not region_name or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                for character in region_name
            ):
                raise ValueError("OBJECT_STORAGE_S3_REGION_NAME is invalid")
            self.OBJECT_STORAGE_S3_REGION_NAME = region_name
            access_key = self.OBJECT_STORAGE_S3_ACCESS_KEY_ID
            secret_key = self.OBJECT_STORAGE_S3_SECRET_ACCESS_KEY
            if access_key is None or not access_key.get_secret_value().strip():
                raise ValueError(
                    "OBJECT_STORAGE_S3_ACCESS_KEY_ID is required for the s3 backend"
                )
            if secret_key is None or not secret_key.get_secret_value():
                raise ValueError(
                    "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY is required for the s3 backend"
                )
            endpoint_url = self.OBJECT_STORAGE_S3_ENDPOINT_URL
            if endpoint_url:
                if self.OBJECT_STORAGE_S3_ADDRESSING_STYLE != "path":
                    raise ValueError(
                        "Custom OBJECT_STORAGE_S3_ENDPOINT_URL requires path addressing"
                    )
                parsed_endpoint = urlsplit(endpoint_url.strip())
                if (
                    parsed_endpoint.scheme.lower() != "https"
                    or not parsed_endpoint.hostname
                    or parsed_endpoint.username
                    or parsed_endpoint.password
                    or parsed_endpoint.query
                    or parsed_endpoint.fragment
                ):
                    raise ValueError(
                        "OBJECT_STORAGE_S3_ENDPOINT_URL must be an https base URL"
                    )
                allowed_s3_hosts = parse_allowed_hosts(
                    self.OBJECT_STORAGE_S3_ALLOWED_HOSTS
                )
                endpoint_host = parsed_endpoint.hostname.lower().rstrip(".")
                if endpoint_host not in allowed_s3_hosts:
                    raise ValueError(
                        "OBJECT_STORAGE_S3_ENDPOINT_URL host must be listed in "
                        "OBJECT_STORAGE_S3_ALLOWED_HOSTS"
                    )
                self.OBJECT_STORAGE_S3_ENDPOINT_URL = endpoint_url.strip().rstrip("/")

        configured = self.AUTH_SESSION_HMAC_SECRET''',
)

# ---------------------------------------------------------------------------
# Relational model: normalized one-to-one raw-object metadata.
# ---------------------------------------------------------------------------
replace_once(
    "backend/db/models.py",
    '''from sqlalchemy import (
    Boolean,
    DateTime,''',
    '''from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,''',
)
replace_once(
    "backend/db/models.py",
    '''    workspace_entity: Mapped["Workspace"] = relationship(
        back_populates="workspace_documents"
    )''',
    '''    workspace_entity: Mapped["Workspace"] = relationship(
        back_populates="workspace_documents"
    )
    object_record: Mapped["DocumentObjectRecord | None"] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class DocumentObjectRecord(Base):
    """Integrity-bearing locator for a raw workspace document stored in S3."""

    __tablename__ = "document_object_records"
    __table_args__ = (
        CheckConstraint(
            "storage_backend = 's3'",
            name="ck_document_object_records_backend",
        ),
        CheckConstraint(
            "storage_state IN ('active', 'deleted')",
            name="ck_document_object_records_state",
        ),
        CheckConstraint(
            "content_length >= 0",
            name="ck_document_object_records_content_length",
        ),
        CheckConstraint(
            "bucket_name IS NOT NULL AND object_key IS NOT NULL "
            "AND inline_payload IS NULL",
            name="ck_document_object_records_s3_locator",
        ),
        UniqueConstraint(
            "document_id",
            name="uq_document_object_records_document",
        ),
        UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_document_object_records_locator",
        ),
        Index(
            "ix_document_object_records_state",
            "storage_backend",
            "storage_state",
        ),
        Index(
            "ix_document_object_records_checksum",
            "checksum_sha256",
        ),
    )

    document_object_record_id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("workspace_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    inline_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    content_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_state: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    document: Mapped["Document"] = relationship(back_populates="object_record")''',
)

# ---------------------------------------------------------------------------
# Data API: persist first, commit normalized metadata, compensate on DB failure.
# ---------------------------------------------------------------------------
replace_once(
    "backend/api/data.py",
    '''from datetime import datetime, timezone
import hashlib
import json
import re''',
    '''from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import uuid''',
)
replace_once(
    "backend/api/data.py",
    '''    ContentSegmentRecord,
    Document,
    Email,''',
    '''    ContentSegmentRecord,
    Document,
    DocumentObjectRecord,
    Email,''',
)
replace_once(
    "backend/api/data.py",
    '''from services.attachment_parser import get_attachment_parser_manifest
from services.newsdom_pdf_recognition import (''',
    '''from services.attachment_parser import get_attachment_parser_manifest
from services.document_object_storage import (
    DocumentObjectStorageError,
    decode_legacy_pdf_payload,
    delete_configured_document_payload,
    load_pending_pdf_document_bytes,
    store_configured_pdf_document,
)
from services.newsdom_pdf_recognition import (''',
)
replace_once(
    "backend/api/data.py",
    '''router = APIRouter(prefix="/api/data", tags=["data"])

DATA_VECTOR_DIMENSIONS''',
    '''router = APIRouter(prefix="/api/data", tags=["data"])
logger = logging.getLogger(__name__)

DATA_VECTOR_DIMENSIONS''',
)
replace_once(
    "backend/api/data.py",
    '''    try:
        decode_pending_pdf_document_bytes(document)
    except ValueError as exc:''',
    '''    try:
        await load_pending_pdf_document_bytes(db, document)
    except (ValueError, DocumentObjectStorageError) as exc:''',
)

api_path = ROOT / "backend/api/data.py"
api_content = api_path.read_text(encoding="utf-8")
api_start = api_content.index(
    '@router.post(\n    "/documents/pdf-dom-recognition",\n'
)
api_end = api_content.index(
    '\n\n@router.post(\n    "/documents/{document_id}/webdav-materialization-intent",',
    api_start,
)
api_replacement = '''@router.post(
    "/documents/pdf-dom-recognition",
    response_model=DataDocumentActionResponse,
)
async def upload_document_for_pdf_dom_recognition(
    file: UploadFile = File(...),
    # Declared as multipart form data (not a query parameter) so a client
    # sending document_name alongside the file is honored.
    document_name: str | None = Form(None),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DataDocumentActionResponse:
    """Persist a PDF and queue NewsDOM recognition without duplicating S3 bytes."""
    raw = await file.read(_MAX_PDF_DOM_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_PDF_DOM_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF upload is too large.")
    if not raw[:5] == b"%PDF-":
        raise HTTPException(
            status_code=415,
            detail="Only application/pdf uploads are supported for DOM recognition.",
        )

    document_id = f"doc_{uuid.uuid4().hex}"
    try:
        stored_payload = await store_configured_pdf_document(
            payload=raw,
            document_id=document_id,
            organization_id=auth_context.organization_id,
            workspace_id=auth_context.workspace_id,
        )
    except DocumentObjectStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Configured document storage is unavailable.",
        ) from exc

    document = Document(
        document_id=document_id,
        workspace_id=auth_context.workspace_id,
        organization_id=auth_context.organization_id,
        document_name=_safe_display_text(
            document_name or file.filename, "workspace document"
        ),
        document_type="pdf",
        document_content=stored_payload.document_content,
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )
    object_record: DocumentObjectRecord | None = stored_payload.to_object_record(
        document_id
    )
    try:
        db.add(document)
        if object_record is not None:
            db.add(object_record)
        await db.commit()
        await db.refresh(document)
    except Exception:
        await db.rollback()
        try:
            await delete_configured_document_payload(stored_payload)
        except DocumentObjectStorageError:
            logger.error(
                "Document object compensation failed after metadata commit failure"
            )
        raise

    return _document_response(
        document,
        audit_event="data.document.pdf_dom_recognition_upload",
        message=(
            "PDF stored in the configured document backend pending NewsDOM DOM "
            "recognition; no provider write executed."
        ),
    )


def decode_pending_pdf_document_bytes(document: Document) -> bytes:
    """Decode the backward-compatible inline PDF payload for legacy callers."""
    return decode_legacy_pdf_payload(document.document_content)
'''
api_path.write_text(
    api_content[:api_start] + api_replacement + api_content[api_end:],
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# NewsDOM worker: async database/S3 read seam with legacy fast path.
# ---------------------------------------------------------------------------
replace_once(
    "backend/services/newsdom_worker.py",
    '''from services.attachment_parser import decode_deferred_attachment_payload
from services.content_graph import ParseResult''',
    '''from services.attachment_parser import decode_deferred_attachment_payload
from services.content_graph import ParseResult
from services.document_object_storage import (
    DocumentObjectStorageError,
    load_pending_pdf_document_bytes,
)''',
)
replace_once(
    "backend/services/newsdom_worker.py",
    '''    from api.data import decode_pending_pdf_document_bytes

    try:
        pdf_bytes = decode_pending_pdf_document_bytes(document)
    except ValueError as exc:''',
    '''    try:
        pdf_bytes = await load_pending_pdf_document_bytes(session, document)
    except (ValueError, DocumentObjectStorageError) as exc:''',
)

# ---------------------------------------------------------------------------
# Operator and architecture documentation kept beside the implementation.
# ---------------------------------------------------------------------------
append_once(
    ".env.example",
    '''# Raw workspace-document storage. The database backend preserves the
# existing inline payload behavior. Select s3 to store immutable binary PDFs in
# AWS S3 or a path-style S3-compatible HTTPS endpoint.
OBJECT_STORAGE_BACKEND=database
OBJECT_STORAGE_S3_BUCKET_NAME=
OBJECT_STORAGE_S3_REGION_NAME=ap-northeast-2
OBJECT_STORAGE_S3_ENDPOINT_URL=
OBJECT_STORAGE_S3_ALLOWED_HOSTS=
OBJECT_STORAGE_S3_ADDRESSING_STYLE=virtual
OBJECT_STORAGE_S3_ACCESS_KEY_ID=
OBJECT_STORAGE_S3_SECRET_ACCESS_KEY=
OBJECT_STORAGE_S3_SESSION_TOKEN=
OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION=AES256
OBJECT_STORAGE_S3_KMS_KEY_ID=
OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER=
OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS=30''',
)
append_once(
    "ARCHITECTURE.md",
    '''## Raw document object-storage boundary

PostgreSQL remains authoritative for workspace scope, authorization, workflow
status, parsed text, checksums, and provenance. Deployments may retain the
backward-compatible inline `database` backend or select `s3` for immutable raw
PDF bytes. S3-backed bytes are referenced by the normalized
`document_object_records` table; no bucket or key is accepted from a client.
Keys contain a one-way scope digest and opaque document ID rather than tenant,
workspace, or filename data.

The S3 adapter signs every request with AWS Signature Version 4, sends a SHA-256
payload checksum, requires server-side encryption, disables overwrite with
`If-None-Match: *`, follows no redirects, and verifies byte length plus SHA-256
on every read. Custom S3-compatible endpoints must be HTTPS, exact-host
allowlisted, path-addressed, and DNS-pinned. The first release is server-mediated
only: no public bucket, ACL, browser credential, or presigned URL surface exists.''',
)
append_once(
    "AGENTS.md",
    '''### Document object-storage contract

- PostgreSQL owns document scope, authorization, state, parsed text, integrity
  metadata, and provenance. S3 may own immutable raw bytes only.
- Never accept a bucket name, object key, endpoint, encryption setting, or S3
  credential from an API caller. These are operator settings and secret values.
- S3 keys must be opaque and must not contain organization IDs, workspace IDs,
  user-provided filenames, email addresses, or other PII.
- Every write requires a signed SHA-256 payload, explicit server-side encryption,
  and non-overwrite semantics. Every read must verify stored length and SHA-256.
- S3 request failures must not log response bodies, credentials, bucket names,
  keys, or source filenames. Database commit failures after an upload require a
  bounded compensating delete attempt.
- Keep the database backend backward compatible and test both backends. New
  production storage branches require 100% statement and branch coverage and
  public API docstrings before merge.''',
)
prepend_after(
    "CHANGELOG.md",
    "## [Unreleased]\n",
    '''
### S3 문서 저장 백엔드

- NewsDOM 처리를 기다리는 원본 PDF를 PostgreSQL inline payload 또는 AWS
  S3/S3-compatible object storage에 저장하는 교체형 백엔드를 추가했습니다.
  PostgreSQL은 권한·상태·파싱 텍스트·무결성·provenance의 원장으로 유지되고,
  S3 메타데이터는 3NF `document_object_records`에 1:1로 저장됩니다.
- S3 경로는 조직·workspace·파일명을 노출하지 않는 opaque key를 사용하며,
  SigV4, SHA-256 checksum, SSE-S3/SSE-KMS, non-overwrite, exact-host allowlist,
  DNS pinning, redirect 금지, read-back 길이·해시 검증을 강제합니다.
- DB commit 실패 시 업로드 객체를 보상 삭제하고, 오류 응답과 로그에는
  credential·bucket·key·provider body를 노출하지 않습니다. 기존 database
  backend와 기존 base64 문서는 그대로 호환됩니다.
''',
)
append_once(
    "docs/adr/README.md",
    '''- [ADR-0004: S3 raw document object storage](0004-s3-document-object-storage.md) — keeps PostgreSQL authoritative while allowing immutable raw PDF bytes in a hardened S3-compatible backend.''',
)
