"""Tests for the workspace agent registry loader."""

import services.agent_registry as agent_registry_module
from services.agent_registry import (
    clear_registry_cache,
    get_registered_agent,
    load_registered_agents,
    load_task_agent_mapping,
    resolve_agent_for_task,
)


def setup_function() -> None:
    """Clear cached registry state before each test."""
    clear_registry_cache()


def teardown_function() -> None:
    """Clear cached registry state after each test."""
    clear_registry_cache()


def test_noema_agent_is_registered() -> None:
    """Expose semantically specific agent attributes from the owned registry."""
    agents = load_registered_agents()
    assert "noema-general-agent" in agents

    agent = get_registered_agent("noema-general-agent")
    assert agent is not None
    assert agent.agent_name == "Noema General Agent"
    assert agent.agent_framework == "pydantic-ai"
    assert agent.agent_entrypoint == "services.noema_agent:run_noema_agent"
    assert agent.agent_enabled is True
    assert agent.degrades_gracefully is True
    assert agent.writeback_opt_in is True
    assert agent.writeback_audit_logged is True
    assert "mail.search" in agent.agent_capabilities
    assert "calendar.writeback" in agent.agent_capabilities


def test_registry_uses_semantic_owned_keys_with_bounded_legacy_aliases() -> None:
    """Keep canonical catalog names specific while retaining Python compatibility."""
    agent = get_registered_agent("noema-general-agent")
    assert agent is not None

    assert agent.raw_entry["agent_name"] == "Noema General Agent"
    assert agent.raw_entry["agent_framework"] == "pydantic-ai"
    assert agent.raw_entry["agent_entrypoint"] == "services.noema_agent:run_noema_agent"
    assert agent.raw_entry["agent_enabled"] is True
    assert "name" not in agent.raw_entry
    assert "framework" not in agent.raw_entry
    assert "entrypoint" not in agent.raw_entry
    assert "enabled" not in agent.raw_entry

    # Existing package/submodule consumers can transition without a flag day.
    assert agent.name == agent.agent_name
    assert agent.framework == agent.agent_framework
    assert agent.entrypoint == agent.agent_entrypoint
    assert agent.enabled == agent.agent_enabled
    assert agent.capabilities == agent.agent_capabilities


def test_legacy_raw_mapping_survives_semantic_and_legacy_catalog_input() -> None:
    """Keep historical raw keys readable while raw_entry remains semantic."""
    semantic_entry = {
        "agent_name": "Semantic Agent",
        "agent_framework": "pydantic-ai",
        "agent_entrypoint": "services.semantic_agent:run",
        "agent_description": "semantic description",
        "agent_capabilities": ["mail.search"],
        "agent_enabled": True,
    }
    legacy_entry = {
        "name": "Legacy Agent",
        "framework": "pydantic-ai",
        "entrypoint": "services.legacy_agent:run",
        "description": "legacy description",
        "capabilities": ["mail.read"],
        "enabled": False,
    }

    for catalog_entry, expected_name, expected_entrypoint, expected_enabled in (
        (semantic_entry, "Semantic Agent", "services.semantic_agent:run", True),
        (legacy_entry, "Legacy Agent", "services.legacy_agent:run", False),
    ):
        registered_agent = agent_registry_module._agent_from_entry(
            "compatibility-agent", catalog_entry
        )
        assert registered_agent is not None
        assert registered_agent.raw["name"] == expected_name
        assert registered_agent.raw["framework"] == "pydantic-ai"
        assert registered_agent.raw["entrypoint"] == expected_entrypoint
        assert registered_agent.raw["description"] in {
            "semantic description",
            "legacy description",
        }
        assert isinstance(registered_agent.raw["capabilities"], list)
        assert registered_agent.raw["enabled"] is expected_enabled
        assert "name" not in registered_agent.raw_entry
        assert "framework" not in registered_agent.raw_entry
        assert "entrypoint" not in registered_agent.raw_entry
        assert "description" not in registered_agent.raw_entry
        assert "capabilities" not in registered_agent.raw_entry
        assert "enabled" not in registered_agent.raw_entry


def test_task_mapping_resolves_to_noema_agent() -> None:
    """Resolve mapped task types to the semantic registered-agent contract."""
    mapping = load_task_agent_mapping()
    assert mapping.get("general") == "noema-general-agent"

    agent = resolve_agent_for_task("mail.triage")
    assert agent is not None
    assert agent.agent_id == "noema-general-agent"


def test_unknown_task_type_resolves_to_none() -> None:
    """Return no agent for task types absent from the registry mapping."""
    assert resolve_agent_for_task("does-not-exist") is None
