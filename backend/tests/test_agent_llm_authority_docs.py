"""Regression contracts for current LLM-routing authority guidance."""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    """Read repository guidance as UTF-8 text."""
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_agent_guidance_does_not_reintroduce_direct_model_routing_authority() -> None:
    """Current agent and architecture guidance must not prescribe direct routing."""
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")
    architecture = _read("ARCHITECTURE.md")

    forbidden_current_guidance = (
        "STRIX_GITHUB_MODELS_TOKEN",
        "https://models.github.ai/inference",
        "Direct OpenAI GPT-5.4-or-newer",
        "OpenAI-compatible LLM providers",
        "API --> LLM[OpenAI APIs when configured]",
    )
    combined = f"{agents}\n{claude}\n{architecture}"
    for phrase in forbidden_current_guidance:
        assert phrase not in combined


def test_agent_guidance_names_canonical_llm_owner_and_fail_closed_boundary() -> None:
    """Guidance must preserve product ownership while delegating LLM routing."""
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")
    architecture = _read("ARCHITECTURE.md")
    normalized_architecture = " ".join(architecture.lower().split())

    assert "ContextualWisdomLab/.github" in agents
    assert "contextual-orchestrator" in agents
    assert "orchestrator/free" in agents
    assert "fail closed" in agents.lower()
    assert "contextual-orchestrator" in claude
    assert "Naruon owns" in claude
    assert "provider/model routing" in claude
    assert "gateway token" in agents
    assert "provider names, model" in agents
    assert "immutable released owner API/client/schema" in agents
    assert "open pr or unreleased branch" in " ".join(agents.lower().split())
    assert "shared application/agent/gateway wall-clock timeout" in agents
    assert "contextual-orchestrator" in normalized_architecture
    assert "provider discovery" in normalized_architecture
    assert "immutable released" in normalized_architecture
    assert "fails closed" in normalized_architecture


def test_opencode_config_uses_only_contextual_orchestrator_free() -> None:
    """Repository OpenCode model work must use only the canonical logical pool."""
    raw_config = _read("opencode.jsonc")
    config = json.loads(raw_config)

    assert config["model"] == "contextual-orchestrator/orchestrator/free"
    assert config["small_model"] == "contextual-orchestrator/orchestrator/free"
    assert config["enabled_providers"] == ["contextual-orchestrator"]
    assert set(config["provider"]) == {"contextual-orchestrator"}

    provider = config["provider"]["contextual-orchestrator"]
    assert provider["options"] == {
        "baseURL": "http://127.0.0.1:8100/v1",
        "apiKey": "{env:CONTEXTUAL_ORCHESTRATOR_TOKEN}",
        "timeout": False,
    }
    assert set(provider["models"]) == {"orchestrator/free"}

    forbidden_direct_routing = (
        "github-models",
        "STRIX_GITHUB_MODELS_TOKEN",
        "https://models.github.ai/inference",
        '"openai/gpt-5"',
        '"deepseek/deepseek-r1-0528"',
        '"deepseek/deepseek-v3-0324"',
    )
    for phrase in forbidden_direct_routing:
        assert phrase not in raw_config
