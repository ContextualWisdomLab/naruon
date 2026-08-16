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


def test_noema_agent_is_registered_as_decision_agent():
    agents = load_registered_agents()
    assert "noema-general-agent" in agents

    agent = get_registered_agent("noema-general-agent")
    assert agent is not None
    assert agent.agent_role == "decision"
    assert agent.framework == "pydantic-ai"
    assert agent.entrypoint == "services.noema_agent:run_noema_agent"
    assert agent.enabled is True
    assert agent.degrades_gracefully is True
    assert agent.provider_source == "contextual-orchestrator"
    assert agent.model_alias == "contextual-orchestrator"
    assert agent.sequential_failover is False
    # The opt-in + audit-logged writeback contract is declared in the catalog.
    assert agent.writeback_opt_in is True
    assert agent.writeback_audit_logged is True
    assert "judgment.decide" in agent.capabilities
    assert "mail.search" in agent.capabilities
    assert "calendar.writeback" in agent.capabilities


def test_task_mapping_resolves_judgments_to_noema_agent():
    mapping = load_task_agent_mapping()
    assert mapping.get("general") == "noema-general-agent"
    assert mapping.get("judgment.decide") == "noema-general-agent"

    for task_type in (
        "mail.triage",
        "mail.search",
        "tasks.followup",
        "calendar.writeback",
        "judgment.decide",
    ):
        agent = resolve_agent_for_task(task_type)
        assert agent is not None
        assert agent.agent_id == "noema-general-agent"
        assert agent.agent_role == "decision"
        assert agent.model_alias == "contextual-orchestrator"
        assert agent.sequential_failover is False


def test_unknown_task_type_resolves_to_none():
    assert resolve_agent_for_task("does-not-exist") is None
