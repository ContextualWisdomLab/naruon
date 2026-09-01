"""Tests for the workspace agent registry loader."""

from dataclasses import asdict
import json

import pytest

import services.agent_registry as agent_registry_module
from services.agent_registry import (
    RegisteredAgent,
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


def test_legacy_raw_mutations_write_through_to_semantic_evidence() -> None:
    """Preserve mutable raw metadata while keeping semantic raw_entry authority."""
    registered_agent = agent_registry_module._agent_from_entry(
        "compatibility-agent",
        {
            "agent_name": "Original Agent",
            "agent_framework": "pydantic-ai",
            "agent_entrypoint": "services.original_agent:run",
            "agent_description": "original description",
            "agent_capabilities": ["mail.search"],
            "agent_enabled": True,
            "custom_metadata": "original",
        },
    )
    assert registered_agent is not None

    legacy_raw = registered_agent.raw
    legacy_raw["name"] = "Renamed Agent"
    legacy_raw["custom_metadata"] = "changed"

    assert registered_agent.raw["name"] == "Renamed Agent"
    assert registered_agent.raw["custom_metadata"] == "changed"
    assert registered_agent.raw_entry["agent_name"] == "Renamed Agent"
    assert registered_agent.raw_entry["custom_metadata"] == "changed"
    assert "name" not in registered_agent.raw_entry

    del registered_agent.raw["description"]
    del registered_agent.raw["custom_metadata"]

    assert "description" not in registered_agent.raw
    assert "custom_metadata" not in registered_agent.raw
    assert "agent_description" not in registered_agent.raw_entry
    assert "custom_metadata" not in registered_agent.raw_entry
    # Typed immutable fields remain the values captured when the entry was loaded;
    # raw/raw_entry are compatibility/evidence metadata rather than live field setters.
    assert registered_agent.agent_name == "Original Agent"
    assert registered_agent.agent_description == "original description"


def test_legacy_raw_remains_a_json_serializable_dictionary() -> None:
    """Preserve historical dict-specific integrations at the compatibility boundary."""
    registered_agent = agent_registry_module._agent_from_entry(
        "compatibility-agent",
        {
            "agent_name": "Serializable Agent",
            "agent_framework": "pydantic-ai",
            "agent_entrypoint": "services.serializable_agent:run",
            "agent_description": "serializable description",
            "agent_capabilities": ["mail.search"],
            "agent_enabled": True,
            "custom_metadata": {"source_name": "registry"},
        },
    )
    assert registered_agent is not None

    legacy_raw = registered_agent.raw
    assert isinstance(legacy_raw, dict)
    serialized_raw = json.loads(json.dumps(legacy_raw, sort_keys=True))
    assert serialized_raw["name"] == "Serializable Agent"
    assert serialized_raw["custom_metadata"] == {"source_name": "registry"}
    assert "agent_name" not in serialized_raw

    union_result = legacy_raw | {"runtime_status": "available"}
    assert union_result["name"] == "Serializable Agent"
    assert union_result["runtime_status"] == "available"
    assert "agent_name" not in union_result
    assert legacy_raw.copy() == dict(legacy_raw)


def test_legacy_raw_dict_mutators_keep_semantic_evidence_synchronized() -> None:
    """Keep dict mutation APIs synchronized with semantic registry evidence."""
    registered_agent = agent_registry_module._agent_from_entry(
        "compatibility-agent",
        {
            "agent_name": "Mutable Agent",
            "agent_framework": "pydantic-ai",
            "agent_entrypoint": "services.mutable_agent:run",
            "agent_description": "mutable description",
            "agent_capabilities": ["mail.search"],
            "agent_enabled": True,
        },
    )
    assert registered_agent is not None
    legacy_raw = registered_agent.raw

    legacy_raw.update({"name": "Updated Agent", "custom_metadata": "updated"})
    assert registered_agent.raw_entry["agent_name"] == "Updated Agent"
    assert registered_agent.raw_entry["custom_metadata"] == "updated"

    assert legacy_raw.setdefault("name", "ignored") == "Updated Agent"
    assert legacy_raw.setdefault("new_metadata", "created") == "created"
    assert registered_agent.raw_entry["new_metadata"] == "created"

    assert legacy_raw.pop("new_metadata") == "created"
    assert "new_metadata" not in registered_agent.raw_entry
    assert legacy_raw.pop("missing_metadata", "fallback") == "fallback"
    with pytest.raises(KeyError, match="missing_metadata"):
        legacy_raw.pop("missing_metadata")

    legacy_raw["tail_metadata"] = "tail"
    assert legacy_raw.popitem() == ("tail_metadata", "tail")
    assert "tail_metadata" not in registered_agent.raw_entry

    legacy_raw |= {"description": "updated description", "ior_metadata": "present"}
    assert registered_agent.raw_entry["agent_description"] == "updated description"
    assert registered_agent.raw_entry["ior_metadata"] == "present"

    with pytest.raises(KeyError, match="agent_name"):
        legacy_raw["agent_name"] = "semantic key is not a legacy key"
    with pytest.raises(KeyError, match="agent_name"):
        del legacy_raw["agent_name"]

    legacy_raw.clear()
    assert legacy_raw == {}
    assert registered_agent.raw_entry == {}


def test_retained_raw_references_share_one_coherent_dictionary() -> None:
    """Keep every retained legacy mapping coherent with semantic evidence."""
    registered_agent = agent_registry_module._agent_from_entry(
        "compatibility-agent",
        {
            "agent_name": "Coherent Agent",
            "agent_framework": "pydantic-ai",
            "agent_entrypoint": "services.coherent_agent:run",
            "agent_description": "coherent description",
            "agent_capabilities": ["mail.search"],
            "agent_enabled": True,
            "custom_metadata": "initial",
        },
    )
    assert registered_agent is not None

    first_raw = registered_agent.raw
    second_raw = registered_agent.raw
    assert first_raw is second_raw

    first_raw["name"] = "Changed Through First"
    first_raw["custom_metadata"] = "changed-through-first"
    assert second_raw["name"] == "Changed Through First"
    assert second_raw["custom_metadata"] == "changed-through-first"
    assert registered_agent.raw_entry["agent_name"] == "Changed Through First"

    second_raw.pop("description")
    assert "description" not in first_raw
    assert "agent_description" not in registered_agent.raw_entry

    registered_agent.raw_entry["agent_framework"] = "semantic-runtime"
    registered_agent.raw_entry["semantic_metadata"] = "semantic-update"
    assert first_raw["framework"] == "semantic-runtime"
    assert second_raw["semantic_metadata"] == "semantic-update"

    del registered_agent.raw_entry["agent_enabled"]
    del registered_agent.raw_entry["semantic_metadata"]
    assert "enabled" not in first_raw
    assert "semantic_metadata" not in second_raw


def test_registered_agent_accepts_legacy_constructor_keywords() -> None:
    """Preserve direct legacy construction while keeping semantic fields canonical."""
    agent = RegisteredAgent(
        agent_id="legacy-constructor",
        name="Legacy Constructor",
        framework="pydantic-ai",
        entrypoint="services.legacy_constructor:run",
        description="legacy description",
        capabilities=("mail.read",),
        enabled=False,
        raw={
            "name": "Legacy Constructor",
            "framework": "pydantic-ai",
            "entrypoint": "services.legacy_constructor:run",
            "description": "legacy description",
            "capabilities": ["mail.read"],
            "enabled": False,
        },
    )

    assert agent.agent_name == "Legacy Constructor"
    assert agent.agent_framework == "pydantic-ai"
    assert agent.agent_entrypoint == "services.legacy_constructor:run"
    assert agent.agent_description == "legacy description"
    assert agent.agent_capabilities == ("mail.read",)
    assert agent.agent_enabled is False
    assert agent.raw["name"] == "Legacy Constructor"
    assert "name" not in agent.raw_entry


def test_registered_agent_rejects_conflicting_semantic_and_legacy_keywords() -> None:
    """Fail closed when old and new constructor vocabularies disagree."""
    with pytest.raises(ValueError, match="agent_name"):
        RegisteredAgent(
            agent_id="conflicting-constructor",
            agent_name="Semantic Name",
            name="Legacy Name",
            agent_framework="pydantic-ai",
            agent_entrypoint="services.conflicting_constructor:run",
        )


def test_registered_agent_asdict_exposes_only_semantic_dataclass_state() -> None:
    """Serialize dataclass state without traversing the retained legacy adapter."""
    agent = agent_registry_module._agent_from_entry(
        "serializable-agent",
        {
            "agent_name": "Serializable Agent",
            "agent_framework": "pydantic-ai",
            "agent_entrypoint": "services.serializable_agent:run",
            "agent_description": "semantic description",
            "agent_capabilities": ["mail.search"],
            "agent_enabled": True,
        },
    )
    assert agent is not None

    serialized_agent = asdict(agent)

    assert serialized_agent["agent_name"] == "Serializable Agent"
    assert serialized_agent["agent_framework"] == "pydantic-ai"
    assert serialized_agent["agent_entrypoint"] == "services.serializable_agent:run"
    assert serialized_agent["raw_entry"]["agent_name"] == "Serializable Agent"
    assert "_legacy_raw_dict" not in serialized_agent
    assert "raw" not in serialized_agent
    assert "name" not in serialized_agent


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
