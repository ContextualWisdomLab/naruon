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
_CONSTRUCTOR_UNSET = object()


def _resolve_constructor_alias(
    semantic_key: str,
    semantic_value: Any,
    legacy_value: Any,
    default_value: Any,
) -> Any:
    """Resolve one semantic/legacy constructor pair and reject contradictions."""
    semantic_supplied = semantic_value is not _CONSTRUCTOR_UNSET
    legacy_supplied = legacy_value is not _CONSTRUCTOR_UNSET
    if semantic_supplied and legacy_supplied and semantic_value != legacy_value:
        raise ValueError(f"conflicting values supplied for {semantic_key}")
    if semantic_supplied:
        return semantic_value
    if legacy_supplied:
        return legacy_value
    return default_value


class _SemanticRawDict(dict[str, Any]):
    """Semantic evidence dictionary synchronized with one legacy dictionary.

    ``raw_entry`` is the canonical organization-owned mapping, so generic legacy
    keys are rejected here. Direct semantic mutations remain supported because
    the field is a public dictionary; each mutation synchronizes the retained
    compatibility dictionary without reintroducing generic keys into semantic
    evidence.
    """

    def __init__(self, semantic_entries: dict[str, Any]) -> None:
        self._legacy_raw_dict: _LegacyRawDict | None = None
        super().__init__(semantic_entries)

    def bind_legacy_raw_dict(self, legacy_raw_dict: _LegacyRawDict) -> None:
        """Bind the one compatibility dictionary owned by the registered agent."""
        self._legacy_raw_dict = legacy_raw_dict

    def set_from_legacy(self, semantic_key: str, semantic_value: Any) -> None:
        """Write semantic evidence without recursively notifying the legacy side."""
        dict.__setitem__(self, semantic_key, semantic_value)

    def delete_from_legacy(self, semantic_key: str) -> None:
        """Delete semantic evidence without recursively notifying the legacy side."""
        dict.__delitem__(self, semantic_key)

    def clear_from_legacy(self) -> None:
        """Clear semantic evidence without recursively notifying the legacy side."""
        dict.clear(self)

    def __setitem__(self, semantic_key: str, semantic_value: Any) -> None:
        if semantic_key in _LEGACY_RAW_TO_SEMANTIC:
            raise KeyError(
                f"{semantic_key!r} is legacy-only; use its semantic agent_* key "
                "through raw_entry"
            )
        dict.__setitem__(self, semantic_key, semantic_value)
        if self._legacy_raw_dict is not None:
            self._legacy_raw_dict.sync_semantic_set(semantic_key, semantic_value)

    def __delitem__(self, semantic_key: str) -> None:
        if semantic_key in _LEGACY_RAW_TO_SEMANTIC:
            raise KeyError(semantic_key)
        dict.__delitem__(self, semantic_key)
        if self._legacy_raw_dict is not None:
            self._legacy_raw_dict.sync_semantic_delete(semantic_key)

    def update(self, *update_sources: Any, **update_values: Any) -> None:
        """Apply a normal dict update while synchronizing legacy compatibility."""
        incoming_entries = dict(*update_sources, **update_values)
        for semantic_key, semantic_value in incoming_entries.items():
            self[semantic_key] = semantic_value

    def setdefault(self, semantic_key: str, default_value: Any = None) -> Any:
        """Return or insert one semantic key while synchronizing compatibility."""
        if semantic_key in self:
            return self[semantic_key]
        self[semantic_key] = default_value
        return default_value

    def pop(self, semantic_key: str, default_value: Any = _MISSING_POP_DEFAULT) -> Any:
        """Remove one semantic key while preserving normal ``dict.pop`` behavior."""
        if semantic_key in self:
            semantic_value = self[semantic_key]
            del self[semantic_key]
            return semantic_value
        if default_value is _MISSING_POP_DEFAULT:
            raise KeyError(semantic_key)
        return default_value

    def popitem(self) -> tuple[str, Any]:
        """Remove the newest semantic item and synchronize compatibility."""
        if not self:
            raise KeyError("popitem(): dictionary is empty")
        semantic_key = next(reversed(self))
        return semantic_key, self.pop(semantic_key)

    def clear(self) -> None:
        """Clear both semantic evidence and its retained compatibility dictionary."""
        dict.clear(self)
        if self._legacy_raw_dict is not None:
            self._legacy_raw_dict.clear_from_semantic()

    def __ior__(self, other_mapping: Any) -> _SemanticRawDict:
        """Apply in-place dict union while synchronizing compatibility."""
        self.update(other_mapping)
        return self


