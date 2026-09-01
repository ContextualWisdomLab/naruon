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

_LEGACY_RAW_TO_SEMANTIC = {
    "name": "agent_name",
    "framework": "agent_framework",
    "entrypoint": "agent_entrypoint",
    "description": "agent_description",
    "capabilities": "agent_capabilities",
    "enabled": "agent_enabled",
}
_SEMANTIC_RAW_TO_LEGACY = {
    semantic_key: legacy_key
    for legacy_key, semantic_key in _LEGACY_RAW_TO_SEMANTIC.items()
}
_MISSING_POP_DEFAULT = object()


class _LegacyRawDict(dict[str, Any]):
    """Legacy ``dict`` contract backed by authoritative semantic registry evidence.

    Historical callers received an actual mutable dictionary from
    ``RegisteredAgent.raw`` and may therefore rely on JSON serialization, dict
    union, ``isinstance(..., dict)``, and the full mutation API. This bounded
    compatibility adapter keeps a legacy-shaped shallow dictionary for those
    operations while writing every mutation through to semantic ``raw_entry``.
    Nested values intentionally retain shallow aliasing, matching the historical
    dictionary behavior.
    """

    def __init__(self, raw_entry: dict[str, Any]) -> None:
        self._raw_entry = raw_entry
        legacy_entries = {
            _SEMANTIC_RAW_TO_LEGACY.get(raw_key, raw_key): raw_value
            for raw_key, raw_value in raw_entry.items()
        }
        super().__init__(legacy_entries)

    def __setitem__(self, legacy_key: str, legacy_value: Any) -> None:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is not None:
            self._raw_entry[semantic_key] = legacy_value
        elif legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(
                f"{legacy_key!r} is semantic-only in raw_entry; "
                "mutate its historical alias through raw instead"
            )
        else:
            self._raw_entry[legacy_key] = legacy_value
        super().__setitem__(legacy_key, legacy_value)

    def __delitem__(self, legacy_key: str) -> None:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is not None:
            del self._raw_entry[semantic_key]
        elif legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(legacy_key)
        else:
            del self._raw_entry[legacy_key]
        super().__delitem__(legacy_key)

    def update(self, *update_sources: Any, **update_values: Any) -> None:
        """Apply a normal dict update while synchronizing semantic evidence."""
        incoming_entries = dict(*update_sources, **update_values)
        for legacy_key, legacy_value in incoming_entries.items():
            self[legacy_key] = legacy_value

    def setdefault(self, legacy_key: str, default_value: Any = None) -> Any:
        """Return or insert one legacy key while synchronizing semantic evidence."""
        if legacy_key in self:
            return self[legacy_key]
        self[legacy_key] = default_value
        return default_value

    def pop(self, legacy_key: str, default_value: Any = _MISSING_POP_DEFAULT) -> Any:
        """Remove one legacy key while preserving normal ``dict.pop`` semantics."""
        if legacy_key in self:
            legacy_value = self[legacy_key]
            del self[legacy_key]
            return legacy_value
        if default_value is _MISSING_POP_DEFAULT:
            raise KeyError(legacy_key)
        return default_value

    def popitem(self) -> tuple[str, Any]:
        """Remove the newest legacy item and synchronize semantic evidence."""
        legacy_key, legacy_value = super().popitem()
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key, legacy_key)
        del self._raw_entry[semantic_key]
        return legacy_key, legacy_value

    def clear(self) -> None:
        """Clear both compatibility and semantic registry evidence."""
        super().clear()
        self._raw_entry.clear()

    def __ior__(self, other_mapping: Any) -> _LegacyRawDict:
        """Apply in-place dict union while synchronizing semantic evidence."""
        self.update(other_mapping)
        return self

    def copy(self) -> dict[str, Any]:
        """Return a detached legacy-shaped dictionary like ``dict.copy``."""
        return dict(self)


@dataclass(frozen=True)
class RegisteredAgent:
    """A semantically named entry from ``registered_agents.json``.

    The ``agent_*`` attributes are the authoritative organization-owned Python
    contract. Read-only legacy properties keep older package/submodule callers
    working while the JSON loader translates historical generic keys at the
    registry boundary.
    """

    agent_id: str
    agent_name: str
    agent_framework: str
    agent_entrypoint: str
    agent_description: str = ""
    agent_capabilities: tuple[str, ...] = ()
    provider_source: str = ""
    writeback_opt_in: bool = False
    writeback_audit_logged: bool = False
    degrades_gracefully: bool = False
    agent_enabled: bool = True
    raw_entry: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Return ``agent_name`` for legacy Python callers."""
        return self.agent_name

    @property
    def framework(self) -> str:
        """Return ``agent_framework`` for legacy Python callers."""
        return self.agent_framework

    @property
    def entrypoint(self) -> str:
        """Return ``agent_entrypoint`` for legacy Python callers."""
        return self.agent_entrypoint

    @property
    def description(self) -> str:
        """Return ``agent_description`` for legacy Python callers."""
        return self.agent_description

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Return ``agent_capabilities`` for legacy Python callers."""
        return self.agent_capabilities

    @property
    def enabled(self) -> bool:
        """Return ``agent_enabled`` for legacy Python callers."""
        return self.agent_enabled

    @property
    def raw(self) -> dict[str, Any]:
        """Return a legacy-shaped dict synchronized with semantic ``raw_entry``."""
        return _LegacyRawDict(self.raw_entry)


