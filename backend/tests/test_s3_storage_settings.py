"""Validation tests for nonsecret deployment-level object-storage policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.object_storage_config import ObjectStorageSettings


def _settings(**overrides) -> ObjectStorageSettings:
    values = {"_env_file": ()}
    values.update(overrides)
    return ObjectStorageSettings(**values)


@pytest.mark.parametrize("backend", ["database", " s3 "])
def test_supported_backend_mode_needs_no_process_credentials(backend: str) -> None:
    configured = _settings(OBJECT_STORAGE_BACKEND=backend)
    assert configured.OBJECT_STORAGE_BACKEND == backend.strip()


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"OBJECT_STORAGE_BACKEND": "unknown"}, "OBJECT_STORAGE_BACKEND"),
        ({"OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS": 0}, "between 0 and 300"),
        ({"OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS": 301}, "between 0 and 300"),
        (
            {"OBJECT_STORAGE_S3_ALLOWED_HOSTS": "*.objects.example.com"},
            "must not use wildcards",
        ),
        (
            {"OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS": -1},
            "between 0 and 2592000",
        ),
        (
            {"OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS": 2592001},
            "between 0 and 2592000",
        ),
    ],
)
def test_invalid_operator_policy_fails_closed(overrides, expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        _settings(**overrides)


def test_custom_endpoint_hosts_are_normalized_and_deduplicated() -> None:
    configured = _settings(
        OBJECT_STORAGE_BACKEND="s3",
        OBJECT_STORAGE_S3_ALLOWED_HOSTS=(
            " Objects.EXAMPLE.com.,objects.example.com,backup.example.com "
        ),
        OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS=12.5,
        OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS=172800,
    )

    assert configured.OBJECT_STORAGE_BACKEND == "s3"
    assert configured.OBJECT_STORAGE_S3_ALLOWED_HOSTS == (
        "backup.example.com,objects.example.com"
    )
    assert configured.OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS == 12.5
    assert configured.OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS == 172800


def test_consumed_object_retention_defaults_to_one_day() -> None:
    configured = _settings()

    assert configured.OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS == 86400
