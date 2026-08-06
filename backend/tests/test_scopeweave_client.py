import pytest
import respx
import httpx
from core.url_validation import ValidatedHTTPSURLHost
from services.scopeweave_client import (
    push_work_item,
    ScopeweavePushError,
    _parse_import_result,
    ScopeweaveImportResult,
    _import_url,
)

def _validated_host() -> ValidatedHTTPSURLHost:
    return ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com",
        hostname="scopeweave.example.com",
        port=443,
        addresses=("8.8.8.8",),
    )

def test_import_url():
    validated = ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com",
        hostname="scopeweave.example.com",
        port=443,
        addresses=("8.8.8.8",)
    )
    assert _import_url(validated) == "https://scopeweave.example.com/api/imports/work-items"

    validated2 = ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com/",
        hostname="scopeweave.example.com",
        port=443,
        addresses=("8.8.8.8",)
    )
    assert _import_url(validated2) == "https://scopeweave.example.com/api/imports/work-items"

def test_parse_import_result_invalid_json():
    with pytest.raises(ScopeweavePushError, match="scopeweave returned a non-JSON import response"):
        _parse_import_result(httpx.Response(201, text="not json"))

def test_parse_import_result_not_dict():
    with pytest.raises(ScopeweavePushError, match="scopeweave import response was not an object"):
        _parse_import_result(httpx.Response(201, json=["list"]))

def test_parse_import_result_missing_id():
    with pytest.raises(ScopeweavePushError, match="scopeweave import response omitted a work item id"):
        _parse_import_result(httpx.Response(201, json={"work_item_url": "url"}))

def test_parse_import_result_fallback_id():
    res = _parse_import_result(httpx.Response(201, json={"id": "fallback-id"}))
    assert res.work_item_id == "fallback-id"

@pytest.mark.asyncio
@respx.mock
async def test_push_work_item_success(monkeypatch):
    import services.scopeweave_client as scopeweave_client
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )

    mock_route = respx.post("https://scopeweave.example.com/api/imports/work-items").mock(
        return_value=httpx.Response(
            201,
            json={"work_item_id": "WI-42", "work_item_url": "https://scopeweave.example.com/w/WI-42"}
        )
    )

    result = await push_work_item(
        base_url="https://scopeweave.example.com",
        access_token="pat-secret",
        payload={"hello": "world"},
    )

    assert result == ScopeweaveImportResult(
        work_item_id="WI-42",
        work_item_url="https://scopeweave.example.com/w/WI-42",
        status_code=201,
    )
    assert mock_route.called
    assert mock_route.calls.last.request.headers["authorization"] == "Bearer pat-secret"

@pytest.mark.asyncio
@respx.mock
async def test_push_work_item_error_status(monkeypatch):
    import services.scopeweave_client as scopeweave_client
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )

    respx.post("https://scopeweave.example.com/api/imports/work-items").mock(
        return_value=httpx.Response(
            400,
            json={"error": "bad request"}
        )
    )

    with pytest.raises(ScopeweavePushError, match="scopeweave import rejected the work item"):
        await push_work_item(
            base_url="https://scopeweave.example.com",
            access_token="pat-secret",
            payload={"hello": "world"},
        )

@pytest.mark.asyncio
@respx.mock
async def test_push_work_item_transport_error(monkeypatch):
    import services.scopeweave_client as scopeweave_client
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )

    respx.post("https://scopeweave.example.com/api/imports/work-items").mock(
        side_effect=httpx.ConnectError("Connection failed")
    )

    with pytest.raises(ScopeweavePushError, match="scopeweave import request failed"):
        await push_work_item(
            base_url="https://scopeweave.example.com",
            access_token="pat-secret",
            payload={"hello": "world"},
        )
