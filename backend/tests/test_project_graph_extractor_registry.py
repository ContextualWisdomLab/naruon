"""Tests for the pluggable, named + versioned KG extractor seam.

The seam turns what used to be a hardcoded ``if/else`` extractor selection into a
registry keyed by the stable ``PROJECT_GRAPH_EXTRACTOR`` selector value. Two
invariants are load-bearing and asserted here:

1. **The deterministic keyword extractor is the structural fallback.** Every
   resolved chain ends at it, so "rule-based extraction is fallback/reference
   only" is guaranteed by construction, not by an ad-hoc branch.
2. **LLM-backed extractors degrade, never fail the projection.** A missing
   credential or unconfigured orchestrator endpoint raises
   ``ExtractorUnavailableError`` so the runner advances down the chain rather
   than propagating.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

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

# The extraction cores are imported into the registry module namespace, so
# tests patch them by dotted path there (keeps a single import style for the
# module under test — no module-alias import alongside the ``from`` import).
_REGISTRY_MODULE = "services.project_graph.extractor_registry"


def _segment(uid: str = "seg1", text: str = "The system must support export.") -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid=uid,
        source_kind="email_body",
        source_record_uid="email:1",
        safe_text_content=text,
        heading_path=None,
        segment_path="body/0",
        ordinal_index=0,
    )


def _llm_context() -> KgExtractorContext:
    return KgExtractorContext(api_key="key", base_url=None, model="gpt-test")


def _patch_cores(monkeypatch, *, llm, keyword):
    """Patch the two extraction cores where the registry imports them."""
    monkeypatch.setattr(f"{_REGISTRY_MODULE}.extract_project_semantics_llm", llm)
    monkeypatch.setattr(f"{_REGISTRY_MODULE}.extract_project_semantics", keyword)


# --- Contract / registry shape ---------------------------------------------


def test_registered_extractors_conform_to_protocol():
    registry = build_default_registry()
    assert set(registry.selectors()) == {
        SELECTOR_KEYWORD,
        SELECTOR_LLM,
        SELECTOR_ORCHESTRATOR,
    }
    for selector in registry.selectors():
        extractor = registry.get(selector)
        assert isinstance(extractor, KgExtractor)
        assert isinstance(extractor.name, str) and extractor.name
        assert isinstance(extractor.version, str) and extractor.version


def test_extractor_identity_matches_module_constants():
    registry = build_default_registry()
    assert registry.get(SELECTOR_KEYWORD).name == DETERMINISTIC_EXTRACTOR_NAME
    assert registry.get(SELECTOR_LLM).name == LLM_EXTRACTOR_NAME
    # The orchestrator-routed variant is the same grounded LLM extractor
    # (identity/provenance is the extractor, not the transport).
    assert registry.get(SELECTOR_ORCHESTRATOR).name == LLM_EXTRACTOR_NAME
    assert registry.get(SELECTOR_ORCHESTRATOR).routed_via_orchestrator is True
    assert registry.get(SELECTOR_LLM).routed_via_orchestrator is False


# --- Chain resolution: deterministic is always the terminal fallback --------


def test_keyword_chain_is_deterministic_only():
    chain = resolve_extractor_chain(SELECTOR_KEYWORD)
    assert [e.name for e in chain] == [DETERMINISTIC_EXTRACTOR_NAME]


def test_llm_chain_falls_back_to_deterministic():
    chain = resolve_extractor_chain(SELECTOR_LLM)
    assert [e.name for e in chain] == [LLM_EXTRACTOR_NAME, DETERMINISTIC_EXTRACTOR_NAME]


def test_orchestrator_chain_falls_back_to_deterministic():
    chain = resolve_extractor_chain(SELECTOR_ORCHESTRATOR)
    assert chain[0].name == LLM_EXTRACTOR_NAME
    assert chain[0].routed_via_orchestrator is True
    assert chain[-1].name == DETERMINISTIC_EXTRACTOR_NAME


def test_unknown_selector_falls_back_to_deterministic_only():
    chain = resolve_extractor_chain("bogus_selector")
    assert [e.name for e in chain] == [DETERMINISTIC_EXTRACTOR_NAME]


@pytest.mark.parametrize(
    "selector",
    [SELECTOR_KEYWORD, SELECTOR_LLM, SELECTOR_ORCHESTRATOR, "unknown"],
)
def test_deterministic_is_always_the_terminal_fallback(selector):
    chain = resolve_extractor_chain(selector)
    assert chain, "chain must never be empty"
    assert chain[-1].name == DETERMINISTIC_EXTRACTOR_NAME


def test_registry_never_drops_the_keyword_fallback():
    registry = KgExtractorRegistry()
    # A registry without the keyword fallback is a programming error.
    with pytest.raises(KeyError):
        registry.resolve_chain(SELECTOR_LLM)


# --- run_extraction: selection + graceful degradation -----------------------


@pytest.mark.asyncio
async def test_run_extraction_uses_primary_on_success(monkeypatch):
    sentinel = object()
    llm_mock = AsyncMock(return_value=sentinel)
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    result = await run_extraction(
        [_segment()], selector=SELECTOR_LLM, context=_llm_context()
    )

    assert result is sentinel
    llm_mock.assert_awaited_once()
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_extraction_falls_back_when_llm_raises(monkeypatch):
    keyword_sentinel = object()
    _patch_cores(
        monkeypatch,
        llm=AsyncMock(side_effect=RuntimeError("provider down")),
        keyword=Mock(return_value=keyword_sentinel),
    )

    result = await run_extraction(
        [_segment()], selector=SELECTOR_LLM, context=_llm_context()
    )

    assert result is keyword_sentinel


@pytest.mark.asyncio
async def test_run_extraction_falls_back_when_credentials_missing(monkeypatch):
    keyword_sentinel = object()
    llm_mock = AsyncMock()
    _patch_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_sentinel)
    )

    # No api_key/model -> the LLM extractor is unavailable and the chain
    # advances to the deterministic fallback without a network call.
    result = await run_extraction(
        [_segment()], selector=SELECTOR_LLM, context=KgExtractorContext()
    )

    assert result is keyword_sentinel
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_keyword_selector_never_calls_llm(monkeypatch):
    keyword_sentinel = object()
    llm_mock = AsyncMock()
    _patch_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_sentinel)
    )

    result = await run_extraction(
        [_segment()], selector=SELECTOR_KEYWORD, context=_llm_context()
    )

    assert result is keyword_sentinel
    llm_mock.assert_not_awaited()


# --- Orchestrator routing ---------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_routing_targets_the_orchestrator_base_url(monkeypatch):
    sentinel = object()
    llm_mock = AsyncMock(return_value=sentinel)
    _patch_cores(monkeypatch, llm=llm_mock, keyword=Mock())

    context = KgExtractorContext(
        api_key="key",
        base_url="https://direct-provider.example",
        model="gpt-test",
        orchestrator_base_url="https://orchestrator.example/v1",
    )
    result = await run_extraction(
        [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
    )

    assert result is sentinel
    # The extraction call is routed at the orchestrator endpoint, NOT the raw
    # provider base URL — this is what "route LLM extraction through
    # contextual-orchestrator" means at the transport seam.
    assert llm_mock.await_args.kwargs["base_url"] == "https://orchestrator.example/v1"
    # The model sent must be the fixed virtual pool id, never the caller's
    # direct-provider model string — the orchestrator gateway resolves
    # "orchestrator/free" itself to a zero-cost/ZDR route; forwarding a
    # literal provider model would bypass that governed pool selection
    # entirely (ContextualWisdomLab/.github docs/adr/
    # 0003-contextual-orchestrator-vendored-free-zdr.md).
    assert llm_mock.await_args.kwargs["model"] == "orchestrator/free"
    assert llm_mock.await_args.kwargs["model"] != context.model


@pytest.mark.asyncio
async def test_orchestrator_routing_falls_back_when_unconfigured(monkeypatch):
    keyword_sentinel = object()
    llm_mock = AsyncMock()
    _patch_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_sentinel)
    )

    # orchestrator selector but no orchestrator_base_url resolved -> unavailable,
    # so it fails closed to the deterministic fallback without a network call.
    context = KgExtractorContext(api_key="key", model="gpt-test")
    result = await run_extraction(
        [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
    )

    assert result is keyword_sentinel
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_llm_routing_uses_provider_base_url(monkeypatch):
    llm_mock = AsyncMock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=Mock())

    context = KgExtractorContext(
        api_key="key",
        base_url="https://direct-provider.example",
        model="gpt-test",
        orchestrator_base_url="https://orchestrator.example/v1",
    )
    await run_extraction([_segment()], selector=SELECTOR_LLM, context=context)

    # The non-orchestrator LLM selector keeps hitting the raw provider base URL
    # and its own configured model — the pool-id pin is orchestrator-only.
    assert llm_mock.await_args.kwargs["base_url"] == "https://direct-provider.example"
    assert llm_mock.await_args.kwargs["model"] == "gpt-test"


# --- Extractor units --------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_extractor_ignores_llm_context(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        f"{_REGISTRY_MODULE}.extract_project_semantics", Mock(return_value=sentinel)
    )
    extractor = DeterministicKeywordExtractor()
    result = await extractor.extract([_segment()], context=KgExtractorContext())
    assert result is sentinel


@pytest.mark.asyncio
async def test_llm_extractor_requires_credentials():
    extractor = LlmGroundedExtractor(routed_via_orchestrator=False)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract([_segment()], context=KgExtractorContext())


@pytest.mark.asyncio
async def test_orchestrator_extractor_requires_endpoint():
    extractor = LlmGroundedExtractor(routed_via_orchestrator=True)
    # Credentials present, but no orchestrator endpoint -> unavailable.
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract(
            [_segment()], context=KgExtractorContext(api_key="key", model="gpt-test")
        )


@pytest.mark.asyncio
async def test_orchestrator_routing_succeeds_without_context_model(monkeypatch):
    """Orchestrator routing must not require context.model.

    _resolve_model always supplies the fixed ORCHESTRATOR_POOL_MODEL for
    orchestrator-routed requests, regardless of context.model. Gating
    availability on context.model (as the extractor previously did via
    ``has_llm_credentials``) made an otherwise-valid orchestrator request
    unavailable -- and silently degrade to keyword extraction -- whenever the
    unrelated direct-provider model setting was unconfigured.
    """
    sentinel = object()
    llm_mock = AsyncMock(return_value=sentinel)
    _patch_cores(monkeypatch, llm=llm_mock, keyword=Mock())

    context = KgExtractorContext(
        api_key="key",
        orchestrator_base_url="https://orchestrator.example/v1",
    )
    result = await run_extraction(
        [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
    )

    assert result is sentinel
    llm_mock.assert_awaited_once()
    assert llm_mock.await_args.kwargs["model"] == "orchestrator/free"


@pytest.mark.asyncio
async def test_direct_llm_routing_requires_model_even_with_api_key():
    # Direct-provider mode still fails closed on a missing model: unlike
    # orchestrator mode, _resolve_model returns context.model verbatim here,
    # so an api_key alone is not sufficient.
    extractor = LlmGroundedExtractor(routed_via_orchestrator=False)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract([_segment()], context=KgExtractorContext(api_key="key"))


@pytest.mark.asyncio
async def test_direct_llm_routing_rejects_blank_model():
    # A blank (non-None) context.model must fail closed too, not be sent to
    # the provider as an empty-string model id: `if model is None` alone
    # would let "" through and only discover the problem after a failed
    # network round-trip. Devin Review caught this in review of
    # ContextualWisdomLab/naruon#1525.
    extractor = LlmGroundedExtractor(routed_via_orchestrator=False)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract(
            [_segment()], context=KgExtractorContext(api_key="key", model="")
        )


def test_custom_extractor_can_register_into_the_seam():
    """A plugin/extractor registers by selector without editing core ingest."""

    class _CustomExtractor:
        name = "custom_project_graph"
        version = "1.0.0"
        routed_via_orchestrator = False

        async def extract(self, segments, *, context):  # pragma: no cover - shape only
            raise NotImplementedError

    registry = build_default_registry()
    registry.register("custom", _CustomExtractor())
    assert registry.get("custom").name == "custom_project_graph"
    # It still falls back to the deterministic reference extractor.
    chain = registry.resolve_chain("custom")
    assert chain[0].name == "custom_project_graph"
    assert chain[-1].name == DETERMINISTIC_EXTRACTOR_NAME
