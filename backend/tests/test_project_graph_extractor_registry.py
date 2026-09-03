"""Behavioral contract for the project-graph extractor registry."""

from dataclasses import fields
from unittest.mock import AsyncMock, Mock

import pytest

from services.project_graph import extractor_registry as registry_module
from services.project_graph.extractor_registry import (
    DETERMINISTIC_EXTRACTOR_NAME,
    LLM_EXTRACTOR_NAME,
    SELECTOR_KEYWORD,
    SELECTOR_LLM,
    SELECTOR_ORCHESTRATOR,
    DeterministicKeywordExtractor,
    ExtractorUnavailableError,
    KgExtractor,
    KgExtractorContext,
    KgExtractorRegistry,
    LlmGroundedExtractor,
    build_default_registry,
    resolve_extractor_chain,
    run_extraction,
)
from services.project_graph.models import ProjectSourceSegment


def _segment() -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid="seg1",
        source_kind="email_body",
        source_record_uid="email:1",
        safe_text_content="The system must support export.",
        heading_path=None,
        segment_path="body/0",
        ordinal_index=0,
    )


def test_default_registry_exposes_stable_selector_identities():
    registry = build_default_registry()
    assert set(registry.selectors()) == {
        SELECTOR_KEYWORD,
        SELECTOR_LLM,
        SELECTOR_ORCHESTRATOR,
    }
    assert registry.get(SELECTOR_KEYWORD).name == DETERMINISTIC_EXTRACTOR_NAME
    assert registry.get(SELECTOR_LLM).name == LLM_EXTRACTOR_NAME
    assert registry.get(SELECTOR_ORCHESTRATOR).name == LLM_EXTRACTOR_NAME
    assert registry.get(SELECTOR_KEYWORD).requires_llm_capability is False
    assert registry.get(SELECTOR_LLM).requires_llm_capability is True
    assert registry.get(SELECTOR_ORCHESTRATOR).requires_llm_capability is True
    for selector in registry.selectors():
        assert isinstance(registry.get(selector), KgExtractor)


def test_keyword_is_explicit_mode_and_llm_modes_have_no_keyword_fallback():
    assert [item.name for item in resolve_extractor_chain(SELECTOR_KEYWORD)] == [
        DETERMINISTIC_EXTRACTOR_NAME
    ]
    assert [item.name for item in resolve_extractor_chain(SELECTOR_LLM)] == [
        LLM_EXTRACTOR_NAME
    ]
    assert [item.name for item in resolve_extractor_chain(SELECTOR_ORCHESTRATOR)] == [
        LLM_EXTRACTOR_NAME
    ]


def test_unknown_selector_fails_closed():
    with pytest.raises(ExtractorUnavailableError, match="unrecognized"):
        resolve_extractor_chain("bogus_selector")


def test_registry_without_keyword_fallback_is_programming_error():
    registry = KgExtractorRegistry()
    with pytest.raises(KeyError):
        registry.resolve_chain(SELECTOR_LLM)


def test_context_has_no_authority_bearing_dataclass_fields():
    assert tuple(field.name for field in fields(KgExtractorContext)) == ()
    context = KgExtractorContext(
        api_key="must-not-survive",
        orchestrator_base_url="https://orchestrator.example/v1",
        orchestrator_model="must-not-survive",
    )
    assert not hasattr(context, "api_key")
    assert not hasattr(context, "orchestrator_base_url")
    assert not hasattr(context, "orchestrator_model")
    assert context._legacy_endpoint_configured is True


@pytest.mark.asyncio
async def test_keyword_selector_runs_deterministic_core(monkeypatch):
    sentinel = object()
    keyword = Mock(return_value=sentinel)
    monkeypatch.setattr(registry_module, "extract_project_semantics", keyword)

    result = await run_extraction(
        [_segment()], selector=SELECTOR_KEYWORD, context=KgExtractorContext()
    )

    assert result is sentinel
    keyword.assert_called_once()


