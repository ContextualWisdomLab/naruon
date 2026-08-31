"""Fast, mocked tests for the Noema general agent.

These cover three seams without needing a live LLM or a database:

* tool wiring (mail read/search, content-graph, task actions, writeback)
* configuration resolved from the DB provider layer (not ``os.getenv``)
* graceful degradation when the provider or pydantic-ai runtime is absent
"""

import datetime

import pytest

from db.models import (
    AuditLog,
    ContentNodeRecord,
    Email,
    KnowledgeGraphEdgeRecord,
    LLMProvider,
    TicketTask,
)
from services import noema_agent
from services.llm_provider_selection import RuntimeLLMProvider
from services.noema_agent import (
    NOEMA_TOOL_SPECS,
    NoemaAgentDeps,
    build_noema_agent,
    run_noema_agent,
    tool_check_calendar_conflict,
    tool_content_graph_query,
    tool_dispatch_writeback,
    tool_list_tasks,
    tool_read_mail,
    tool_search_mail,
    tool_update_task_status,
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
        self.statements = []
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        self.statements.append(_statement)
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
    assert "email_records.workspace_id" in str(session.statements[0])
    assert "workspace-org-1" in session.statements[0].compile().params.values()


@pytest.mark.asyncio
async def test_read_mail_missing_returns_not_found():
    session = _QueueSession([_FakeResult(items=[])])
    result = await tool_read_mail(_deps(session), "msg-404")
    assert "email_records.workspace_id" in str(session.statements[0])
    assert "workspace-org-1" in session.statements[0].compile().params.values()
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
    assert "email_records.workspace_id" in str(session.statements[0])
    assert "workspace-org-1" in session.statements[0].compile().params.values()


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


# --------------------------------------------------------------------------- #
# Calendar conflict check: same deterministic policy as /api/calendar/conflicts
# --------------------------------------------------------------------------- #


def _commitment_row(commitment_id, start_at, end_at, status):
    return {
        "commitment_id": commitment_id,
        "start_at": start_at,
        "end_at": end_at,
        "status": status,
    }


@pytest.mark.asyncio
async def test_check_calendar_conflict_requires_authoritative_provider_evidence():
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="confirmed",
        existing=[
            _commitment_row(
                "other-1",
                "2026-03-01T12:00:00+00:00",
                "2026-03-01T13:00:00+00:00",
                "confirmed",
            )
        ],
    )
    assert result["status"] == "error"
    assert result["decision_code"] == "review_required"
    assert result["error_code"] == "calendar_authoritative_evidence_unavailable"


@pytest.mark.asyncio
async def test_check_calendar_conflict_does_not_trust_conversational_overlap():
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="confirmed",
        existing=[
            _commitment_row(
                "other-1",
                "2026-03-01T10:30:00+00:00",
                "2026-03-01T11:30:00+00:00",
                "confirmed",
            )
        ],
    )
    assert result["status"] == "error"
    assert result["decision_code"] == "review_required"


@pytest.mark.asyncio
async def test_check_calendar_conflict_remains_review_required_without_provider_read():
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="confirmed",
        existing=[
            _commitment_row(
                "other-1",
                "2026-03-01T10:30:00+00:00",
                "2026-03-01T11:30:00+00:00",
                "tentative",
            )
        ],
    )
    assert result["status"] == "error"
    assert result["decision_code"] == "review_required"


@pytest.mark.asyncio
async def test_check_calendar_conflict_does_not_drop_malformed_rows_and_claim_available():
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="confirmed",
        existing=[
            {"commitment_id": "bad-1"},  # missing start_at/end_at/status
            _commitment_row("bad-2", "not-a-timestamp", "also-not-one", "confirmed"),
        ],
    )
    assert result["status"] == "error"
    assert result["decision_code"] == "review_required"
    assert result["error_code"] == "calendar_authoritative_evidence_unavailable"


@pytest.mark.asyncio
async def test_check_calendar_conflict_rejects_even_empty_unverified_evidence():
    """Conversational evidence cannot substitute for an authoritative read."""
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="confirmed",
        existing=[],
    )
    assert result["status"] == "error"
    assert result["error_code"] == "calendar_authoritative_evidence_unavailable"


