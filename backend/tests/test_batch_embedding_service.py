"""Tests for batch-tolerant embedding routing via the pg-llm-batch submodule.

These are fast, fully-mocked unit tests: no live Postgres, pg_tiktoken, or the
submodule itself is required. They verify three properties the integration
promises:

* bulk import embeddings route through the batch engine when a tenant has
  enabled + configured batching;
* the path degrades gracefully (returns ``None`` so callers fall back to the
  per-item path) when batching is disabled or the submodule is not importable;
* batch config (enablement + DSN) is read from the per-tenant Fernet-encrypted
  ``tenant_configs`` row, never from ``os.getenv``.
"""

import os
import types
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from core.config import settings
from db.models import LlmBatchItem, LlmBatchJob, TenantConfig
from services.email_import_service import (
    EmailImportBatchContext,
    EmailImportEmbeddingProvider,
    _generate_import_embeddings,
)
import services.batch_embedding_service as batch_module
from services.batch_embedding_service import (
    resolve_batch_embedding_settings,
    try_batch_import_embeddings,
)


PROVIDER = EmailImportEmbeddingProvider(
    api_key="secret-provider-token",
    base_url="http://gateway.internal/v1",
    embedding_model="text-embedding-test",
)


@pytest.fixture(autouse=True)
def encryption_key():
    old_key = settings.ENCRYPTION_KEY
    settings.ENCRYPTION_KEY = SecretStr(Fernet.generate_key().decode("ascii"))
    yield
    settings.ENCRYPTION_KEY = old_key


class FakeResult:
    def __init__(self, tenant_config):
        self._tenant_config = tenant_config

    def scalar_one_or_none(self):
        return self._tenant_config


class FakeAsyncSession:
    """Minimal async session: returns a tenant config and records .add()."""

    def __init__(self, tenant_config=None):
        self.tenant_config = tenant_config
        self.added: list = []

    async def execute(self, _stmt):
        return FakeResult(self.tenant_config)

    def add(self, obj):
        self.added.append(obj)


# --- Fake pg-llm-batch engine (stands in for the submodule) -----------------


class _FakeConfigStore:
    def __init__(self, dsn):
        self.dsn = dsn
        self.closed = False

    def close(self):
        self.closed = True


class _FakeTokenCounter:
    def __init__(self, dsn, config=None):
        self.dsn = dsn
        self.config = config


class _FakeAccumulator:
    """Partitions into groups of two to exercise multi-part planning."""

    def __init__(self, counter, model):
        self.model = model
        self.reset()

    def reset(self):
        self.record_count = 0

    def compute_tokens(self, _system, user):
        tokens = len(user)
        return tokens, 0, tokens

    @staticmethod
    def compute_byte_size(line):
        return len(line.encode("utf-8")) + 1

    def would_exceed(self, _tokens, _byte_size):
        return self.record_count >= 2

    def add_entry(self, _rid, _line, _tokens, _byte_size):
        self.record_count += 1


def _fake_engine():
    return types.SimpleNamespace(
        PostgresConfigStore=_FakeConfigStore,
        TokenCounter=_FakeTokenCounter,
        BatchAccumulator=_FakeAccumulator,
    )


def _batch_tenant_config(**overrides):
    config = TenantConfig(user_id="user-1", organization_id="org-acme")
    config.batch_embedding_enabled = True
    config.batch_embedding_dsn = "postgresql://batch-host/batch_db"
    config.batch_embedding_endpoint = "primary_gateway"
    config.batch_embedding_model = "text-embedding-test"
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


# --- Routing ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_embeddings_route_through_batch_component(monkeypatch):
    session = FakeAsyncSession(_batch_tenant_config())
    monkeypatch.setattr(batch_module, "load_batch_engine", _fake_engine)
    generate = AsyncMock(side_effect=lambda texts, *a, **k: [[0.5] * 8 for _ in texts])
    monkeypatch.setattr(batch_module, "generate_embeddings", generate)

    texts = ["body", "att-1", "att-2", "att-3", "att-4"]
    result = await try_batch_import_embeddings(
        session,
        texts,
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
        dimension=8,
    )

    assert result is not None
    assert len(result) == 5
    assert all(len(vector) == 8 for vector in result)
    # 5 texts partitioned two-at-a-time -> 3 batch parts -> 3 embedding calls.
    assert generate.await_count == 3
    # Credentials came from the runtime provider, not os.getenv.
    assert generate.await_args_list[0].args[1] == "secret-provider-token"

    jobs = [obj for obj in session.added if isinstance(obj, LlmBatchJob)]
    items = [obj for obj in session.added if isinstance(obj, LlmBatchItem)]
    assert len(jobs) == 1
    assert jobs[0].job_status == "completed"
    assert jobs[0].total_items == 5
    assert jobs[0].part_count == 3
    assert len(items) == 5
    assert all(item.item_status == "completed" for item in items)
    assert {item.part_index for item in items} == {0, 1, 2}