class _LegacyRawDict(dict[str, Any]):
    """Legacy ``dict`` contract backed by authoritative semantic registry evidence.

    Historical callers received one actual mutable dictionary from
    ``RegisteredAgent.raw`` and may retain that reference, serialize it, perform
    dict union, and use the full mutation API. This bounded compatibility adapter
    stays a real shallow dictionary while every mutation writes through to the
    paired semantic ``raw_entry`` mapping.
    """

    def __init__(self, raw_entry: _SemanticRawDict) -> None:
        self._raw_entry = raw_entry
        legacy_entries = {
            _SEMANTIC_RAW_TO_LEGACY.get(raw_key, raw_key): raw_value
            for raw_key, raw_value in raw_entry.items()
        }
        super().__init__(legacy_entries)
        raw_entry.bind_legacy_raw_dict(self)

    def sync_semantic_set(self, semantic_key: str, semantic_value: Any) -> None:
        """Mirror one direct semantic mutation without writing it back recursively."""
        legacy_key = _SEMANTIC_RAW_TO_LEGACY.get(semantic_key, semantic_key)
        dict.__setitem__(self, legacy_key, semantic_value)

    def sync_semantic_delete(self, semantic_key: str) -> None:
        """Mirror one direct semantic deletion without writing it back recursively."""
        legacy_key = _SEMANTIC_RAW_TO_LEGACY.get(semantic_key, semantic_key)
        dict.__delitem__(self, legacy_key)

    def clear_from_semantic(self) -> None:
        """Mirror a direct semantic clear without recursively clearing evidence."""
        dict.clear(self)

    def __setitem__(self, legacy_key: str, legacy_value: Any) -> None:
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is None and legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(
                f"{legacy_key!r} is semantic-only in raw_entry; "
                "mutate its historical alias through raw instead"
            )
        semantic_key = semantic_key or legacy_key
        self._raw_entry.set_from_legacy(semantic_key, legacy_value)
        dict.__setitem__(self, legacy_key, legacy_value)

    def __delitem__(self, legacy_key: str) -> None:
        if legacy_key not in self:
            raise KeyError(legacy_key)
        semantic_key = _LEGACY_RAW_TO_SEMANTIC.get(legacy_key)
        if semantic_key is None and legacy_key in _SEMANTIC_RAW_TO_LEGACY:
            raise KeyError(legacy_key)
        semantic_key = semantic_key or legacy_key
        self._raw_entry.delete_from_legacy(semantic_key)
        dict.__delitem__(self, legacy_key)

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
        if not self:
            raise KeyError("popitem(): dictionary is empty")
        legacy_key = next(reversed(self))
        return legacy_key, self.pop(legacy_key)

    def clear(self) -> None:
        """Clear both compatibility and semantic registry evidence."""
        self._raw_entry.clear_from_legacy()
        dict.clear(self)

    def __ior__(self, other_mapping: Any) -> _LegacyRawDict:
        """Apply in-place dict union while synchronizing semantic evidence."""
        self.update(other_mapping)
        return self

    def copy(self) -> dict[str, Any]:
        """Return a detached legacy-shaped dictionary like ``dict.copy``."""
        return dict(self)


