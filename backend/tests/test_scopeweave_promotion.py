import httpx
import pytest

import api.projects as projects_api
import services.scopeweave_client as scopeweave_client
import services.scopeweave_promotion as scopeweave_promotion
from core.url_validation import ValidatedHTTPSURLHost
from db.models import ScopeweavePromotionLink, ScopeweavePromotionTarget
from db.session import get_db
from main import app
from services.project_graph.project_registration import (
    ProjectCitation,
    ProjectEvidence,
    ProjectGraphNotFoundError,
    ProjectGraphQueryScope,
)
from services.scopeweave_client import (
    ScopeweaveConfigError,
    ScopeweaveImportResult,
    ScopeweavePushError,
)
from services.scopeweave_promotion import (
    ScopeweaveNotConfiguredError,
    ScopeweavePromotionOutcome,
    build_import_payload,
    promote_project_object,
)


def _evidence() -> ProjectEvidence:
    return ProjectEvidence(
        project_uid="project_candidate:demo",
        object_uid="issue:demo",
        object_type="issue",
        title="결제 실패 재현 필요",
        summary="결제 승인 단계에서 간헐적 오류가 보고됨",
        status_code="confirmed",
        confidence=0.82,
        citation_bundle=(
            ProjectCitation(
                content_segment_uid="seg-1",
                source_kind="email_body",
                source_record_uid="<thread-9@example.com>",
                heading_path="Issues",
                segment_path="/document[1]/paragraph[3]",
                ordinal_index=3,
                safe_text_excerpt="결제 승인 오류 근거 문단",
            ),
        ),
    )


def _validated_host() -> ValidatedHTTPSURLHost:
    return ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com",
        hostname="scopeweave.example.com",
        port=443,
        addresses=("203.0.113.10",),
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.requests: list[dict] = []
        self.closed = False

    async def post(self, url, *, json, headers, timeout):
        self.requests.append(
            {"url": url, "json": json, "headers": headers, "timeout": timeout}
        )
        return self._response

    async def aclose(self):
        self.closed = True


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, _statement):
        return _FakeResult(self._results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _scope() -> ProjectGraphQueryScope:
    return ProjectGraphQueryScope(
        user_id="promoter",
        organization_id="org-1",
        workspace_id="workspace-org-1",
    )


def _target() -> ScopeweavePromotionTarget:
    return ScopeweavePromotionTarget(
        user_id="promoter",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        base_url="https://scopeweave.example.com",
        access_token="pat-secret",
        is_active=True,
    )


def test_build_import_payload_carries_citations():
    payload = build_import_payload(_evidence())

    assert payload["source_system"] == "naruon"
    assert payload["external_ref"] == {
        "project_uid": "project_candidate:demo",
        "object_uid": "issue:demo",
    }
    assert payload["work_item"]["object_type"] == "issue"
    assert payload["work_item"]["confidence"] == 0.82
    assert len(payload["citations"]) == 1
    citation = payload["citations"][0]
    assert citation["content_segment_uid"] == "seg-1"
    assert citation["source_record_uid"] == "<thread-9@example.com>"


def test_validate_base_url_requires_configured_allowlist(monkeypatch):
    monkeypatch.setattr(scopeweave_client.settings, "ALLOWED_SCOPEWEAVE_HOSTS", "")
    with pytest.raises(ScopeweaveConfigError):
        scopeweave_client.validate_scopeweave_base_url(
            "https://scopeweave.example.com"
        )


def test_validate_base_url_rejects_non_allowlisted_host(monkeypatch):
    monkeypatch.setattr(
        scopeweave_client.settings,
        "ALLOWED_SCOPEWEAVE_HOSTS",
        "scopeweave.example.com",
    )
    with pytest.raises(ScopeweaveConfigError):
        scopeweave_client.validate_scopeweave_base_url("https://evil.example.net")


def test_validate_base_url_rejects_http_scheme(monkeypatch):
    monkeypatch.setattr(
        scopeweave_client.settings,
        "ALLOWED_SCOPEWEAVE_HOSTS",
        "scopeweave.example.com",
    )
    with pytest.raises(ScopeweaveConfigError):
        scopeweave_client.validate_scopeweave_base_url(
            "http://scopeweave.example.com"
        )


@pytest.mark.asyncio
async def test_push_work_item_posts_bearer_payload(monkeypatch):
    fake_client = _FakeAsyncClient(
        _FakeResponse(
            201,
            {
                "work_item_id": "WI-42",
                "work_item_url": "https://scopeweave.example.com/w/WI-42",
            },
        )
    )
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )
    monkeypatch.setattr(
        scopeweave_client,
        "build_pinned_https_async_client",
        lambda *_args: fake_client,
    )

    result = await scopeweave_client.push_work_item(
        base_url="https://scopeweave.example.com",
        access_token="pat-secret",
        payload={"hello": "world"},
    )

    assert result == ScopeweaveImportResult(
        work_item_id="WI-42",
        work_item_url="https://scopeweave.example.com/w/WI-42",
        status_code=201,
    )
    assert fake_client.closed is True
    sent = fake_client.requests[0]
    assert sent["url"] == (
        "https://scopeweave.example.com/api/imports/work-items"
    )
    assert sent["headers"]["authorization"] == "Bearer pat-secret"
    assert sent["json"] == {"hello": "world"}


