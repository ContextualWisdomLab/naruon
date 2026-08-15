"""Validation tests for operator-provided S3 object-storage settings."""

from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from core.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
        "ALLOWED_CORS_ORIGINS": "http://localhost:3000",
        "_env_file": (),
    }
    values.update(overrides)
    return Settings(**values)


def test_database_backend_needs_no_s3_credentials() -> None:
    configured = _settings(OBJECT_STORAGE_BACKEND="database")
    assert configured.OBJECT_STORAGE_BACKEND == "database"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"OBJECT_STORAGE_BACKEND": "unknown"}, "OBJECT_STORAGE_BACKEND"),
        ({"OBJECT_STORAGE_BACKEND": "s3"}, "OBJECT_STORAGE_S3_BUCKET_NAME"),
        (
            {
                "OBJECT_STORAGE_BACKEND": "s3",
                "OBJECT_STORAGE_S3_BUCKET_NAME": "naruon-documents",
                "OBJECT_STORAGE_S3_ACCESS_KEY_ID": "access",
            },
            "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY",
        ),
        (
            {
                "OBJECT_STORAGE_BACKEND": "s3",
                "OBJECT_STORAGE_S3_BUCKET_NAME": "naruon-documents",
                "OBJECT_STORAGE_S3_ACCESS_KEY_ID": "access",
                "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY": "secret",
                "OBJECT_STORAGE_S3_ADDRESSING_STYLE": "invalid",
            },
            "OBJECT_STORAGE_S3_ADDRESSING_STYLE",
        ),
        (
            {
                "OBJECT_STORAGE_BACKEND": "s3",
                "OBJECT_STORAGE_S3_BUCKET_NAME": "naruon-documents",
                "OBJECT_STORAGE_S3_ACCESS_KEY_ID": "access",
                "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY": "secret",
                "OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION": "aws:kms",
            },
            "OBJECT_STORAGE_S3_KMS_KEY_ID",
        ),
        (
            {
                "OBJECT_STORAGE_BACKEND": "s3",
                "OBJECT_STORAGE_S3_BUCKET_NAME": "naruon-documents",
                "OBJECT_STORAGE_S3_ACCESS_KEY_ID": "access",
                "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY": "secret",
                "OBJECT_STORAGE_S3_ENDPOINT_URL": "https://objects.example.com",
                "OBJECT_STORAGE_S3_ALLOWED_HOSTS": "objects.example.com",
                "OBJECT_STORAGE_S3_ADDRESSING_STYLE": "virtual",
            },
            "path addressing",
        ),
    ],
)
def test_invalid_s3_configuration_fails_closed(overrides, expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        _settings(**overrides)


def test_valid_s3_configuration_preserves_secrets_as_secret_values() -> None:
    configured = _settings(
        OBJECT_STORAGE_BACKEND="s3",
        OBJECT_STORAGE_S3_BUCKET_NAME="naruon-documents",
        OBJECT_STORAGE_S3_REGION_NAME="ap-northeast-2",
        OBJECT_STORAGE_S3_ACCESS_KEY_ID="access-key",
        OBJECT_STORAGE_S3_SECRET_ACCESS_KEY="secret-key",
        OBJECT_STORAGE_S3_SESSION_TOKEN="temporary-token",
        OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER="111122223333",
        OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION="aws:kms",
        OBJECT_STORAGE_S3_KMS_KEY_ID="arn:aws:kms:ap-northeast-2:111122223333:key/example",
        OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS=12.5,
    )

    assert configured.OBJECT_STORAGE_BACKEND == "s3"
    assert configured.OBJECT_STORAGE_S3_REGION_NAME == "ap-northeast-2"
    assert configured.OBJECT_STORAGE_S3_ACCESS_KEY_ID.get_secret_value() == "access-key"
    assert configured.OBJECT_STORAGE_S3_SECRET_ACCESS_KEY.get_secret_value() == "secret-key"
    assert configured.OBJECT_STORAGE_S3_SESSION_TOKEN.get_secret_value() == "temporary-token"