@pytest.mark.asyncio
async def test_import_embeddings_fall_back_when_batch_disabled(monkeypatch):
    session = FakeAsyncSession(_batch_tenant_config(batch_embedding_enabled=False))
    monkeypatch.setattr(batch_module, "load_batch_engine", _fake_engine)
    generate = AsyncMock()
    monkeypatch.setattr(batch_module, "generate_embeddings", generate)

    result = await try_batch_import_embeddings(
        session,
        ["body"],
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
    )

    assert result is None
    generate.assert_not_awaited()
    assert session.added == []


@pytest.mark.asyncio
async def test_import_embeddings_fall_back_when_submodule_missing(monkeypatch):
    session = FakeAsyncSession(_batch_tenant_config())
    monkeypatch.setattr(batch_module, "load_batch_engine", lambda: None)
    generate = AsyncMock()
    monkeypatch.setattr(batch_module, "generate_embeddings", generate)

    result = await try_batch_import_embeddings(
        session,
        ["body"],
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
    )

    assert result is None
    generate.assert_not_awaited()
    assert session.added == []


@pytest.mark.asyncio
async def test_load_batch_engine_is_import_guarded():
    # The submodule is not installed on the backend path in this environment,
    # so the loader must degrade to None rather than raising ImportError.
    batch_module._ENGINE_CACHE.clear()
    try:
        assert batch_module.load_batch_engine() is None
    finally:
        batch_module._ENGINE_CACHE.clear()


# --- email_import_service wiring --------------------------------------------


@pytest.mark.asyncio
async def test_generate_import_embeddings_prefers_batch_context(monkeypatch):
    context = EmailImportBatchContext(
        session=FakeAsyncSession(), user_id="user-1", organization_id="org-acme"
    )
    batched = [[0.1] * 1536, [0.2] * 1536]
    routed = AsyncMock(return_value=batched)
    monkeypatch.setattr(
        "services.email_import_service.try_batch_import_embeddings", routed
    )
    per_item = AsyncMock()
    monkeypatch.setattr("services.email_import_service.generate_embeddings", per_item)

    result = await _generate_import_embeddings(
        ["body", "attachment"],
        embedding_provider=PROVIDER,
        batch_context=context,
    )

    assert result == batched
    routed.assert_awaited_once()
    # Batch path handled it; the per-item embedding path was never touched.
    per_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_import_embeddings_falls_back_when_batch_returns_none(
    monkeypatch,
):
    context = EmailImportBatchContext(
        session=FakeAsyncSession(), user_id="user-1", organization_id="org-acme"
    )
    routed = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "services.email_import_service.try_batch_import_embeddings", routed
    )
    per_item = AsyncMock(return_value=[[0.9] * 1536, [0.9] * 1536])
    monkeypatch.setattr("services.email_import_service.generate_embeddings", per_item)

    result = await _generate_import_embeddings(
        ["body", "attachment"],
        embedding_provider=PROVIDER,
        batch_context=context,
    )

    routed.assert_awaited_once()
    # Fell through to the existing bulk/per-item path.
    per_item.assert_awaited()
    assert len(result) == 2


# --- Config from the Fernet DB (never env) ----------------------------------


@pytest.mark.asyncio
async def test_batch_config_resolves_from_fernet_db_not_env(monkeypatch):
    monkeypatch.delenv("PG_LLM_BATCH_DSN", raising=False)
    secret_dsn = "postgresql://batch-user:batch-pass@batch-host/batch_db"

    engine = create_engine("sqlite:///:memory:")
    TenantConfig.__table__.create(engine)
    try:
        with Session(engine) as session:
            session.add(
                TenantConfig(
                    user_id="user-1",
                    organization_id="org-acme",
                    batch_embedding_enabled=True,
                    batch_embedding_dsn=secret_dsn,
                    batch_embedding_endpoint="primary_gateway",
                    batch_embedding_model="text-embedding-test",
                )
            )
            session.commit()

            # Stored at rest as Fernet ciphertext, not the plaintext DSN.
            raw = session.execute(
                text("SELECT batch_embedding_dsn FROM tenant_configs")
            ).scalar_one()
            assert raw != secret_dsn
            assert "batch-pass" not in raw

            reloaded = session.query(TenantConfig).one()
            assert reloaded.batch_embedding_dsn == secret_dsn
    finally:
        engine.dispose()

    # The resolver returns the DSN decrypted from the DB row, and no env var
    # supplied it.
    settings_obj = await resolve_batch_embedding_settings(
        FakeAsyncSession(reloaded),
        user_id="user-1",
        organization_id="org-acme",
    )
    assert settings_obj is not None
    assert settings_obj.dsn == secret_dsn
    assert settings_obj.endpoint_alias == "primary_gateway"
    assert "PG_LLM_BATCH_DSN" not in os.environ