@dataclass(frozen=True, init=False)
class RegisteredAgent:
    """A semantically named entry from ``registered_agents.json``.

    The ``agent_*`` attributes are the authoritative organization-owned Python
    contract. Historical constructor keywords and scalar properties remain a
    bounded compatibility surface while the JSON loader translates generic keys
    at the registry boundary.
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

    def __init__(
        self,
        agent_id: str,
        agent_name: Any = _CONSTRUCTOR_UNSET,
        agent_framework: Any = _CONSTRUCTOR_UNSET,
        agent_entrypoint: Any = _CONSTRUCTOR_UNSET,
        agent_description: Any = _CONSTRUCTOR_UNSET,
        agent_capabilities: Any = _CONSTRUCTOR_UNSET,
        provider_source: str = "",
        writeback_opt_in: bool = False,
        writeback_audit_logged: bool = False,
        degrades_gracefully: bool = False,
        agent_enabled: Any = _CONSTRUCTOR_UNSET,
        raw_entry: Any = _CONSTRUCTOR_UNSET,
        *,
        name: Any = _CONSTRUCTOR_UNSET,
        framework: Any = _CONSTRUCTOR_UNSET,
        entrypoint: Any = _CONSTRUCTOR_UNSET,
        description: Any = _CONSTRUCTOR_UNSET,
        capabilities: Any = _CONSTRUCTOR_UNSET,
        enabled: Any = _CONSTRUCTOR_UNSET,
        raw: Any = _CONSTRUCTOR_UNSET,
    ) -> None:
        """Build an agent from semantic names or the bounded legacy vocabulary."""
        resolved_name = _resolve_constructor_alias(
            "agent_name", agent_name, name, _CONSTRUCTOR_UNSET
        )
        resolved_framework = _resolve_constructor_alias(
            "agent_framework", agent_framework, framework, _CONSTRUCTOR_UNSET
        )
        resolved_entrypoint = _resolve_constructor_alias(
            "agent_entrypoint", agent_entrypoint, entrypoint, _CONSTRUCTOR_UNSET
        )
        for required_key, required_value in (
            ("agent_name", resolved_name),
            ("agent_framework", resolved_framework),
            ("agent_entrypoint", resolved_entrypoint),
        ):
            if required_value is _CONSTRUCTOR_UNSET:
                raise TypeError(f"missing required argument: {required_key!r}")

        resolved_description = _resolve_constructor_alias(
            "agent_description", agent_description, description, ""
        )
        semantic_capabilities = (
            tuple(agent_capabilities)
            if agent_capabilities is not _CONSTRUCTOR_UNSET
            else _CONSTRUCTOR_UNSET
        )
        legacy_capabilities = (
            tuple(capabilities)
            if capabilities is not _CONSTRUCTOR_UNSET
            else _CONSTRUCTOR_UNSET
        )
        resolved_capabilities = _resolve_constructor_alias(
            "agent_capabilities", semantic_capabilities, legacy_capabilities, ()
        )
        resolved_enabled = _resolve_constructor_alias(
            "agent_enabled", agent_enabled, enabled, True
        )

        semantic_raw_entry = (
            _canonical_raw_entry(dict(raw_entry))
            if raw_entry is not _CONSTRUCTOR_UNSET
            else _CONSTRUCTOR_UNSET
        )
        legacy_raw_entry = (
            _canonical_raw_entry(dict(raw))
            if raw is not _CONSTRUCTOR_UNSET
            else _CONSTRUCTOR_UNSET
        )
        resolved_raw_entry = _resolve_constructor_alias(
            "raw_entry", semantic_raw_entry, legacy_raw_entry, {}
        )

        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "agent_name", resolved_name)
        object.__setattr__(self, "agent_framework", resolved_framework)
        object.__setattr__(self, "agent_entrypoint", resolved_entrypoint)
        object.__setattr__(self, "agent_description", resolved_description)
        object.__setattr__(self, "agent_capabilities", resolved_capabilities)
        object.__setattr__(self, "provider_source", provider_source)
        object.__setattr__(self, "writeback_opt_in", writeback_opt_in)
        object.__setattr__(self, "writeback_audit_logged", writeback_audit_logged)
        object.__setattr__(self, "degrades_gracefully", degrades_gracefully)
        object.__setattr__(self, "agent_enabled", resolved_enabled)
        object.__setattr__(self, "raw_entry", resolved_raw_entry)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Bind one coherent semantic/legacy dictionary pair for this agent."""
        semantic_raw_entry = _SemanticRawDict(self.raw_entry)
        legacy_raw_dict = _LegacyRawDict(semantic_raw_entry)
        object.__setattr__(self, "raw_entry", semantic_raw_entry)
        object.__setattr__(self, "_legacy_raw_dict", legacy_raw_dict)

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
        """Return this agent's stable legacy dictionary compatibility boundary."""
        return self._legacy_raw_dict


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
