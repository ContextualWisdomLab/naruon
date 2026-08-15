"""Validated operator configuration for raw document object storage.

This module keeps the object-storage deployment contract independent from the
application-wide settings singleton.  Deployments can continue using the
``database`` backend with no additional configuration; selecting ``s3`` fails
closed unless the bucket, credentials, addressing mode, encryption settings,
and custom-endpoint allowlist are internally consistent.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env_paths import ENV_FILE_PATHS, operator_env_file_paths
from core.url_validation import parse_allowed_hosts


class ObjectStorageSettings(BaseSettings):
    """Deployment-level configuration for raw workspace-document persistence."""

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

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATHS,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        """Load operator env files unless tests explicitly provide another source."""
        values.setdefault("_env_file", operator_env_file_paths())
        super().__init__(**values)

    @model_validator(mode="after")
    def validate_object_storage(self) -> "ObjectStorageSettings":
        """Normalize and fail closed on unsafe or incomplete S3 configuration."""
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

        if self.OBJECT_STORAGE_BACKEND == "database":
            return self

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
        self.OBJECT_STORAGE_S3_BUCKET_NAME = bucket_name

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
            normalized_endpoint = endpoint_url.strip().rstrip("/")
            parsed_endpoint = urlsplit(normalized_endpoint)
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
            self.OBJECT_STORAGE_S3_ENDPOINT_URL = normalized_endpoint

        return self


object_storage_settings = ObjectStorageSettings()
