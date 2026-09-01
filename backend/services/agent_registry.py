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
from collections.abc import Iterator, MutableMapping
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


class _LegacyRawView(MutableMapping[str, Any]):
    """Mutable legacy-key view backed by authoritative semantic registry evidence.

    Historical callers received a mutable dictionary from ``RegisteredAgent.raw``.
    This adapter preserves write-through mutation semantics without storing the
    generic compatibility keys in ``raw_entry``. The six translated legacy keys
    address their semantic counterparts; unrelated metadata addresses the same
    key in ``raw_entry`` directly.
    """

    def __init__(self, raw_entry: dict[str, Any]) -> None:
        self._raw_entry = raw_entry

    def __getitem__(self, legacy_key: str) -> Any:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is not None:
            return self._raw_entry[semantic_key]
        if legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(legacy_key)
        return self._raw_entry[legacy_key]

    def __setitem__(self, legacy_key: str, legacy_value: Any) -> None:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is not None:
            self._raw_entry[semantic_key] = legacy_value
            return
        if legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(
                f"{legacy_key!r} is semantic-only in raw_entry; "
                "mutate its historical alias through raw instead"
            )
        self._raw_entry[legacy_key] = legacy_value

    def __delitem__(self, legacy_key: str) -> None:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is not None:
            del self._raw_entry[semantic_key]
            return
        if legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(legacy_key)
        del self._raw_entry[legacy_key]

    def __iter__(self) -> Iterator[str]:
        for raw_key in self._raw_entry:
            yield _SEMANTIC_RAW_TO_LEGACY.get(raw_key, raw_key)

    def __len__(self) -> int:
        return len(self._raw_entry)

    def copy(self) -> dict[str, Any]:
        """Return a detached legacy-shaped dictionary like ``dict.copy``."""
        return dict(self.items())


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
    def raw(self) -> MutableMapping[str, Any]:
        """Return a mutable legacy-key view synchronized with ``raw_entry``."""
        return _LegacyRawView(self.raw_entry)


def _coerce_capabilities(value: Any) -> tuple[str, ...]:
    """Return non-empty string capability names from a registry JSON value."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _entry_value(
    entry: dict[str, Any], semantic_key: str, legacy_key: str, default_value: Any = None
) -> Any:
    """Read a canonical semantic key, falling back to one bounded legacy alias."""
    if semantic_key in entry:
        return entry[semantic_key]
    return entry.get(legacy_key, default_value)


def _canonical_raw_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return registry evidence with owned generic keys translated semantically."""
    canonical_entry = dict(entry)
    for legacy_key, semantic_key in _LEGACY_RAW_TO_SEMANTIC.items():
        if semantic_key not in canonical_entry and legacy_key in canonical_entry:
            canonical_entry[semantic_key] = canonical_entry[legacy_key]
        canonical_entry.pop(legacy_key, None)
    return canonical_entry


def _agent_from_entry(agent_id: str, entry: dict[str, Any]) -> RegisteredAgent | None:
    """Translate one registry JSON entry into the semantic Python contract."""
    agent_entrypoint = _entry_value(entry, "agent_entrypoint", "entrypoint")
    agent_name = _entry_value(entry, "agent_name", "name")
    agent_framework = _entry_value(entry, "agent_framework", "framework")
    if not isinstance(agent_entrypoint, str) or not agent_entrypoint:
        logger.debug("Skipping agent %s: missing agent_entrypoint", agent_id)
        return None
    if not isinstance(agent_name, str) or not agent_name:
        agent_name = agent_id
    if not isinstance(agent_framework, str):
        agent_framework = ""

    writeback_policy = entry.get("writeback")
    writeback_policy = writeback_policy if isinstance(writeback_policy, dict) else {}

    return RegisteredAgent(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_framework=agent_framework,
        agent_entrypoint=agent_entrypoint,
        agent_description=str(
            _entry_value(entry, "agent_description", "description", "") or ""
        ),
        agent_capabilities=_coerce_capabilities(
            _entry_value(entry, "agent_capabilities", "capabilities", [])
        ),
        provider_source=str(entry.get("provider_source", "") or ""),
        writeback_opt_in=bool(writeback_policy.get("opt_in", False)),
        writeback_audit_logged=bool(writeback_policy.get("audit_logged", False)),
        degrades_gracefully=bool(entry.get("degrades_gracefully", False)),
        agent_enabled=bool(_entry_value(entry, "agent_enabled", "enabled", True)),
        raw_entry=_canonical_raw_entry(entry),
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object or fail closed to an empty mapping."""
    try:
        file_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.debug("Registration file not found: %s", path)
        return {}
    except OSError:
        logger.debug("Could not read registration file: %s", path, exc_info=True)
        return {}

    try:
        parsed_object = json.loads(file_text or "{}")
    except json.JSONDecodeError:
        logger.debug("Malformed registration file: %s", path, exc_info=True)
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
