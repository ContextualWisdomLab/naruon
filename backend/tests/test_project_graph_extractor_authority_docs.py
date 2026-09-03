"""Regression tests for project-graph extractor authority documentation."""

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_root_authority_docs_match_fail_closed_project_graph_extractor_contract() -> None:
    """Root architecture guidance must not restore provider or keyword-fallback authority."""

    architecture = (_REPOSITORY_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    claude = (_REPOSITORY_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "terminal\nelement is **always** the deterministic keyword extractor" not in architecture
    assert "fails closed to the deterministic extractor" not in architecture
    assert "OpenAI-compatible LLM providers (Ollama locally)" not in claude

    assert "Explicit `PROJECT_GRAPH_EXTRACTOR=keyword`" in architecture
    assert "must not silently fall back to keyword extraction" in architecture
    assert "released contextual-orchestrator consumer contract" in architecture
    assert "contextual-orchestrator released consumer contract" in claude
