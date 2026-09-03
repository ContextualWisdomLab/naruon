"""Regression contract for current LLM-routing authority guidance."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    """Read repository guidance as UTF-8 text."""
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_agent_guidance_does_not_reintroduce_direct_model_routing_authority() -> None:
    """Current agent guidance must not prescribe direct provider/model routing."""
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")

    forbidden_current_guidance = (
        "STRIX_GITHUB_MODELS_TOKEN",
        "https://models.github.ai/inference",
        "Direct OpenAI GPT-5.4-or-newer",
        "OpenAI-compatible LLM providers",
    )
    combined = f"{agents}\n{claude}"
    for phrase in forbidden_current_guidance:
        assert phrase not in combined


def test_agent_guidance_names_canonical_llm_owner_and_fail_closed_boundary() -> None:
    """Guidance must preserve product ownership while delegating LLM routing."""
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")

    assert "ContextualWisdomLab/.github" in agents
    assert "contextual-orchestrator" in agents
    assert "orchestrator/free" in agents
    assert "fail closed" in agents.lower()
    assert "contextual-orchestrator" in claude
    assert "Naruon owns" in claude
    assert "provider/model routing" in claude