@pytest.mark.asyncio
async def test_push_work_item_raises_on_error_status(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse(422, {"detail": "bad"}))
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )
    monkeypatch.setattr(
        scopeweave_client,
        "build_pinned_https_async_client",
        lambda *_args: fake_client,
    )

    with pytest.raises(ScopeweavePushError):
        await scopeweave_client.push_work_item(
            base_url="https://scopeweave.example.com",
            access_token="pat-secret",
            payload={},
        )
    assert fake_client.closed is True


@pytest.mark.asyncio
async def test_promote_degrades_when_not_configured():
    session = _FakeSession([None])
    with pytest.raises(ScopeweaveNotConfiguredError):
        await promote_project_object(
            session,
            scope=_scope(),
            project_uid="project_candidate:demo",
            object_uid="issue:demo",
            actor_user_id="promoter",
        )
    assert session.added == []


@pytest.mark.asyncio
async def test_promote_pushes_and_persists_mapping(monkeypatch):
    # results: 1) active target lookup, 2) existing link lookup (none)
    session = _FakeSession([_target(), None])

    async def fake_get_evidence(_session, *, scope, project_uid, object_uid):
        return _evidence()

    async def fake_push(*, base_url, access_token, payload):
        assert base_url == "https://scopeweave.example.com"
        assert access_token == "pat-secret"
        assert payload["external_ref"]["object_uid"] == "issue:demo"
        return ScopeweaveImportResult(
            work_item_id="WI-7",
            work_item_url="https://scopeweave.example.com/w/WI-7",
            status_code=201,
        )

    monkeypatch.setattr(
        scopeweave_promotion, "get_project_evidence", fake_get_evidence
    )
    monkeypatch.setattr(scopeweave_promotion, "push_work_item", fake_push)

    outcome = await promote_project_object(
        session,
        scope=_scope(),
        project_uid="project_candidate:demo",
        object_uid="issue:demo",
        actor_user_id="promoter",
    )

    assert outcome.created is True
    assert outcome.scopeweave_work_item_id == "WI-7"
    assert outcome.citation_count == 1
    assert len(session.added) == 1
    link = session.added[0]
    assert isinstance(link, ScopeweavePromotionLink)
    assert link.object_uid == "issue:demo"
    assert link.scopeweave_work_item_id == "WI-7"
    assert link.promoted_confidence == 0.82


