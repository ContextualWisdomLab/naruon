"""Tests for the pluggable, named + versioned KG extractor seam.

The seam turns what used to be a hardcoded ``if/else`` extractor selection into a
registry keyed by the stable ``PROJECT_GRAPH_EXTRACTOR`` selector value. Two
invariants are load-bearing and asserted here:

1. **The deterministic keyword extractor is available as its own product
   mode, and as a fallback only for extractors that opt into degrading.**
   ``SELECTOR_KEYWORD`` (and an unrecognized selector) always resolves to it
   directly.
2. **LLM-backed extractors (``requires_llm_capability = True``) never
   degrade.** An unavailable or failed :data:`SELECTOR_LLM` or
   :data:`SELECTOR_ORCHESTRATOR` request propagates through
   :func:`run_extraction` rather than silently resolving to a
   keyword-derived result (ADR-0005 Revision 8: a deterministic semantic
   substitute must not masquerade as successful LLM work). Today both are
   also unconditionally unavailable: ``llm`` is policy-disabled (Naruon
   holds no direct-provider LLM authority outside contextual-orchestrator's
   released consumer contract, which does not exist), and ``orchestrator``
   has nothing to populate ``context.orchestrator_model`` from until that
   contract ships.
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


def _orchestrator_context(**overrides) -> KgExtractorContext:
    """A fully-configured, valid orchestrator-mode context for success-path tests."""
    defaults = dict(
        api_key="key",
        orchestrator_base_url="https://orchestrator.example/v1",
        orchestrator_model="co-contract-resolved-model",
    )
    defaults.update(overrides)
    return KgExtractorContext(**defaults)


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
    assert registry.get(SELECTOR_KEYWORD).requires_llm_capability is False
    assert registry.get(SELECTOR_LLM).name == LLM_EXTRACTOR_NAME
    # The orchestrator-routed variant is the same grounded LLM extractor
    # (identity/provenance is the extractor, not the transport).
    assert registry.get(SELECTOR_ORCHESTRATOR).name == LLM_EXTRACTOR_NAME
    assert registry.get(SELECTOR_ORCHESTRATOR).routed_via_orchestrator is True
    assert registry.get(SELECTOR_LLM).routed_via_orchestrator is False
    assert registry.get(SELECTOR_ORCHESTRATOR).requires_llm_capability is True
    assert registry.get(SELECTOR_LLM).requires_llm_capability is True


# --- Chain resolution --------------------------------------------------------


def test_keyword_chain_is_deterministic_only():
    chain = resolve_extractor_chain(SELECTOR_KEYWORD)
    assert [e.name for e in chain] == [DETERMINISTIC_EXTRACTOR_NAME]


def test_llm_chain_has_no_fallback():
    """requires_llm_capability=True means the chain is the extractor alone."""
    chain = resolve_extractor_chain(SELECTOR_LLM)
    assert [e.name for e in chain] == [LLM_EXTRACTOR_NAME]


def test_orchestrator_chain_has_no_fallback():
    chain = resolve_extractor_chain(SELECTOR_ORCHESTRATOR)
    assert [e.name for e in chain] == [LLM_EXTRACTOR_NAME]
    assert chain[0].routed_via_orchestrator is True


def test_unknown_selector_falls_back_to_deterministic_only():
    chain = resolve_extractor_chain("bogus_selector")
    assert [e.name for e in chain] == [DETERMINISTIC_EXTRACTOR_NAME]


@pytest.mark.parametrize("selector", [SELECTOR_KEYWORD, "unknown"])
def test_deterministic_selectors_resolve_only_to_the_keyword_extractor(selector):
    chain = resolve_extractor_chain(selector)
    assert [e.name for e in chain] == [DETERMINISTIC_EXTRACTOR_NAME]


@pytest.mark.parametrize("selector", [SELECTOR_LLM, SELECTOR_ORCHESTRATOR])
def test_llm_backed_selectors_never_resolve_to_the_keyword_extractor(selector):
    chain = resolve_extractor_chain(selector)
    assert DETERMINISTIC_EXTRACTOR_NAME not in [e.name for e in chain]


def test_registry_never_drops_the_keyword_fallback():
    registry = KgExtractorRegistry()
    # A registry without the keyword fallback is a programming error --
    # resolve_chain looks it up unconditionally before deciding whether the
    # resolved extractor is LLM-backed, so this still raises regardless of
    # selector.
    with pytest.raises(KeyError):
        registry.resolve_chain(SELECTOR_LLM)


# --- run_extraction: selection + truthful unavailability --------------------


@pytest.mark.asyncio
async def test_run_extraction_uses_primary_on_success(monkeypatch):
    sentinel = object()
    llm_mock = AsyncMock(return_value=sentinel)
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    result = await run_extraction(
        [_segment()], selector=SELECTOR_ORCHESTRATOR, context=_orchestrator_context()
    )

    assert result is sentinel
    llm_mock.assert_awaited_once()
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_extraction_propagates_when_orchestrator_extraction_raises(monkeypatch):
    """A genuine extraction failure must not become a keyword result."""
    _patch_cores(
        monkeypatch,
        llm=AsyncMock(side_effect=RuntimeError("provider down")),
        keyword=Mock(return_value=object()),
    )

    with pytest.raises(RuntimeError, match="provider down"):
        await run_extraction(
            [_segment()], selector=SELECTOR_ORCHESTRATOR, context=_orchestrator_context()
        )


@pytest.mark.asyncio
async def test_run_extraction_propagates_when_orchestrator_credentials_missing(monkeypatch):
    llm_mock = AsyncMock()
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    # No api_key -> the orchestrator extractor is unavailable, and with no
    # fallback in its chain, run_extraction propagates rather than degrading.
    with pytest.raises(ExtractorUnavailableError):
        await run_extraction(
            [_segment()], selector=SELECTOR_ORCHESTRATOR, context=KgExtractorContext()
        )
    llm_mock.assert_not_awaited()
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_extraction_propagates_when_direct_llm_selected(monkeypatch):
    """SELECTOR_LLM is policy-disabled and never falls back to keyword either."""
    llm_mock = AsyncMock()
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    with pytest.raises(ExtractorUnavailableError, match="disabled"):
        await run_extraction(
            [_segment()],
            selector=SELECTOR_LLM,
            context=KgExtractorContext(api_key="key"),
        )
    llm_mock.assert_not_awaited()
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_keyword_selector_never_calls_llm(monkeypatch):
    keyword_sentinel = object()
    llm_mock = AsyncMock()
    _patch_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_sentinel)
    )

    result = await run_extraction(
        [_segment()], selector=SELECTOR_KEYWORD, context=_orchestrator_context()
    )

    assert result is keyword_sentinel
    llm_mock.assert_not_awaited()


# --- Orchestrator routing ---------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_routing_targets_the_orchestrator_base_url(monkeypatch):
    sentinel = object()
    llm_mock = AsyncMock(return_value=sentinel)
    _patch_cores(monkeypatch, llm=llm_mock, keyword=Mock())

    context = _orchestrator_context()
    result = await run_extraction(
        [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
    )

    assert result is sentinel
    # The extraction call is routed at the orchestrator endpoint — this is
    # what "route LLM extraction through contextual-orchestrator" means at
    # the transport seam.
    assert llm_mock.await_args.kwargs["base_url"] == "https://orchestrator.example/v1"
    # The model sent is exactly context.orchestrator_model, forwarded
    # verbatim -- this extractor picks nothing itself (ADR-0005 Revision 7:
    # hardcoding a pool id here was a boundary violation).
    assert llm_mock.await_args.kwargs["model"] == context.orchestrator_model


@pytest.mark.asyncio
async def test_orchestrator_routing_propagates_when_unconfigured(monkeypatch):
    llm_mock = AsyncMock()
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    # orchestrator selector but no orchestrator_base_url resolved -> unavailable,
    # and with no fallback in its chain, this propagates rather than degrading.
    context = KgExtractorContext(api_key="key", orchestrator_model="some-model")
    with pytest.raises(ExtractorUnavailableError, match="endpoint is not configured"):
        await run_extraction(
            [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
        )
    llm_mock.assert_not_awaited()
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_routing_propagates_without_a_configured_model(monkeypatch):
    """No hardcoded model to fall back on, and no keyword fallback either.

    A prior revision of this extractor substituted a Naruon-hardcoded virtual
    pool id ("orchestrator/free") whenever the model was unset, so
    orchestrator-routed requests always "succeeded" regardless of whether a
    real model was configured -- itself the bug ADR-0005 Revision 7
    corrects. A later revision (8) additionally stopped silently degrading
    to a keyword-derived result: contextual-orchestrator has published no
    released consumer contract yet (0 GitHub Releases), so nothing
    legitimately populates context.orchestrator_model today, and the correct
    behavior is to propagate that unavailability, not mask it.
    """
    llm_mock = AsyncMock()
    keyword_mock = Mock(return_value=object())
    _patch_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)

    context = KgExtractorContext(
        api_key="key",
        orchestrator_base_url="https://orchestrator.example/v1",
    )
    with pytest.raises(ExtractorUnavailableError, match="no consumer release"):
        await run_extraction(
            [_segment()], selector=SELECTOR_ORCHESTRATOR, context=context
        )
    llm_mock.assert_not_awaited()
    keyword_mock.assert_not_called()


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
async def test_direct_llm_extractor_is_unconditionally_disabled():
    """Policy-disabled means no context can make it available.

    Not a missing-configuration gate: even a fully "valid-looking" context
    (credentials present) must still fail, and for the disabled-by-policy
    reason specifically, not a credentials/model complaint.
    """
    extractor = LlmGroundedExtractor(routed_via_orchestrator=False)
    with pytest.raises(ExtractorUnavailableError, match="disabled"):
        await extractor.extract([_segment()], context=KgExtractorContext(api_key="key"))


@pytest.mark.asyncio
async def test_orchestrator_extractor_requires_endpoint():
    extractor = LlmGroundedExtractor(routed_via_orchestrator=True)
    # Credentials present, but no orchestrator endpoint -> unavailable.
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract(
            [_segment()], context=KgExtractorContext(api_key="key")
        )


@pytest.mark.asyncio
async def test_orchestrator_extractor_requires_credentials():
    extractor = LlmGroundedExtractor(routed_via_orchestrator=True)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract([_segment()], context=KgExtractorContext())


@pytest.mark.asyncio
async def test_orchestrator_routing_rejects_blank_model():
    # A blank (non-None) orchestrator_model must fail closed too, not be
    # sent as an empty-string model id: `if model is None` alone would let
    # "" through and only discover the problem after a failed network
    # round-trip. (Originally caught by Devin Review against context.model
    # in direct-provider mode, ContextualWisdomLab/naruon#1525; the same
    # validation now lives on context.orchestrator_model, the only field
    # still reachable by extract().)
    extractor = LlmGroundedExtractor(routed_via_orchestrator=True)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract(
            [_segment()],
            context=KgExtractorContext(
                api_key="key",
                orchestrator_base_url="https://orchestrator.example/v1",
                orchestrator_model="",
            ),
        )


@pytest.mark.asyncio
async def test_orchestrator_routing_rejects_whitespace_only_model():
    # A whitespace-only orchestrator_model ("   ") is truthy so `if not
    # model` alone lets it through as an invalid model id sent straight to
    # the gateway, only failing after a network round-trip.
    extractor = LlmGroundedExtractor(routed_via_orchestrator=True)
    with pytest.raises(ExtractorUnavailableError):
        await extractor.extract(
            [_segment()],
            context=KgExtractorContext(
                api_key="key",
                orchestrator_base_url="https://orchestrator.example/v1",
                orchestrator_model="   ",
            ),
        )


def test_custom_extractor_can_register_into_the_seam():
    """A plugin/extractor registers by selector without editing core ingest.

    A custom extractor that does not opt into requires_llm_capability keeps
    the deterministic fallback behind it -- opting out of the fallback is a
    deliberate choice an extractor makes, not the registry's default.
    """

    class _CustomExtractor:
        name = "custom_project_graph"
        version = "1.0.0"
        routed_via_orchestrator = False

        async def extract(self, segments, *, context):  # pragma: no cover - shape only
            raise NotImplementedError

    registry = build_default_registry()
    registry.register("custom", _CustomExtractor())
    assert registry.get("custom").name == "custom_project_graph"
    chain = registry.resolve_chain("custom")
    assert chain[0].name == "custom_project_graph"
    assert chain[-1].name == DETERMINISTIC_EXTRACTOR_NAME
