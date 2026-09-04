"""Regression tests for project-graph extractor authority documentation."""

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _normalized_markdown(path: Path) -> str:
    """Collapse Markdown layout whitespace so prose wrapping cannot defeat contract checks."""

    return " ".join(path.read_text(encoding="utf-8").split())


def test_root_authority_docs_match_fail_closed_project_graph_extractor_contract() -> None:
    """Root architecture guidance must not restore provider or keyword-fallback authority."""

    architecture = _normalized_markdown(_REPOSITORY_ROOT / "ARCHITECTURE.md")
    claude = _normalized_markdown(_REPOSITORY_ROOT / "CLAUDE.md")

    assert "terminal element is **always** the deterministic keyword extractor" not in architecture
    assert "fails closed to the deterministic extractor" not in architecture
    assert "OpenAI-compatible LLM providers (Ollama locally)" not in claude

    assert "Explicit `PROJECT_GRAPH_EXTRACTOR=keyword`" in architecture
    assert "must not silently fall back to keyword extraction" in architecture
    assert "released contextual-orchestrator consumer contract" in architecture
    assert "contextual-orchestrator released consumer contract" in claude


def test_extractor_seam_docs_expose_no_raw_orchestrator_configuration() -> None:
    """Detailed extractor docs must describe the same authority-free runtime seam."""

    seam = _normalized_markdown(
        _REPOSITORY_ROOT / "docs" / "architecture" / "kg-extractor-seam.md"
    )
    doctoring = _normalized_markdown(
        _REPOSITORY_ROOT
        / "docs"
        / "doctoring"
        / "project-graph-orchestrator-consumer-boundary.md"
    )

    assert "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL" not in seam
    assert "KgExtractorContext` is intentionally fieldless" in seam
    assert "no project-graph-specific contextual-orchestrator URL" in seam
    assert "`KgExtractorContext` is now fieldless" in doctoring
    assert "no legacy compatibility constructor" in doctoring
