"""Fast, mocked tests for the Noema general agent.

These cover the seams without needing a live LLM or a database:

* tool wiring (mail read/search, content-graph, task actions, writeback)
* LLM calls go only to the contextual-orchestrator gateway (KV token, not env)
* no sequential model list / provider-key failover
* graceful degradation when the gateway or pydantic-ai runtime is absent
"""

import datetime
from pathlib import Path

import pytest

from db.models import (
    AuditLog,
    ContentNodeRecord,
    Email,
    KnowledgeGraphEdgeRecord,
    TicketTask,
)
from services import noema_agent
from services.noema_agent import (
    NOEMA_TOOL_SPECS,
    NoemaAgentDeps,
    build_noema_agent,
    run_noema_agent,
    tool_content_graph_query,
    tool_dispatch_writeback,
    tool_list_tasks,
    tool_read_mail,
    tool_search_mail,
    tool_update_task_status,
)
from services.orchestrator_gateway import (
    ORCHESTRATOR_MODEL_ALIAS,
    OrchestratorGateway,
)

UTC = datetime.timezone.utc


class _FakeScalars:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items=None, scalar=None):
        self._items = list(items or [])
        self._scalar = scalar

    def scalars(self):
        return _FakeScalars(self._items)

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar


class _QueueSession:
    """Async session stub that returns queued results in execute() order."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        if not self._results:
            return _FakeResult()
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def _deps(session, **kwargs):
    params = {
        "session": session,
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "workspace-org-1",
    }
    params.update(kwargs)
    return NoemaAgentDeps(**params)


def _email(**overrides):
    values = {
        "id": 1,
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "subject": "Quarterly plan",
        "sender": "boss@company.com",
        "recipients": "me@company.com",
        "body": "Please review the quarterly plan and confirm the budget.",
        "date": datetime.datetime(2026, 1, 2, tzinfo=UTC),
    }
    values.update(overrides)
    return Email(**values)


# --------------------------------------------------------------------------- #
# Tool wiring
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_search_mail_returns_owner_scoped_snippets():
    session = _QueueSession([_FakeResult(items=[_email()])])
    results = await tool_search_mail(_deps(session), "budget", limit=5)
    assert len(results) == 1
    assert results[0]["message_id"] == "msg-1"
    assert "budget" in results[0]["snippet"]


@pytest.mark.asyncio
async def test_read_mail_missing_returns_not_found():
    session = _QueueSession([_FakeResult(items=[])])
    result = await tool_read_mail(_deps(session), "msg-404")
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_read_mail_returns_body():
    session = _QueueSession([_FakeResult(items=[_email()])])
    result = await tool_read_mail(_deps(session), "msg-1")
    assert result["status"] == "ok"
    assert result["subject"] == "Quarterly plan"
    assert "quarterly plan" in result["body"].lower()


@pytest.mark.asyncio
async def test_content_graph_query_returns_nodes_and_edges():
    node = ContentNodeRecord(
        content_node_uid="node-1",
        email_id=1,
        source_kind="body",
        source_record_uid="rec-1",
        node_kind="paragraph",
        node_path="/document/p1",
        ordinal_index=0,
        display_label="Intro",
        safe_text_content="Please review the quarterly plan.",
        content_hash="hash-1",
    )
    edge = KnowledgeGraphEdgeRecord(
        edge_uid="edge-1",
        email_id=1,
        source_kind="body",
        source_record_uid="rec-1",
        edge_kind="mentions",
        ordinal_index=0,
    )
    session = _QueueSession(
        [
            _FakeResult(scalar=1),  # email id lookup
            _FakeResult(items=[node]),  # content nodes
            _FakeResult(items=[edge]),  # edges
        ]
    )
    result = await tool_content_graph_query(_deps(session), "msg-1")
    assert result["status"] == "ok"
    assert result["nodes"][0]["uid"] == "node-1"
    assert result["edges"][0]["kind"] == "mentions"


@pytest.mark.asyncio
async def test_content_graph_query_unknown_email():
    session = _QueueSession([_FakeResult(scalar=None)])
    result = await tool_content_graph_query(_deps(session), "msg-404")
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_list_tasks_maps_rows():
    task = TicketTask(
        task_uid="task-1",
        user_id="user-1",
        organization_id="org-1",
        title="Confirm budget",
        status="open",
        priority="high",
        source_type="email",
    )
    session = _QueueSession([_FakeResult(items=[task])])
    results = await tool_list_tasks(_deps(session), status="open")
    assert results == [
        {
            "task_uid": "task-1",
            "title": "Confirm budget",
            "status": "open",
            "priority": "high",
            "source_type": "email",
        }
    ]


@pytest.mark.asyncio
async def test_update_task_status_writes_audit_log():
    task = TicketTask(
        task_uid="task-1",
        user_id="user-1",
        organization_id="org-1",
        title="Confirm budget",
        status="open",
        priority="high",
        source_type="email",
    )
    session = _QueueSession([_FakeResult(items=[task])])
    result = await tool_update_task_status(_deps(session), "task-1", "done")
    assert result["status"] == "ok"
    assert task.status == "done"
    audit_rows = [obj for obj in session.added if isinstance(obj, AuditLog)]
    assert len(audit_rows) == 1
    assert audit_rows[0].resource_type == "ticket_task"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_update_task_status_rejects_unknown_status():
    session = _QueueSession([])
    result = await tool_update_task_status(_deps(session), "task-1", "banana")
    assert result["status"] == "error"
    assert session.commits == 0
    assert session.added == []


# --------------------------------------------------------------------------- #
# Writeback: opt-in + audit contract
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_writeback_skipped_when_not_opted_in():
    dispatched = []

    async def dispatcher(org, workspace, command):
        dispatched.append(command)
        return {"provider_write_executed": True}

    session = _QueueSession([])
    deps = _deps(session, writeback_enabled=False, dispatcher=dispatcher)
    result = await tool_dispatch_writeback(
        deps, "write_caldav", "acct", "/Naruon/Calendar/x.ics", "BEGIN:VCALENDAR"
    )
    assert result["status"] == "skipped"
    assert result["provider_write_executed"] is False
    assert dispatched == []  # runner never contacted
    assert session.added == []  # no audit side effect


@pytest.mark.asyncio
async def test_writeback_dispatches_and_audits_when_opted_in():
    seen = {}

    async def dispatcher(org, workspace, command):
        seen["org"] = org
        seen["command"] = command
        return {"provider_write_executed": True}

    session = _QueueSession([])
    deps = _deps(session, writeback_enabled=True, dispatcher=dispatcher)
    result = await tool_dispatch_writeback(
        deps, "write_caldav", "acct", "/Naruon/Calendar/x.ics", "BEGIN:VCALENDAR"
    )
    assert result["status"] == "ok"
    assert result["provider_write_executed"] is True
    assert seen["org"] == "org-1"
    assert seen["command"]["action"] == "write_caldav"
    audit_rows = [obj for obj in session.added if isinstance(obj, AuditLog)]
    assert len(audit_rows) == 1
    assert audit_rows[0].action == "writeback_executed"
    assert audit_rows[0].resource_type == "runner_writeback"


@pytest.mark.asyncio
async def test_writeback_rejects_unknown_action():
    session = _QueueSession([])
    deps = _deps(session, writeback_enabled=True)
    result = await tool_dispatch_writeback(deps, "delete_everything", "acct", "/x", "")
    assert result["status"] == "error"


def test_tool_specs_cover_declared_capabilities():
    capabilities = {spec["capability"] for spec in NOEMA_TOOL_SPECS}
    assert {
        "mail.search",
        "mail.read",
        "content_graph.query",
        "tasks.read",
        "tasks.update",
        "calendar.writeback",
    } <= capabilities


# --------------------------------------------------------------------------- #
# Orchestrator gateway + graceful degradation
# --------------------------------------------------------------------------- #


def _gateway() -> OrchestratorGateway:
    return OrchestratorGateway(
        inference_token="naruon-orch-inference-token",
        base_url="https://orchestrator.example/v1",
    )


@pytest.mark.asyncio
async def test_run_agent_unavailable_without_orchestrator_gateway(monkeypatch):
    async def _no_gateway(*args, **kwargs):
        return None

    monkeypatch.setattr(noema_agent, "resolve_orchestrator_gateway", _no_gateway)
    result = await run_noema_agent(
        _QueueSession([]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )
    assert result.status == "unavailable"
    assert result.error_code == "orchestrator_gateway_unavailable"
    assert result.provider_name is None
    assert result.model_alias is None


@pytest.mark.asyncio
async def test_run_agent_uses_orchestrator_gateway_and_degrades_without_runtime(
    monkeypatch,
):
    async def _gateway_from_kv(*args, **kwargs):
        return _gateway()

    monkeypatch.setattr(noema_agent, "resolve_orchestrator_gateway", _gateway_from_kv)
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: None)

    result = await run_noema_agent(
        _QueueSession([]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )
    assert result.status == "unavailable"
    assert result.provider_name == ORCHESTRATOR_MODEL_ALIAS
    assert result.model_alias == ORCHESTRATOR_MODEL_ALIAS
    assert "pydantic-ai" in (result.notice or "")


@pytest.mark.asyncio
async def test_run_agent_uses_single_orchestrator_alias(monkeypatch):
    captured: dict[str, object] = {}

    async def _gateway_from_kv(*args, **kwargs):
        return _gateway()

    async def _fake_build(gateway):
        captured["gateway"] = gateway

        class _Agent:
            async def run(self, prompt, deps):
                captured["prompt"] = prompt
                return type("Result", (), {"output": "Hold the reply until Friday."})()

        async def _closer() -> None:
            return None

        return _Agent(), _closer

    monkeypatch.setattr(noema_agent, "resolve_orchestrator_gateway", _gateway_from_kv)
    monkeypatch.setattr(noema_agent, "build_noema_agent", _fake_build)

    result = await run_noema_agent(
        _QueueSession([]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="Should I reply today?",
    )
    assert result.status == "ok"
    assert result.output == "Hold the reply until Friday."
    assert result.model_alias == "contextual-orchestrator"
    assert result.error_code is None
    gateway = captured["gateway"]
    assert isinstance(gateway, OrchestratorGateway)
    assert gateway.model_alias == "contextual-orchestrator"
    assert gateway.model_candidates == ()
    assert gateway.inference_token == "naruon-orch-inference-token"
    assert gateway.base_url == "https://orchestrator.example/v1"


@pytest.mark.asyncio
async def test_build_agent_targets_orchestrator_alias_only(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, api_key, base_url, http_client=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url

        async def close(self):
            return None

    class _FakeChatModel:
        def __init__(self, model_name, provider=None):
            captured["model_name"] = model_name
            captured["provider"] = provider

    class _FakeProvider:
        def __init__(self, openai_client=None):
            captured["openai_client"] = openai_client

    class _FakeAgent:
        def __init__(self, model, deps_type=None, system_prompt=None):
            captured["system_prompt"] = system_prompt
            self.tools = []

        def tool(self, fn):
            self.tools.append(fn.__name__)
            return fn

    async def _fake_http_client(base_url):
        captured["validated_base_url"] = base_url
        return base_url, object()

    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: {
        "Agent": _FakeAgent,
        "RunContext": object,
        "OpenAIChatModel": _FakeChatModel,
        "OpenAIProvider": _FakeProvider,
    })
    monkeypatch.setattr(noema_agent, "AsyncOpenAI", _FakeOpenAI)
    monkeypatch.setattr(noema_agent, "build_llm_provider_http_client", _fake_http_client)

    agent, closer = await build_noema_agent(_gateway())
    assert agent is not None
    assert captured["api_key"] == "naruon-orch-inference-token"
    assert captured["base_url"] == "https://orchestrator.example/v1"
    assert captured["model_name"] == "contextual-orchestrator"
    assert captured["model_name"] != "gpt-4o"
    assert "chat_model" not in captured
    await closer()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["rejected", "missing"])
async def test_run_agent_fails_closed_for_invalid_gateway_client(
    monkeypatch, failure_mode
):
    class _FakeClient:
        def __init__(self):
            self.closed = False

        async def aclose(self):
            self.closed = True

    client = _FakeClient()

    async def _gateway_from_kv(*args, **kwargs):
        return _gateway()

    async def _invalid_http_client(base_url):
        if failure_mode == "rejected":
            raise ValueError("rejected")
        return None, client

    monkeypatch.setattr(noema_agent, "resolve_orchestrator_gateway", _gateway_from_kv)
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: {})
    monkeypatch.setattr(
        noema_agent, "build_llm_provider_http_client", _invalid_http_client
    )
    monkeypatch.setattr(
        noema_agent,
        "AsyncOpenAI",
        lambda **kwargs: pytest.fail("rejected gateway must not build AsyncOpenAI"),
    )

    result = await run_noema_agent(
        _QueueSession([]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )

    assert result.status == "unavailable"
    assert result.error_code == "orchestrator_gateway_unavailable"
    assert result.model_alias == ORCHESTRATOR_MODEL_ALIAS
    assert client.closed is (failure_mode == "missing")


@pytest.mark.asyncio
async def test_build_agent_returns_none_without_runtime(monkeypatch):
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: None)
    agent, closer = await build_noema_agent(_gateway())
    assert agent is None
    await closer()  # no-op closer must be awaitable


# --------------------------------------------------------------------------- #
# Full agent run using pydantic-ai's TestModel (skipped if not installed)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_agent_runs_tools_with_test_model(monkeypatch):
    # This is the ONLY test that exercises the real pydantic-ai build path
    # (imports OpenAIChatModel, constructs the Agent, registers the tools and
    # their RunContext-typed schemas). It is skipped only when pydantic-ai is
    # genuinely absent; CI installs backend/requirements-agent.txt so it runs
    # and proves build_noema_agent returns a working, tool-driving agent.
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.models.test import TestModel

    async def _fake_http_client(base_url):
        return base_url, None

    monkeypatch.setattr(noema_agent, "build_llm_provider_http_client", _fake_http_client)
    agent, closer = await build_noema_agent(_gateway())
    # A real Agent must be built — not the graceful-degradation None.
    assert agent is not None
    assert isinstance(agent, PydanticAgent)

    session = _QueueSession([])  # every execute yields an empty result
    deps = _deps(session, writeback_enabled=False)
    try:
        with agent.override(model=TestModel()):
            result = await agent.run("Summarize my mail", deps=deps)
    finally:
        await closer()

    # TestModel exercises each registered tool once, so every declared tool
    # name must show up in the recorded call log (proves the RunContext-typed
    # tool schemas resolved and wired end to end).
    expected_tools = {spec["name"] for spec in NOEMA_TOOL_SPECS}
    assert expected_tools <= set(deps.tool_calls)
    assert getattr(result, "output", None) is not None


def test_noema_agent_source_does_not_import_tenant_llm_provider():
    """Unique slice: Noema's LLM client is orchestrator-only.

    ``resolve_runtime_llm_provider`` remains for search / chat / embeddings.
    This file must not import that resolver or ``llm_provider_selection``.
    """
    source = Path(noema_agent.__file__).read_text(encoding="utf-8")
    assert "llm_provider_selection" not in source
    assert "resolve_runtime_llm_provider" not in source
    assert "RuntimeLLMProvider" not in source
    assert "model_profile_id" not in source
    assert "contextual_orchestrator_client" not in source
    assert "gpt-4o" not in source
    assert "from services.orchestrator_gateway import" in source
    assert "run_noema_decision" not in source
    assert "COPILOT_GITHUB_TOKEN" not in source
    assert "models.github.ai" not in source
    assert "api.githubcopilot.com" not in source
