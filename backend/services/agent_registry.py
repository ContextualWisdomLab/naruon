"""Loader for the workspace agent registry.

The repository ships two registration files at its root:

* ``registered_agents.json`` — the catalog of available agents keyed by agent id.
* ``task_agent_mapping.json`` — a mapping from a task type to the agent id that
  should handle it.

These files are the intended registration point for pluggable agents. This
module loads them lazily, validates their shape defensively, and exposes small
lookup helpers so callers never have to touch the filesystem directly.
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
    """A single entry from ``registered_agents.json``."""

    agent_id: str
    name: str
    framework: str
    entrypoint: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    provider_source: str = ""
    agent_role: str = ""
    model_alias: str = ""
    sequential_failover: bool = False
    writeback_opt_in: bool = False
    writeback_audit_logged: bool = False
    degrades_gracefully: bool = False
    enabled: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


def _coerce_capabilities(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _agent_from_entry(agent_id: str, entry: dict[str, Any]) -> RegisteredAgent | None:
    entrypoint = entry.get("entrypoint")
    name = entry.get("name")
    framework = entry.get("framework")
    if not isinstance(entrypoint, str) or not entrypoint:
        logger.debug("Skipping agent %s: missing entrypoint", agent_id)
        return None
    if not isinstance(name, str) or not name:
        name = agent_id
    if not isinstance(framework, str):
        framework = ""

    writeback = entry.get("writeback")
    writeback = writeback if isinstance(writeback, dict) else {}

    return RegisteredAgent(
        agent_id=agent_id,
        name=name,
        framework=framework,
        entrypoint=entrypoint,
        description=str(entry.get("description", "") or ""),
        capabilities=_coerce_capabilities(entry.get("capabilities")),
        provider_source=str(entry.get("provider_source", "") or ""),
        agent_role=str(entry.get("agent_role", "") or ""),
        model_alias=str(entry.get("model_alias", "") or ""),
        sequential_failover=bool(entry.get("sequential_failover", False)),
        writeback_opt_in=bool(writeback.get("opt_in", False)),
        writeback_audit_logged=bool(writeback.get("audit_logged", False)),
        degrades_gracefully=bool(entry.get("degrades_gracefully", False)),
        enabled=bool(entry.get("enabled", True)),
        raw=dict(entry),
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("Registration file not found: %s", path)
        return {}
    except OSError:
        logger.debug("Could not read registration file: %s", path, exc_info=True)
        return {}

    try:
        parsed = json.loads(text or "{}")
    except json.JSONDecodeError:
        logger.debug("Malformed registration file: %s", path, exc_info=True)
        return {}

    return parsed if isinstance(parsed, dict) else {}


@lru_cache(maxsize=1)
def load_registered_agents() -> dict[str, RegisteredAgent]:
    """Return the registered agents keyed by ``agent_id`` (cached)."""
    raw = _load_json_object(REGISTERED_AGENTS_PATH)
    agents: dict[str, RegisteredAgent] = {}
    for agent_id, entry in raw.items():
        if not isinstance(agent_id, str) or not isinstance(entry, dict):
            continue
        agent = _agent_from_entry(agent_id, entry)
        if agent is not None:
            agents[agent_id] = agent
    return agents


@lru_cache(maxsize=1)
def load_task_agent_mapping() -> dict[str, str]:
    """Return the task-type -> agent-id mapping (cached)."""
    raw = _load_json_object(TASK_AGENT_MAPPING_PATH)
    mapping: dict[str, str] = {}
    for task_type, agent_id in raw.items():
        if isinstance(task_type, str) and isinstance(agent_id, str) and agent_id:
            mapping[task_type] = agent_id
    return mapping


def get_registered_agent(agent_id: str) -> RegisteredAgent | None:
    """Look up a single registered agent by id."""
    return load_registered_agents().get(agent_id)


def resolve_agent_for_task(task_type: str) -> RegisteredAgent | None:
    """Resolve the enabled agent registered to handle ``task_type``."""
    agent_id = load_task_agent_mapping().get(task_type)
    if not agent_id:
        return None
    agent = get_registered_agent(agent_id)
    if agent is None or not agent.enabled:
        return None
    return agent


def clear_registry_cache() -> None:
    """Reset cached registry state (primarily for tests)."""
    load_registered_agents.cache_clear()
    load_task_agent_mapping.cache_clear()
