"""Loader for the workspace agent registry.

The repository ships two registration files at its root:

* ``registered_agents.json`` — the catalog of available agents keyed by agent id.
* ``task_agent_mapping.json`` — a mapping from a task type to the agent id that
  should handle it.

These files are the intended registration point for pluggable agents. This
module loads them lazily, validates their shape defensively, and exposes small
lookup helpers so callers never have to touch the filesystem directly.

The current registry document uses ContextualWisdomLab-owned semantic field
names. The loader still accepts the previous generic field names at this single
adapter boundary so existing deployments can migrate without breaking callers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# backend/services/agent_registry.py -> parents[2] is the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTERED_AGENTS_PATH = _REPO_ROOT / "registered_agents.json"
TASK_AGENT_MAPPING_PATH = _REPO_ROOT / "task_agent_mapping.json"


@dataclass(frozen=True)
class RegisteredAgent:
    """A validated agent-registration record with semantic internal field names."""

    agent_id: str
    agent_display_name: str
    agent_framework_name: str
    agent_entrypoint: str
    agent_description: str = ""
    agent_capabilities: tuple[str, ...] = ()
    provider_source: str = ""
    writeback_opt_in: bool = False
    writeback_audit_logged: bool = False
    degrades_gracefully: bool = False
    agent_enabled: bool = True
    registry_entry_payload: dict[str, Any] = field(default_factory=dict)


def _registry_field_value(
    registry_entry: dict[str, Any],
    semantic_field_name: str,
    legacy_field_name: str,
    default_value: Any = None,
) -> Any:
    """Read one semantic registry field with a legacy-key compatibility fallback."""
    if semantic_field_name in registry_entry:
        return registry_entry[semantic_field_name]
    return registry_entry.get(legacy_field_name, default_value)


def _coerce_capabilities(capability_value: Any) -> tuple[str, ...]:
    """Normalize a registry capability list to non-empty capability strings."""
    if not isinstance(capability_value, list):
        return ()
    return tuple(
        capability_item
        for capability_item in capability_value
        if isinstance(capability_item, str) and capability_item
    )


def _agent_from_entry(
    agent_id: str,
    registry_entry: dict[str, Any],
) -> RegisteredAgent | None:
    """Translate one registry document entry into the semantic internal model."""
    agent_entrypoint = _registry_field_value(
        registry_entry,
        "agent_entrypoint",
        "entrypoint",
    )
    agent_display_name = _registry_field_value(
        registry_entry,
        "agent_display_name",
        "name",
    )
    agent_framework_name = _registry_field_value(
        registry_entry,
        "agent_framework_name",
        "framework",
    )
    if not isinstance(agent_entrypoint, str) or not agent_entrypoint:
        logger.debug("Skipping agent %s: missing agent_entrypoint", agent_id)
        return None
    if not isinstance(agent_display_name, str) or not agent_display_name:
        agent_display_name = agent_id
    if not isinstance(agent_framework_name, str):
        agent_framework_name = ""

    writeback_policy = _registry_field_value(
        registry_entry,
        "writeback_policy",
        "writeback",
        {},
    )
    writeback_policy = writeback_policy if isinstance(writeback_policy, dict) else {}

    return RegisteredAgent(
        agent_id=agent_id,
        agent_display_name=agent_display_name,
        agent_framework_name=agent_framework_name,
        agent_entrypoint=agent_entrypoint,
        agent_description=str(
            _registry_field_value(
                registry_entry,
                "agent_description",
                "description",
                "",
            )
            or ""
        ),
        agent_capabilities=_coerce_capabilities(
            _registry_field_value(
                registry_entry,
                "agent_capabilities",
                "capabilities",
            )
        ),
        provider_source=str(registry_entry.get("provider_source", "") or ""),
        writeback_opt_in=bool(writeback_policy.get("opt_in", False)),
        writeback_audit_logged=bool(writeback_policy.get("audit_logged", False)),
        degrades_gracefully=bool(registry_entry.get("degrades_gracefully", False)),
        agent_enabled=bool(
            _registry_field_value(
                registry_entry,
                "agent_enabled",
                "enabled",
                True,
            )
        ),
        registry_entry_payload=dict(registry_entry),
    )


def _load_json_object(registration_path: Path) -> dict[str, Any]:
    """Load one JSON object from a registration document path."""
    try:
        registration_text = registration_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("Registration file not found: %s", registration_path)
        return {}
    except OSError:
        logger.debug(
            "Could not read registration file: %s",
            registration_path,
            exc_info=True,
        )
        return {}

    try:
        parsed_document = json.loads(registration_text or "{}")
    except json.JSONDecodeError:
        logger.debug(
            "Malformed registration file: %s",
            registration_path,
            exc_info=True,
        )
        return {}

    return parsed_document if isinstance(parsed_document, dict) else {}


@lru_cache(maxsize=1)
def load_registered_agents() -> dict[str, RegisteredAgent]:
    """Return the registered agents keyed by ``agent_id`` (cached)."""
    registry_document = _load_json_object(REGISTERED_AGENTS_PATH)
    registered_agents: dict[str, RegisteredAgent] = {}
    for agent_id, registry_entry in registry_document.items():
        if not isinstance(agent_id, str) or not isinstance(registry_entry, dict):
            continue
        registered_agent = _agent_from_entry(agent_id, registry_entry)
        if registered_agent is not None:
            registered_agents[agent_id] = registered_agent
    return registered_agents


@lru_cache(maxsize=1)
def load_task_agent_mapping() -> dict[str, str]:
    """Return the task-type -> agent-id mapping (cached)."""
    mapping_document = _load_json_object(TASK_AGENT_MAPPING_PATH)
    task_agent_mapping: dict[str, str] = {}
    for task_type, agent_id in mapping_document.items():
        if isinstance(task_type, str) and isinstance(agent_id, str) and agent_id:
            task_agent_mapping[task_type] = agent_id
    return task_agent_mapping


def get_registered_agent(agent_id: str) -> RegisteredAgent | None:
    """Look up a single registered agent by id."""
    return load_registered_agents().get(agent_id)


def resolve_agent_for_task(task_type: str) -> RegisteredAgent | None:
    """Resolve the enabled agent registered to handle ``task_type``."""
    agent_id = load_task_agent_mapping().get(task_type)
    if not agent_id:
        return None
    resolved_agent = get_registered_agent(agent_id)
    if resolved_agent is None or not resolved_agent.agent_enabled:
        return None
    return resolved_agent


def clear_registry_cache() -> None:
    """Reset cached registry state (primarily for tests)."""
    load_registered_agents.cache_clear()
    load_task_agent_mapping.cache_clear()