@pytest.mark.asyncio
async def test_promote_updates_existing_mapping(monkeypatch):
    existing = ScopeweavePromotionLink(
        user_id="promoter",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        project_uid="project_candidate:demo",
        object_uid="issue:demo",
        object_type="issue",
        scopeweave_work_item_id="WI-old",
        scopeweave_work_item_url=None,
        promoted_confidence=0.1,
        citation_count=0,
        promoted_by_user_id="promoter",
    )
    session = _FakeSession([_target(), existing])

    async def fake_get_evidence(_session, *, scope, project_uid, object_uid):
        return _evidence()

    async def fake_push(*, base_url, access_token, payload):
        return ScopeweaveImportResult(
            work_item_id="WI-new",
            work_item_url="https://scopeweave.example.com/w/WI-new",
            status_code=200,
        )

    monkeypatch.setattr(
        scopeweave_promotion, "get_project_evidence", fake_get_evidence
    )
    monkeypatch.setattr(scopeweave_promotion, "push_work_item", fake_push)

    outcome = await promote_project_object(
        session,
        scope=_scope(),
        project_uid="project_candidate:demo",
        object_uid="issue:demo",
        actor_user_id="promoter",
    )

    assert outcome.created is False
    assert session.added == []
    assert existing.scopeweave_work_item_id == "WI-new"
    assert existing.promoted_confidence == 0.82


# --- API endpoint tests (mocked service) ---


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={
            "X-User-Id": "promoter",
            "X-Organization-Id": "org-1",
            "X-User-Role": "member",
        },
    )


@pytest.fixture
def _override_db():
    async def override_get_db():
        yield _FakeSession([])

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_promote_endpoint_returns_200(
    dev_auth_dependency_overrides, _override_db, monkeypatch
):
    async def fake_promote(session, *, scope, project_uid, object_uid, actor_user_id):
        assert project_uid == "project_candidate:demo"
        assert object_uid == "issue:demo"
        return ScopeweavePromotionOutcome(
            project_uid=project_uid,
            object_uid=object_uid,
            object_type="issue",
            scopeweave_work_item_id="WI-99",
            scopeweave_work_item_url="https://scopeweave.example.com/w/WI-99",
            promoted_confidence=0.82,
            citation_count=1,
            created=True,
        )

    monkeypatch.setattr(projects_api, "promote_project_object", fake_promote)

    async with _client() as client:
        response = await client.post(
            "/api/projects/project_candidate:demo/promote",
            json={"object_uid": "issue:demo"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scopeweave_work_item_id"] == "WI-99"
    assert body["created"] is True
    assert body["citation_count"] == 1


@pytest.mark.asyncio
async def test_promote_endpoint_returns_409_when_unconfigured(
    dev_auth_dependency_overrides, _override_db, monkeypatch
):
    async def fake_promote(*_args, **_kwargs):
        raise ScopeweaveNotConfiguredError("not configured")

    monkeypatch.setattr(projects_api, "promote_project_object", fake_promote)

    async with _client() as client:
        response = await client.post(
            "/api/projects/project_candidate:demo/promote",
            json={"object_uid": "issue:demo"},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_promote_endpoint_returns_404_when_object_missing(
    dev_auth_dependency_overrides, _override_db, monkeypatch
):
    async def fake_promote(*_args, **_kwargs):
        raise ProjectGraphNotFoundError("missing")

    monkeypatch.setattr(projects_api, "promote_project_object", fake_promote)

    async with _client() as client:
        response = await client.post(
            "/api/projects/project_candidate:demo/promote",
            json={"object_uid": "issue:demo"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_promote_endpoint_returns_502_on_push_failure(
    dev_auth_dependency_overrides, _override_db, monkeypatch
):
    async def fake_promote(*_args, **_kwargs):
        raise ScopeweavePushError("scopeweave import request failed")

    monkeypatch.setattr(projects_api, "promote_project_object", fake_promote)

    async with _client() as client:
        response = await client.post(
            "/api/projects/project_candidate:demo/promote",
            json={"object_uid": "issue:demo"},
        )

    assert response.status_code == 502
