"""Cross-service contract test for the batch embeddings integration.

This is the naruon half of a *real* contract test (not just mocks-passing): it
asserts that ``batch_embedding_service`` serializes to exactly the request the
contextual-orchestrator ``/v1/batch/embeddings`` endpoint accepts, and parses
exactly the response that endpoint returns.

Both repositories keep a byte-identical copy of
``fixtures/batch_embeddings_contract.json`` (the orchestrator asserts its server
against the same file in ``tests/test_batch_embeddings.py``). If either side
drifts from the shared shape, one of these tests fails — which is precisely the
defect this reconciliation fixes: naruon was POSTing to a path/shape the
orchestrator never exposed, so real calls 404'd and only mocks passed.
"""

import json
from pathlib import Path

import pytest

from db.models import LlmBatchItem, LlmBatchJob, TenantConfig
from services.batch_embedding_service import (
    _BATCH_SUBMIT_PATH,
    try_batch_import_embeddings,
)

from tests.test_batch_embedding_service import (  # reuse the fakes
    FakeAsyncClient,
    FakeAsyncSession,
    FakeResponse,
    ORCH_URL,
    PROVIDER,
    _patch_client,
    encryption_key,  # noqa: F401 - autouse fixture
    fast_polls,  # noqa: F401 - autouse fixture
)


CONTRACT = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "batch_embeddings_contract.json").read_text(
        encoding="utf-8"
    )
)


def _attributed_tenant_config():
    config = TenantConfig(user_id="user-1", organization_id="org-acme")
    config.batch_embedding_enabled = True
    config.batch_orchestrator_base_url = ORCH_URL
    config.batch_orchestrator_token = "orch-secret-token"
    config.batch_orchestrator_endpoint = CONTRACT["request"]["endpoint"]
    config.batch_embedding_model = CONTRACT["request"]["model"]
    config.batch_local_dsn = None
    # Full attribution context from the tenant/config (never env).
    config.batch_attribution_service = CONTRACT["request"]["metadata"]["service"]
    config.batch_attribution_team = CONTRACT["request"]["metadata"]["team"]
    config.batch_attribution_group = CONTRACT["request"]["metadata"]["group"]
    config.batch_attribution_company = CONTRACT["request"]["metadata"]["company"]
    return config


def _contract_completed_response(count):
    """Build the exact response the orchestrator endpoint returns for the batch."""
    return FakeResponse(
        {
            "batch_id": "orc_batch_contract",
            "status": CONTRACT["response"]["status_completed"],
            "embeddings": [
                {"index": i, "embedding": [0.5, -0.25, 0.125] } for i in range(count)
            ],
            "cost_micro_usd": 4200,
            "part_count": 1,
            "total_tokens": 12,
            "token_counts": [4] * count,
        }
    )


@pytest.mark.asyncio
async def test_client_serializes_to_exact_contract_request(monkeypatch):
    """naruon POSTs exactly the path + payload the orchestrator endpoint accepts."""
    session = FakeAsyncSession(_attributed_tenant_config())
    texts = list(CONTRACT["request"]["inputs"])
    client = FakeAsyncClient(post_responses=[_contract_completed_response(len(texts))])
    _patch_client(monkeypatch, client)

    result = await try_batch_import_embeddings(
        session,
        texts,
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
        dimension=8,
        zdr_only=CONTRACT["request"]["zdr_only"],
    )
    assert result is not None
    assert len(result) == len(texts)

    # Path is exactly the contract submit path.
    assert _BATCH_SUBMIT_PATH == CONTRACT["endpoint"]["submit_path"]
    call = client.post_calls[0]
    assert call["url"] == ORCH_URL + CONTRACT["endpoint"]["submit_path"]

    body = call["json"]
    # Request required keys are present with the contract values.
    for key in CONTRACT["request_required_keys"]:
        assert key in body
    assert body["inputs"] == texts
    assert body["model"] == CONTRACT["request"]["model"]
    assert body["zdr_only"] is True
    assert body["endpoint"] == CONTRACT["request"]["endpoint"]

    # FULL attribution: every dimension the orchestrator ledger expects is sent
    # in metadata, sourced from the tenant/config context.
    metadata = body["metadata"]
    for dimension in CONTRACT["attribution_dimensions_in_metadata"]:
        assert metadata.get(dimension) == CONTRACT["request"]["metadata"][dimension]
    # Observability keys are still present.
    assert metadata["source"] == "naruon-email-import"
    assert metadata["organization_id"] == "org-acme"
    assert metadata["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_client_forwards_false_zdr_policy(monkeypatch):
    """The gateway option remains caller-controlled instead of being hardcoded."""
    session = FakeAsyncSession(_attributed_tenant_config())
    client = FakeAsyncClient(
        post_responses=[_contract_completed_response(len(CONTRACT["request"]["inputs"]))]
    )
    _patch_client(monkeypatch, client)

    result = await try_batch_import_embeddings(
        session,
        list(CONTRACT["request"]["inputs"]),
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
        dimension=8,
        zdr_only=False,
    )

    assert result is not None
    assert client.post_calls[0]["json"]["zdr_only"] is False


@pytest.mark.asyncio
async def test_client_parses_exact_contract_response(monkeypatch):
    """naruon parses the orchestrator's response shape into vectors + audit rows."""
    session = FakeAsyncSession(_attributed_tenant_config())
    texts = list(CONTRACT["request"]["inputs"])
    client = FakeAsyncClient(post_responses=[_contract_completed_response(len(texts))])
    _patch_client(monkeypatch, client)

    result = await try_batch_import_embeddings(
        session,
        texts,
        embedding_provider=PROVIDER,
        user_id="user-1",
        organization_id="org-acme",
        dimension=8,
    )

    # Every input got a fitted vector back, in order.
    assert result is not None
    assert len(result) == len(texts)
    assert all(len(vector) == 8 for vector in result)

    # The response's cost + batch id land on the audit row (from the exact keys).
    jobs = [obj for obj in session.added if isinstance(obj, LlmBatchJob)]
    items = [obj for obj in session.added if isinstance(obj, LlmBatchItem)]
    assert len(jobs) == 1
    assert jobs[0].orchestrator_batch_uid == "orc_batch_contract"
    assert jobs[0].cost_micro_usd == 4200
    assert jobs[0].routing_mode == "orchestrator"
    assert len(items) == len(texts)


def test_contract_fixture_matches_orchestrator_copy():
    """The shared fixture must stay byte-identical to the orchestrator's copy.

    The orchestrator repo asserts its server against the same JSON; this guards
    the naruon copy's structural keys so a one-sided edit is caught here.
    """
    assert CONTRACT["endpoint"]["submit_path"] == "/v1/batch/embeddings"
    assert CONTRACT["endpoint"]["poll_path_template"] == "/v1/batch/embeddings/{batch_id}"
    assert set(CONTRACT["response"]["required_keys"]) == {
        "batch_id",
        "status",
        "embeddings",
        "cost_micro_usd",
        "token_counts",
    }
    assert CONTRACT["response"]["embedding_item_keys"] == ["index", "embedding"]
