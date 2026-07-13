"""Tests for the workspace agent registry loader."""

from services.agent_registry import (
    clear_registry_cache,
    get_registered_agent,
    load_registered_agents,
    load_task_agent_mapping,
    resolve_agent_for_task,
)


def setup_function() -> None:
    clear_registry_cache()


def teardown_function() -> None:
    clear_registry_cache()


def test_noema_agent_is_registered():
    agents = load_registered_agents()
    assert "noema-general-agent" in agents

    agent = get_registered_agent("noema-general-agent")
    assert agent is not None
    assert agent.framework == "pydantic-ai"
    assert agent.entrypoint == "services.noema_agent:run_noema_agent"
    assert agent.enabled is True
    assert agent.degrades_gracefully is True
    # The opt-in + audit-logged writeback contract is declared in the catalog.
    assert agent.writeback_opt_in is True
    assert agent.writeback_audit_logged is True
    assert "mail.search" in agent.capabilities
    assert "calendar.writeback" in agent.capabilities


def test_task_mapping_resolves_to_noema_agent():
    mapping = load_task_agent_mapping()
    assert mapping.get("general") == "noema-general-agent"

    agent = resolve_agent_for_task("mail.triage")
    assert agent is not None
    assert agent.agent_id == "noema-general-agent"


def test_unknown_task_type_resolves_to_none():
    assert resolve_agent_for_task("does-not-exist") is None