def _coerce_capabilities(capability_value: Any) -> tuple[str, ...]:
    """Return non-empty string capability names from a registry JSON value."""
    if not isinstance(capability_value, list):
        return ()
    return tuple(
        capability_name
        for capability_name in capability_value
        if isinstance(capability_name, str) and capability_name
    )


def _entry_value(
    registry_entry: dict[str, Any],
    semantic_key: str,
    legacy_key: str,
    default_value: Any = None,
) -> Any:
    """Read a canonical semantic key, falling back to one bounded legacy alias."""
    if semantic_key in registry_entry:
        return registry_entry[semantic_key]
    return registry_entry.get(legacy_key, default_value)


def _canonical_raw_entry(registry_entry: dict[str, Any]) -> dict[str, Any]:
    """Return registry evidence with owned generic keys translated semantically."""
    canonical_entry = dict(registry_entry)
    for legacy_key, semantic_key in _LEGACY_RAW_TO_SEMANTIC.items():
        if semantic_key not in canonical_entry and legacy_key in canonical_entry:
            canonical_entry[semantic_key] = canonical_entry[legacy_key]
        canonical_entry.pop(legacy_key, None)
    return canonical_entry


def _agent_from_entry(
    agent_id: str, registry_entry: dict[str, Any]
) -> RegisteredAgent | None:
    """Translate one registry JSON entry into the semantic Python contract."""
    agent_entrypoint = _entry_value(
        registry_entry, "agent_entrypoint", "entrypoint"
    )
    agent_name = _entry_value(registry_entry, "agent_name", "name")
    agent_framework = _entry_value(registry_entry, "agent_framework", "framework")
    if not isinstance(agent_entrypoint, str) or not agent_entrypoint:
        logger.debug("Skipping agent %s: missing agent_entrypoint", agent_id)
        return None
    if not isinstance(agent_name, str) or not agent_name:
        agent_name = agent_id
    if not isinstance(agent_framework, str):
        agent_framework = ""

    writeback_policy = registry_entry.get("writeback")
    writeback_policy = writeback_policy if isinstance(writeback_policy, dict) else {}

    return RegisteredAgent(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_framework=agent_framework,
        agent_entrypoint=agent_entrypoint,
        agent_description=str(
            _entry_value(
                registry_entry, "agent_description", "description", ""
            )
            or ""
        ),
        agent_capabilities=_coerce_capabilities(
            _entry_value(
                registry_entry, "agent_capabilities", "capabilities", []
            )
        ),
        provider_source=str(registry_entry.get("provider_source", "") or ""),
        writeback_opt_in=bool(writeback_policy.get("opt_in", False)),
        writeback_audit_logged=bool(writeback_policy.get("audit_logged", False)),
        degrades_gracefully=bool(
            registry_entry.get("degrades_gracefully", False)
        ),
        agent_enabled=bool(
            _entry_value(registry_entry, "agent_enabled", "enabled", True)
        ),
        raw_entry=_canonical_raw_entry(registry_entry),
    )


def _load_json_object(registry_path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object or fail closed to an empty mapping."""
    try:
        file_text = registry_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("Registration file not found: %s", registry_path)
        return {}
    except OSError:
        logger.debug("Could not read registration file: %s", registry_path, exc_info=True)
        return {}

    try:
        parsed_object = json.loads(file_text or "{}")
    except json.JSONDecodeError:
        logger.debug("Malformed registration file: %s", registry_path, exc_info=True)
        return {}

    return parsed_object if isinstance(parsed_object, dict) else {}


@lru_cache(maxsize=1)
def load_registered_agents() -> dict[str, RegisteredAgent]:
    """Return the registered agents keyed by ``agent_id`` (cached)."""
    registry_entries = _load_json_object(REGISTERED_AGENTS_PATH)
    registered_agents: dict[str, RegisteredAgent] = {}
    for agent_id, registry_entry in registry_entries.items():
        if not isinstance(agent_id, str) or not isinstance(registry_entry, dict):
            continue
        registered_agent = _agent_from_entry(agent_id, registry_entry)
        if registered_agent is not None:
            registered_agents[agent_id] = registered_agent
    return registered_agents


@lru_cache(maxsize=1)
def load_task_agent_mapping() -> dict[str, str]:
    """Return the task-type -> agent-id mapping (cached)."""
    mapping_entries = _load_json_object(TASK_AGENT_MAPPING_PATH)
    task_agent_mapping: dict[str, str] = {}
    for task_type, agent_id in mapping_entries.items():
        if isinstance(task_type, str) and isinstance(agent_id, str) and agent_id:
            task_agent_mapping[task_type] = agent_id
    return task_agent_mapping


def get_registered_agent(agent_id: str) -> RegisteredAgent | None:
    """Look up a single registered agent by ``agent_id``."""
    return load_registered_agents().get(agent_id)


def resolve_agent_for_task(task_type: str) -> RegisteredAgent | None:
    """Resolve the enabled agent registered to handle ``task_type``."""
    agent_id = load_task_agent_mapping().get(task_type)
    if not agent_id:
        return None
    registered_agent = get_registered_agent(agent_id)
    if registered_agent is None or not registered_agent.agent_enabled:
        return None
    return registered_agent


def clear_registry_cache() -> None:
    """Reset cached registry state (primarily for tests)."""
    load_registered_agents.cache_clear()
    load_task_agent_mapping.cache_clear()
