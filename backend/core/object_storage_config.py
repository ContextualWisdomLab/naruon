"""Validated deployment policy for raw document object storage.

The process environment selects only the broad backend mode, trusted custom
endpoint hosts, and a transport timeout. Organization-owned bucket metadata,
encryption choices, and credentials live in the Fernet-encrypted PostgreSQL
provider registry and are resolved through a scoped runtime session.
"""

from __future__ import annotations

from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.env_paths import ENV_FILE_PATHS, operator_env_file_paths
from core.url_validation import parse_allowed_hosts


class ObjectStorageSettings(BaseSettings):
    """Deployment policy for selecting and constraining document persistence."""

    OBJECT_STORAGE_BACKEND: str = "database"
    OBJECT_STORAGE_S3_ALLOWED_HOSTS: str = ""
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
        """Normalize backend policy and reject unsafe host or timeout settings."""
        self.OBJECT_STORAGE_BACKEND = self.OBJECT_STORAGE_BACKEND.strip().lower()
        if self.OBJECT_STORAGE_BACKEND not in {"database", "s3"}:
            raise ValueError("OBJECT_STORAGE_BACKEND must be database or s3")
        if not 0 < self.OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS <= 300:
            raise ValueError(
                "OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS must be between 0 and 300"
            )
        allowed_hosts = parse_allowed_hosts(self.OBJECT_STORAGE_S3_ALLOWED_HOSTS)
        if any("*" in host for host in allowed_hosts):
            raise ValueError("OBJECT_STORAGE_S3_ALLOWED_HOSTS must not use wildcards")
        self.OBJECT_STORAGE_S3_ALLOWED_HOSTS = ",".join(sorted(allowed_hosts))
        return self


object_storage_settings = ObjectStorageSettings()