@pytest.mark.asyncio
async def test_direct_llm_selector_is_policy_disabled_even_with_legacy_inputs(monkeypatch):
    raw_transport = AsyncMock()
    monkeypatch.setattr(registry_module, "extract_project_semantics_llm", raw_transport)

    with pytest.raises(ExtractorUnavailableError, match="disabled"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_LLM,
            context=KgExtractorContext(
                api_key="secret",
                orchestrator_base_url="https://orchestrator.example/v1",
                orchestrator_model="provider/model",
            ),
        )

    raw_transport.assert_not_awaited()


@pytest.mark.asyncio
async def test_orchestrator_selector_fails_closed_without_endpoint(monkeypatch):
    raw_transport = AsyncMock()
    monkeypatch.setattr(registry_module, "extract_project_semantics_llm", raw_transport)

    with pytest.raises(ExtractorUnavailableError, match="endpoint is not configured"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_ORCHESTRATOR,
            context=KgExtractorContext(),
        )

    raw_transport.assert_not_awaited()


@pytest.mark.asyncio
async def test_orchestrator_selector_rejects_raw_transport_even_when_legacy_values_exist(
    monkeypatch,
):
    raw_transport = AsyncMock(return_value=object())
    monkeypatch.setattr(registry_module, "extract_project_semantics_llm", raw_transport)

    with pytest.raises(ExtractorUnavailableError, match="no consumer release"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_ORCHESTRATOR,
            context=KgExtractorContext(
                api_key="tenant-provider-secret",
                orchestrator_base_url="https://orchestrator.example/v1",
                orchestrator_model="provider/model",
            ),
        )

    raw_transport.assert_not_awaited()


def test_custom_non_llm_extractor_keeps_keyword_fallback():
    class CustomExtractor:
        name = "custom_project_graph"
        version = "1.0.0"
        requires_llm_capability = False

        async def extract(self, segments, *, context):
            raise ExtractorUnavailableError("custom unavailable")

    registry = build_default_registry()
    registry.register("custom", CustomExtractor())
    assert [item.name for item in registry.resolve_chain("custom")] == [
        "custom_project_graph",
        DETERMINISTIC_EXTRACTOR_NAME,
    ]


@pytest.mark.asyncio
async def test_custom_non_llm_failure_can_degrade_to_keyword(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        registry_module, "extract_project_semantics", Mock(return_value=sentinel)
    )

    class CustomExtractor:
        name = "custom_project_graph"
        version = "1.0.0"
        requires_llm_capability = False

        async def extract(self, segments, *, context):
            raise RuntimeError("custom failed")

    registry = build_default_registry()
    registry.register("custom", CustomExtractor())
    result = await run_extraction(
        [_segment()],
        selector="custom",
        context=KgExtractorContext(),
        registry=registry,
    )
    assert result is sentinel


def test_custom_llm_extractor_gets_no_fallback():
    class CustomLlmExtractor:
        name = "custom_llm_project_graph"
        version = "1.0.0"
        requires_llm_capability = True

        async def extract(self, segments, *, context):
            raise NotImplementedError

    registry = build_default_registry()
    registry.register("custom_llm", CustomLlmExtractor())
    assert [item.name for item in registry.resolve_chain("custom_llm")] == [
        "custom_llm_project_graph"
    ]


def test_nonconforming_plugin_fails_loudly():
    class NonConformingExtractor:
        name = "forgot_the_contract"
        version = "1.0.0"

        async def extract(self, segments, *, context):
            raise NotImplementedError

    registry = build_default_registry()
    registry.register("non_conforming", NonConformingExtractor())
    with pytest.raises(AttributeError, match="requires_llm_capability"):
        registry.resolve_chain("non_conforming")


@pytest.mark.asyncio
async def test_llm_terminal_failure_is_not_replaced_by_keyword(monkeypatch):
    class FailingLlmExtractor:
        name = "failing_llm"
        version = "1.0.0"
        requires_llm_capability = True

        async def extract(self, segments, *, context):
            raise RuntimeError("provider path must remain unavailable")

    keyword = Mock(return_value=object())
    monkeypatch.setattr(registry_module, "extract_project_semantics", keyword)
    registry = build_default_registry()
    registry.register("failing_llm", FailingLlmExtractor())

    with pytest.raises(RuntimeError, match="provider path must remain unavailable"):
        await run_extraction(
            [_segment()],
            selector="failing_llm",
            context=KgExtractorContext(),
            registry=registry,
        )

    keyword.assert_not_called()