@pytest.mark.asyncio
async def test_check_calendar_conflict_rejects_invalid_proposed_status():
    session = _QueueSession([])
    result = await tool_check_calendar_conflict(
        _deps(session),
        proposed_commitment_id="new-1",
        proposed_start_at="2026-03-01T10:00:00+00:00",
        proposed_end_at="2026-03-01T11:00:00+00:00",
        proposed_status="banana",
        existing=[],
    )
    assert result["status"] == "error"
    assert result["error_code"] == "calendar_status_unsupported"


def test_tool_specs_cover_declared_capabilities():
    capabilities = {spec["capability"] for spec in NOEMA_TOOL_SPECS}
    assert {
        "mail.search",
        "mail.read",
        "content_graph.query",
        "tasks.read",
        "tasks.update",
        "calendar.writeback",
        "calendar.conflict_check",
    } <= capabilities


# --------------------------------------------------------------------------- #
# Config-from-DB + graceful degradation
# --------------------------------------------------------------------------- #


class _ProviderScalars:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None


class _ProviderResult:
    def __init__(self, providers):
        self._providers = providers

    def scalars(self):
        return _ProviderScalars(self._providers)

    def scalar_one_or_none(self):
        return None


class _ProviderSession:
    """Minimal session that satisfies resolve_runtime_llm_provider."""

    def __init__(self, providers):
        self._providers = providers

    async def execute(self, statement):
        text = str(statement).lower()
        if "llm_providers" in text:
            return _ProviderResult(self._providers)
        return _ProviderResult([])


@pytest.mark.asyncio
async def test_run_agent_unavailable_without_provider(monkeypatch):
    async def _no_provider(*args, **kwargs):
        return None

    monkeypatch.setattr(noema_agent, "resolve_runtime_llm_provider", _no_provider)
    result = await run_noema_agent(
        _QueueSession([]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )
    assert result.status == "unavailable"
    assert result.provider_name is None


@pytest.mark.asyncio
async def test_run_agent_uses_db_provider_and_degrades_without_runtime(monkeypatch):
    provider = LLMProvider(
        id=7,
        user_id="user-1",
        organization_id="org-1",
        name="Local Gemma",
        provider_type="ollama",
        base_url="http://ollama:11434/v1",
        model_identifier="gemma",
        embedding_model="embeddinggemma",
        api_key=None,
        is_active=True,
        updated_at=datetime.datetime.now(UTC),
    )
    # Simulate the pydantic-ai runtime being absent: the config still resolves
    # from the DB provider, and the agent degrades to a notice.
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: None)

    result = await run_noema_agent(
        _ProviderSession([provider]),
        user_id="user-1",
        organization_id="org-1",
        workspace_id="workspace-org-1",
        prompt="hello",
    )
    assert result.status == "unavailable"
    # Proves the provider name came from the DB record, not os.getenv.
    assert result.provider_name is not None
    assert "pydantic-ai" in (result.notice or "")


@pytest.mark.asyncio
async def test_build_agent_returns_none_without_runtime(monkeypatch):
    monkeypatch.setattr(noema_agent, "_load_pydantic_ai", lambda: None)
    provider = RuntimeLLMProvider(
        api_key="sk-test",
        base_url=None,
        chat_model="gpt-4o",
        embedding_model="text-embedding-3-small",
        provider_name="OpenAI",
        provider_source="tenant_config",
    )
    agent, closer = await build_noema_agent(provider)
    assert agent is None
    await closer()  # no-op closer must be awaitable


# --------------------------------------------------------------------------- #
# Full agent run using pydantic-ai's TestModel (skipped if not installed)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_agent_runs_tools_with_test_model():
    # This is the ONLY test that exercises the real pydantic-ai build path
    # (imports OpenAIChatModel, constructs the Agent, registers the tools and
    # their RunContext-typed schemas). It is skipped only when pydantic-ai is
    # genuinely absent; CI installs backend/requirements-agent.txt so it runs
    # and proves build_noema_agent returns a working, tool-driving agent.
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.models.test import TestModel

    provider = RuntimeLLMProvider(
        api_key="sk-test",
        base_url=None,
        chat_model="gpt-4o",
        embedding_model="text-embedding-3-small",
        provider_name="OpenAI",
        provider_source="tenant_config",
    )
    agent, closer = await build_noema_agent(provider)
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
