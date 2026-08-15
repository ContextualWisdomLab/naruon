"""Docstring contract for the object-storage production modules."""

from __future__ import annotations

import inspect

import pytest

import api.document_storage as document_storage_api
import core.object_storage_config as object_storage_config
import db.document_object_record as document_object_record
import services.document_object_storage as document_storage
import services.s3_object_storage as s3_storage


@pytest.mark.parametrize(
    "module",
    [
        document_storage_api,
        object_storage_config,
        document_object_record,
        document_storage,
        s3_storage,
    ],
)
def test_public_storage_symbols_have_docstrings(module) -> None:
    """Require readable documentation on every public owned class/function."""
    missing: list[str] = []
    for name, value in vars(module).items():
        if name.startswith("_") or getattr(value, "__module__", None) != module.__name__:
            continue
        if (inspect.isclass(value) or inspect.isfunction(value)) and not inspect.getdoc(value):
            missing.append(name)
    assert missing == []
