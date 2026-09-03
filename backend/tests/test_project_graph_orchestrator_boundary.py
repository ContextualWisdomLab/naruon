"""Fail-closed contract for project-graph LLM ownership."""

from dataclasses import fields
import inspect
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
    context = KgExtractorContext(
        api_key="secret",
        orchestrator_base_url="https://orchestrator.example/v1",
        orchestrator_model="provider/model",
    )
    assert not hasattr(context, "api_key")
    assert not hasattr(context, "orchestrator_base_url")
    assert not hasattr(context, "orchestrator_model")


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
