"""Tests for the workspace agent registry loader."""

import logging
from pathlib import Path

from services import agent_registry
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


def test_registry_read_failure_redacts_exception_value_and_path(
    caplog, monkeypatch, tmp_path
):
    secret_path = tmp_path / "OPENAI_API_KEY=sk-test-secret" / "registered_agents.json"
    secret_error = (
        "postgresql://operator:password@db.internal/naruon "
        "OPENAI_API_KEY=sk-test-secret"
    )

    def raise_read_error(self: Path, *args, **kwargs) -> str:
        raise OSError(secret_error)

    monkeypatch.setattr(Path, "read_text", raise_read_error)

    with caplog.at_level(logging.DEBUG, logger=agent_registry.__name__):
        assert agent_registry._load_json_object(secret_path) == {}

    formatter = logging.Formatter("%(levelname)s %(name)s %(message)s")
    rendered = "\n".join(formatter.format(record) for record in caplog.records)

    assert "Could not read registration file" in rendered
    assert "OSError" in rendered
    assert "exception_fingerprint=" in rendered
    assert secret_error not in rendered
    assert "sk-test-secret" not in rendered
    assert "operator:password" not in rendered
    assert str(secret_path) not in rendered


def test_registry_parse_failure_redacts_payload_and_path(caplog, monkeypatch, tmp_path):
    secret_path = tmp_path / "provider-token-sk-test-secret" / "task_agent_mapping.json"
    malformed_payload = '{"provider_token":"sk-test-secret",'

    def return_malformed_payload(self: Path, *args, **kwargs) -> str:
        return malformed_payload

    monkeypatch.setattr(Path, "read_text", return_malformed_payload)

    with caplog.at_level(logging.DEBUG, logger=agent_registry.__name__):
        assert agent_registry._load_json_object(secret_path) == {}

    formatter = logging.Formatter("%(levelname)s %(name)s %(message)s")
    rendered = "\n".join(formatter.format(record) for record in caplog.records)

    assert "Malformed registration file" in rendered
    assert "JSONDecodeError" in rendered
    assert "exception_fingerprint=" in rendered
    assert "sk-test-secret" not in rendered
    assert str(secret_path) not in rendered
