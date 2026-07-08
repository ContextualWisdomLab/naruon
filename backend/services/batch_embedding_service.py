"""Batch-tolerant embedding routing backed by the pg-llm-batch component.

This adapter lets naruon route *bulk, latency-tolerant* embedding work (email
import, summarization backfills) through the ``pg-llm-batch`` git submodule
instead of issuing one embedding call per item. The component supplies the
token-budget-aware batching core (``pg_tiktoken`` counting + byte/record/token
accumulation); naruon records a durable job/item audit trail in its own control
plane (``llm_batch_jobs`` / ``llm_batch_items``).

Two hard requirements shape this module:

* **Graceful degradation.** If the submodule is not initialized (import fails),
  or the tenant has not enabled/configured batching, or the batch Postgres is
  unreachable, every entry point returns ``None`` so the caller transparently
  falls back to the existing per-item embedding path. naruon therefore keeps
  working with the submodule uninitialized.
* **No ``os.getenv`` for secrets/config.** Batch enablement, the batch Postgres
  DSN and the endpoint alias are resolved from the per-tenant Fernet-encrypted
  ``tenant_configs`` row (the batch DSN column is an ``EncryptedString``),
  mirroring how provider credentials are resolved via
  :func:`resolve_runtime_llm_provider`. The environment is never read here.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LlmBatchItem, LlmBatchJob
from services.embedding import (
    STORAGE_EMBEDDING_DIMENSION,
    fit_embedding_vector,
    generate_embeddings,
)
from services.exceptions import EmbeddingGenerationError
from services.tenant_config_scope import get_scoped_tenant_config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from services.email_import_service import EmailImportEmbeddingProvider

logger = logging.getLogger(__name__)

# Cache the (im)port result so repeated imports don't re-probe sys.path.
_ENGINE_CACHE: list[ModuleType | None] = []


def load_batch_engine() -> ModuleType | None:
    """Return the ``pg_llm_batch`` module, or ``None`` when unavailable.

    The submodule is an *optional* dependency: naruon must run with it
    uninitialized. When the package cannot be imported we log once at debug
    level and signal fallback by returning ``None``.
    """
    if _ENGINE_CACHE:
        return _ENGINE_CACHE[0]
    try:
        import pg_llm_batch  # type: ignore
    except ImportError:
        logger.debug(
            "pg_llm_batch submodule not importable; batch embedding disabled, "
            "falling back to per-item path"
        )
        _ENGINE_CACHE.append(None)
        return None
    _ENGINE_CACHE.append(pg_llm_batch)
    return pg_llm_batch


@dataclass(frozen=True)
class BatchEmbeddingSettings:
    """Per-tenant batch configuration resolved from the Fernet DB (never env)."""

    dsn: str
    endpoint_alias: str | None
    model: str


async def resolve_batch_embedding_settings(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> BatchEmbeddingSettings | None:
    """Resolve batch settings from the per-tenant Fernet-encrypted config.

    Returns ``None`` (i.e. "route the normal per-item path") unless the tenant
    has both enabled batching and stored a batch Postgres DSN. The DSN is read
    back through the ``EncryptedString`` column, so it is decrypted from the
    Fernet DB rather than read from the process environment.
    """
    tenant_config = await get_scoped_tenant_config(session, user_id, organization_id)
    if tenant_config is None:
        return None
    if not getattr(tenant_config, "batch_embedding_enabled", False):
        return None
    dsn = getattr(tenant_config, "batch_embedding_dsn", None)
    if not dsn:
        return None
    return BatchEmbeddingSettings(
        dsn=dsn,
        endpoint_alias=getattr(tenant_config, "batch_embedding_endpoint", None),
        model=(getattr(tenant_config, "batch_embedding_model", None) or "").strip()
        or None,  # resolved against the provider model below
    )


def _plan_partitions(
    engine: ModuleType, dsn: str, model: str, texts: list[str]
) -> tuple[list[list[int]], list[int]]:
    """Group text indices into token/byte/record-bounded partitions.

    Runs the component's ``TokenCounter`` + ``BatchAccumulator`` (which count
    tokens inside Postgres via ``pg_tiktoken``) to split the batch the same way
    the standalone engine would. Pure planning: returns index partitions plus
    the per-text token counts. Synchronous (psycopg) — call via a thread.
    """
    config = engine.PostgresConfigStore(dsn)
    try:
        counter = engine.TokenCounter(dsn, config=config)
        accumulator = engine.BatchAccumulator(counter, model)
        partitions: list[list[int]] = []
        current: list[int] = []
        token_counts: list[int] = []
        for index, text in enumerate(texts):
            total_tokens, _system, _user = accumulator.compute_tokens("", text)
            token_counts.append(int(total_tokens))
            byte_size = engine.BatchAccumulator.compute_byte_size(text)
            if current and accumulator.would_exceed(total_tokens, byte_size):
                partitions.append(current)
                current = []
                accumulator.reset()
            accumulator.add_entry(str(index), text, total_tokens, byte_size)
            current.append(index)
        if current:
            partitions.append(current)
        return partitions, token_counts
    finally:
        close = getattr(config, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover - defensive
                pass


async def try_batch_import_embeddings(
    session: AsyncSession,
    texts: list[str],
    *,
    embedding_provider: "EmailImportEmbeddingProvider",
    user_id: str,
    organization_id: str | None,
    dimension: int = STORAGE_EMBEDDING_DIMENSION,
) -> list[list[float]] | None:
    """Route bulk embeddings through the batch engine, or ``None`` to fall back.

    On success returns one fitted vector per input text (original order). Any
    failure — batch disabled, submodule missing, batch DB unreachable, embedding
    error — returns ``None`` so the caller uses its per-item path. The batch run
    is recorded in ``llm_batch_jobs`` / ``llm_batch_items`` for observability.
    """
    if not texts:
        return None

    settings = await resolve_batch_embedding_settings(
        session, user_id=user_id, organization_id=organization_id
    )
    if settings is None:
        return None

    engine = load_batch_engine()
    if engine is None:
        return None

    model = settings.model or embedding_provider.embedding_model

    try:
        partitions, token_counts = await asyncio.to_thread(
            _plan_partitions, engine, settings.dsn, model, texts
        )
    except Exception as exc:
        logger.warning(
            "Batch embedding planning unavailable; falling back to per-item path: "
            "error_type=%s text_count=%s",
            type(exc).__name__,
            len(texts),
        )
        return None

    job = _new_batch_job(
        organization_id=organization_id,
        user_id=user_id,
        model=model,
        endpoint_alias=settings.endpoint_alias,
        text_count=len(texts),
        total_tokens=sum(token_counts),
        part_count=len(partitions),
    )
    items = _new_batch_items(job.batch_job_uid, partitions, token_counts)
    session.add(job)
    for item in items:
        session.add(item)

    results: list[list[float] | None] = [None] * len(texts)
    try:
        for index_group in partitions:
            part_texts = [texts[i] for i in index_group]
            vectors = await generate_embeddings(
                part_texts,
                embedding_provider.api_key,
                base_url=embedding_provider.base_url,
                model=model,
            )
            for offset, text_index in enumerate(index_group):
                if offset < len(vectors):
                    results[text_index] = fit_embedding_vector(
                        vectors[offset], dimension
                    )
    except (EmbeddingGenerationError, ValueError, TypeError) as exc:
        logger.warning(
            "Batch embedding generation failed; falling back to per-item path: "
            "error_type=%s text_count=%s part_count=%s",
            type(exc).__name__,
            len(texts),
            len(partitions),
        )
        _mark_job_failed(job, items, error_code=type(exc).__name__)
        return None

    if any(vector is None for vector in results):
        # A partition returned fewer vectors than inputs — treat as incomplete
        # and fall back rather than persisting zero vectors silently.
        logger.warning(
            "Batch embedding returned incomplete vectors; falling back: "
            "text_count=%s",
            len(texts),
        )
        _mark_job_failed(job, items, error_code="incomplete_vectors")
        return None

    _mark_job_completed(job, items)
    return [vector for vector in results if vector is not None]


def _new_batch_job(
    *,
    organization_id: str | None,
    user_id: str,
    model: str,
    endpoint_alias: str | None,
    text_count: int,
    total_tokens: int,
    part_count: int,
) -> LlmBatchJob:
    return LlmBatchJob(
        batch_job_uid=f"llm_batch_{uuid.uuid4().hex}",
        organization_id=organization_id or "",
        user_id=user_id,
        job_status="preparing",
        model_name=model,
        endpoint_alias=endpoint_alias,
        total_items=text_count,
        completed_items=0,
        failed_items=0,
        total_tokens=total_tokens,
        part_count=part_count,
    )


def _new_batch_items(
    batch_job_uid: str,
    partitions: list[list[int]],
    token_counts: list[int],
) -> list[LlmBatchItem]:
    items: list[LlmBatchItem] = []
    for part_index, index_group in enumerate(partitions):
        for text_index in index_group:
            items.append(
                LlmBatchItem(
                    batch_item_uid=f"llm_batch_item_{uuid.uuid4().hex}",
                    batch_job_uid=batch_job_uid,
                    sequence_no=text_index,
                    part_index=part_index,
                    token_count=(
                        token_counts[text_index]
                        if text_index < len(token_counts)
                        else 0
                    ),
                    item_status="queued",
                )
            )
    return items


def _mark_job_completed(job: LlmBatchJob, items: list[LlmBatchItem]) -> None:
    job.job_status = "completed"
    job.completed_items = job.total_items
    for item in items:
        item.item_status = "completed"


def _mark_job_failed(
    job: LlmBatchJob, items: list[LlmBatchItem], *, error_code: str
) -> None:
    job.job_status = "failed"
    job.failed_items = job.total_items
    job.error_code = error_code
    for item in items:
        item.item_status = "failed"
