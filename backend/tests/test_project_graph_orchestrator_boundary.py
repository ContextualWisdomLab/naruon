"""Fail-closed contract for project-graph LLM ownership.

Naruon owns project-graph semantics and selector policy, not upstream LLM
provider credentials, raw OpenAI-compatible transport, or model routing.
Until contextual-orchestrator publishes an immutable consumer release, the
orchestrator selector must remain unavailable without retaining a dormant raw
transport path that configuration could accidentally make reachable.
"""

from dataclasses import fields
import inspect

import pytest

import services.email_import_service as import_service
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
    """The extractor context cannot become a second provider-routing contract."""
    assert tuple(field.name for field in fields(KgExtractorContext)) == ()


def test_import_projection_does_not_forward_provider_credentials_or_raw_gateway_url():
    """Email embedding credentials are unrelated to project-graph LLM authority."""
    source = inspect.getsource(import_service._extract_project_semantics_for_import)
    assert "embedding_provider.api_key" not in source
    assert "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL" not in source
    assert not hasattr(import_service.settings, "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL")


@pytest.mark.asyncio
async def test_orchestrator_selector_has_no_dormant_raw_llm_transport():
    """No release means fail closed before any local OpenAI-compatible call."""
    source = inspect.getsource(LlmGroundedExtractor.extract)
    assert "extract_project_semantics_llm" not in source

    with pytest.raises(ExtractorUnavailableError, match="released consumer contract"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_ORCHESTRATOR,
            context=KgExtractorContext(),
        )
