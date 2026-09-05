"""Tests for the workspace agent registry loader."""

import json
from dataclasses import fields

from services.agent_registry import (
    REGISTERED_AGENTS_PATH,
    RegisteredAgent,
    _agent_from_entry,
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


def test_noema_agent_is_registered() -> None:
    registered_agents = load_registered_agents()
    assert "noema-general-agent" in registered_agents

    noema_agent = get_registered_agent("noema-general-agent")
    assert noema_agent is not None
    assert noema_agent.agent_framework_name == "pydantic-ai"
    assert noema_agent.agent_entrypoint == "services.noema_agent:run_noema_agent"
    assert noema_agent.agent_enabled is True
    assert noema_agent.degrades_gracefully is True
    # The opt-in + audit-logged writeback contract is declared in the catalog.
    assert noema_agent.writeback_opt_in is True
    assert noema_agent.writeback_audit_logged is True
    assert "mail.search" in noema_agent.agent_capabilities
    assert "calendar.writeback" in noema_agent.agent_capabilities


def test_task_mapping_resolves_to_noema_agent() -> None:
    task_agent_mapping = load_task_agent_mapping()
    assert task_agent_mapping.get("general") == "noema-general-agent"

    resolved_agent = resolve_agent_for_task("mail.triage")
    assert resolved_agent is not None
    assert resolved_agent.agent_id == "noema-general-agent"


def test_unknown_task_type_resolves_to_none() -> None:
    assert resolve_agent_for_task("does-not-exist") is None


def test_registered_agent_internal_fields_are_semantically_specific() -> None:
    """Keep organization-owned dataclass fields specific to the agent registry."""
    registered_agent_fields = {field_info.name for field_info in fields(RegisteredAgent)}
    required_agent_fields = {
        "agent_id",
        "agent_display_name",
        "agent_framework_name",
        "agent_entrypoint",
        "agent_description",
        "agent_capabilities",
        "agent_enabled",
        "registry_entry_payload",
    }
    forbidden_generic_fields = {
        "name",
        "framework",
        "entrypoint",
        "description",
        "capabilities",
        "enabled",
        "raw",
    }

    assert required_agent_fields <= registered_agent_fields
    assert forbidden_generic_fields.isdisjoint(registered_agent_fields)


def test_registry_document_uses_semantic_owned_keys() -> None:
    """The organization-owned registry document should publish semantic field names."""
    registry_document = json.loads(REGISTERED_AGENTS_PATH.read_text(encoding="utf-8"))
    noema_registry_entry = registry_document["noema-general-agent"]

    assert noema_registry_entry["agent_display_name"] == "Noema General Agent"
    assert noema_registry_entry["agent_framework_name"] == "pydantic-ai"
    assert noema_registry_entry["agent_entrypoint"] == "services.noema_agent:run_noema_agent"
    assert noema_registry_entry["agent_enabled"] is True
    assert "mail.search" in noema_registry_entry["agent_capabilities"]


def test_legacy_registry_keys_remain_accepted_at_adapter_boundary() -> None:
    """Existing registry deployments keep loading while callers migrate semantic keys."""
    legacy_registry_entry = {
        "name": "Legacy Agent",
        "framework": "pydantic-ai",
        "entrypoint": "services.legacy_agent:run_legacy_agent",
        "description": "Legacy registry compatibility fixture",
        "capabilities": ["mail.read"],
        "enabled": True,
    }

    adapted_agent = _agent_from_entry("legacy-agent", legacy_registry_entry)

    assert adapted_agent is not None
    assert adapted_agent.agent_display_name == "Legacy Agent"
    assert adapted_agent.agent_framework_name == "pydantic-ai"
    assert adapted_agent.agent_entrypoint == "services.legacy_agent:run_legacy_agent"
    assert adapted_agent.agent_description == "Legacy registry compatibility fixture"
    assert adapted_agent.agent_capabilities == ("mail.read",)
    assert adapted_agent.agent_enabled is True


def test_conflicting_semantic_and_legacy_fields_are_rejected() -> None:
    """Do not dispatch an ambiguous registry entry during a staged migration."""
    adapted_agent = _agent_from_entry(
        "ambiguous-agent",
        {
            "agent_display_name": "Canonical Agent",
            "name": "Different Legacy Agent",
            "agent_framework_name": "pydantic-ai",
            "agent_entrypoint": "services.agent:run_agent",
        },
    )

    assert adapted_agent is None


def test_matching_semantic_and_legacy_fields_remain_compatible() -> None:
    """Permit an exact duplicate value while deployed registries migrate."""
    adapted_agent = _agent_from_entry(
        "migrating-agent",
        {
            "agent_display_name": "Migrating Agent",
            "name": "Migrating Agent",
            "agent_framework_name": "pydantic-ai",
            "agent_entrypoint": "services.agent:run_agent",
        },
    )

    assert adapted_agent is not None
    assert adapted_agent.agent_display_name == "Migrating Agent"
