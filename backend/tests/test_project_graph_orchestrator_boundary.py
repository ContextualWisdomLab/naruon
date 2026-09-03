"""Fail-closed contract for project-graph LLM ownership."""

from dataclasses import fields
import inspect
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from services.project_graph import extractor_registry as registry_module
from services.project_graph.extractor_registry import (
    SELECTOR_ORCHESTRATOR,
    ExtractorUnavailableError,
    KgExtractorContext,
    LlmGroundedExtractor,
    run_extraction,
)
from services.project_graph.models import ProjectSourceSegment

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _segment() -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid="seg-boundary",
        source_kind="email_body",
        source_record_uid="email:boundary",
        safe_text_content="The project requires a grounded decision.",
        heading_path=None,
        segment_path="body/0",
        ordinal_index=0,
    )


def test_project_graph_context_carries_no_provider_or_raw_transport_authority():
    assert tuple(field.name for field in fields(KgExtractorContext)) == ()
    assert tuple(inspect.signature(KgExtractorContext).parameters) == ()
    context = KgExtractorContext()
    assert not hasattr(context, "api_key")
    assert not hasattr(context, "orchestrator_base_url")
    assert not hasattr(context, "orchestrator_model")
    assert not hasattr(context, "_legacy_endpoint_configured")


def test_project_graph_runtime_has_no_legacy_orchestrator_configuration_seam():
    config_source = (_BACKEND_ROOT / "core" / "config.py").read_text(encoding="utf-8")
    import_source = (
        _BACKEND_ROOT / "services" / "email_import_service.py"
    ).read_text(encoding="utf-8")

    assert "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL" not in config_source
    function_start = import_source.index("async def _extract_project_semantics_for_import")
    function_end = import_source.index(
        "\n\nasync def _persist_project_graph_projection", function_start
    )
    function_source = import_source[function_start:function_end]
    assert "embedding_provider" not in function_source
    assert "KgExtractorContext()" in function_source


@pytest.mark.asyncio
async def test_orchestrator_selector_has_no_dormant_raw_llm_transport(monkeypatch):
    source = inspect.getsource(LlmGroundedExtractor.extract)
    assert "extract_project_semantics_llm" not in source

    raw_transport = AsyncMock(return_value=object())
    monkeypatch.setattr(registry_module, "extract_project_semantics_llm", raw_transport)

    with pytest.raises(ExtractorUnavailableError, match="released consumer contract"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_ORCHESTRATOR,
            context=KgExtractorContext(),
        )

    raw_transport.assert_not_awaited()
