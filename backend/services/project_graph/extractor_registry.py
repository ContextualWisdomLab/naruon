"""Pluggable, named + versioned extractor seam for the project knowledge graph.

The semantic project graph is populated by *extractors* that turn grounded
content segments into cited objects and edges. Historically the import pipeline
chose between them with a hardcoded ``if settings.PROJECT_GRAPH_EXTRACTOR == "llm"
… else keyword`` branch. This module replaces that branch with a real, stable
seam:

* a typed :class:`KgExtractor` contract (name + version + ``extract``),
* a :class:`KgExtractorRegistry` keyed by the stable ``PROJECT_GRAPH_EXTRACTOR``
  selector value, into which additional extractors (including future plugins,
  per the platform plan's ``kg.extractor`` extension point) register without
  editing core ingest,
* :func:`resolve_extractor_chain` / :func:`run_extraction`, which build an
  ordered fallback chain whose terminal element is the deterministic
  reference extractor — encoding "rule-based extraction is fallback/reference
  only" structurally rather than in an ad-hoc branch.

Routing LLM extraction through **contextual-orchestrator** is modelled as a
transport concern: the orchestrator is an OpenAI-compatible gateway, so the
``orchestrator`` selector reuses the same grounded LLM extractor but points its
SSRF-allowlisted client at the orchestrator base URL resolved by the caller
(:class:`KgExtractorContext`). If that endpoint is unset or the provider
credentials are missing, the extractor raises :class:`ExtractorUnavailableError`
and the runner fails closed to the deterministic reference extractor — the
projection is best-effort and never lost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from .extractors import (
    EXTRACTOR_NAME as DETERMINISTIC_EXTRACTOR_NAME,
    EXTRACTOR_VERSION as DETERMINISTIC_EXTRACTOR_VERSION,
    extract_project_semantics,
)
from .llm_extractor import (
    LLM_EXTRACTOR_NAME,
    LLM_EXTRACTOR_VERSION,
    extract_project_semantics_llm,
)
from .models import ProjectSemanticExtractionResult, ProjectSourceSegment

logger = logging.getLogger(__name__)

# Stable selector keys the ``PROJECT_GRAPH_EXTRACTOR`` config chooses among.
SELECTOR_KEYWORD = "keyword"
SELECTOR_LLM = "llm"
SELECTOR_ORCHESTRATOR = "orchestrator"


class ExtractorUnavailableError(RuntimeError):
    """An extractor cannot run in the current context.

    Raised for a *recoverable* precondition — missing LLM credentials, an
    unconfigured orchestrator endpoint — so :func:`run_extraction` advances to
    the next extractor in the fallback chain instead of propagating. It is not
    used for genuine extraction failures (those surface as ordinary exceptions,
    which the runner also treats as fall-through).
    """


@dataclass(frozen=True, slots=True)
class KgExtractorContext:
    """Per-run resources an extractor may consume.

    Deliberately small and provider-agnostic so extractors stay decoupled from
    import-service internals (no ambient session/settings authority).
    ``api_key``/``base_url``/``model`` describe the OpenAI-compatible LLM
    endpoint a direct LLM extractor calls; ``orchestrator_base_url`` is the
    OpenAI-compatible contextual-orchestrator gateway an orchestrator-routed
    extractor targets instead of the raw provider.
    """

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    orchestrator_base_url: str | None = None

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.api_key and self.model)


@runtime_checkable
class KgExtractor(Protocol):
    """Stable, named + versioned contract for a project-graph extractor.

    Implementations self-identify with ``name``/``version`` (recorded as
    per-row provenance on the objects/edges they emit) and turn segments into a
    :class:`ProjectSemanticExtractionResult`. ``extract`` is always awaited so
    pure/deterministic and LLM-backed extractors compose uniformly behind the
    seam.
    """

    name: str
    version: str

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        # Structural contract only; concrete extractors override this. The
        # Protocol method is never invoked directly (no implementation calls
        # super().extract), so raising here is unreachable at runtime and only
        # documents that the method is abstract.
        raise NotImplementedError


class DeterministicKeywordExtractor:
    """The deterministic keyword reference extractor and last-resort fallback.

    Pure and dependency-free: it needs no credentials and always produces a
    result, which is exactly why the registry keeps it as the terminal element
    of every fallback chain.
    """

    name = DETERMINISTIC_EXTRACTOR_NAME
    version = DETERMINISTIC_EXTRACTOR_VERSION
    routed_via_orchestrator = False

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        return extract_project_semantics(segments)


class LlmGroundedExtractor:
    """The grounded LLM extractor, in direct-provider or orchestrator-routed mode.

    Both modes run the identical grounded extraction core
    (:func:`extract_project_semantics_llm`, which enforces segment citations);
    they differ only in which OpenAI-compatible endpoint the request is routed
    to. When ``routed_via_orchestrator`` is set the request targets the
    contextual-orchestrator gateway resolved into the context; otherwise it hits
    the tenant's provider directly.
    """

    name = LLM_EXTRACTOR_NAME
    version = LLM_EXTRACTOR_VERSION

    def __init__(self, *, routed_via_orchestrator: bool = False) -> None:
        self.routed_via_orchestrator = routed_via_orchestrator

    def _resolve_base_url(self, context: KgExtractorContext) -> str | None:
        if self.routed_via_orchestrator:
            if not context.orchestrator_base_url:
                raise ExtractorUnavailableError(
                    "contextual-orchestrator endpoint is not configured"
                )
            return context.orchestrator_base_url
        return context.base_url

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        if not context.has_llm_credentials:
            raise ExtractorUnavailableError("LLM provider credentials are not resolved")
        base_url = self._resolve_base_url(context)
        return await extract_project_semantics_llm(
            segments,
            api_key=context.api_key,
            base_url=base_url,
            model=context.model,
        )


class KgExtractorRegistry:
    """Selector-keyed registry with a guaranteed reference-only fallback.

    The registry is the pluggable seam: a plugin or a new extractor registers a
    :class:`KgExtractor` under a selector key and becomes selectable via
    ``PROJECT_GRAPH_EXTRACTOR`` without touching the ingest pipeline. Chain
    resolution always appends the deterministic reference extractor as the
    terminal fallback; it is never the default judgment source.
    """

    def __init__(self) -> None:
        self._by_selector: dict[str, KgExtractor] = {}

    def register(self, selector: str, extractor: KgExtractor) -> None:
        self._by_selector[selector] = extractor

    def get(self, selector: str) -> KgExtractor | None:
        return self._by_selector.get(selector)

    def selectors(self) -> tuple[str, ...]:
        return tuple(self._by_selector)

    @property
    def fallback(self) -> KgExtractor:
        # The keyword extractor is the structural fallback; a registry without
        # it is a programming error and surfaces loudly as a KeyError.
        return self._by_selector[SELECTOR_KEYWORD]

    def resolve_chain(self, selector: str) -> list[KgExtractor]:
        fallback = self.fallback
        primary = self._by_selector.get(selector, fallback)
        if primary is fallback:
            return [fallback]
        return [primary, fallback]


def build_default_registry() -> KgExtractorRegistry:
    """Registry pre-populated with the three built-in extractors."""
    registry = KgExtractorRegistry()
    registry.register(SELECTOR_KEYWORD, DeterministicKeywordExtractor())
    registry.register(SELECTOR_LLM, LlmGroundedExtractor(routed_via_orchestrator=False))
    registry.register(
        SELECTOR_ORCHESTRATOR, LlmGroundedExtractor(routed_via_orchestrator=True)
    )
    return registry


# Process-wide default registry. Tests and plugins may build their own.
default_registry = build_default_registry()


def resolve_extractor_chain(
    selector: str,
    *,
    registry: KgExtractorRegistry | None = None,
) -> list[KgExtractor]:
    """Ordered extractor chain for ``selector`` (deterministic fallback last)."""
    return (registry or default_registry).resolve_chain(selector)


async def run_extraction(
    segments: Iterable[ProjectSourceSegment],
    *,
    selector: str,
    context: KgExtractorContext,
    registry: KgExtractorRegistry | None = None,
) -> ProjectSemanticExtractionResult:
    """Run the resolved extractor chain, returning the first successful result.

    Each extractor that raises :class:`ExtractorUnavailableError` (recoverable
    precondition) or any other exception (extraction failure) is skipped in
    favour of the next. Because the chain always ends at the pure deterministic
    keyword extractor, a result is effectively always produced; the trailing
    raise only guards a misconfigured registry with no fallback.
    """
    chain = resolve_extractor_chain(selector, registry=registry)
    segment_list = list(segments)
    last_error: Exception | None = None
    for extractor in chain:
        try:
            return await extractor.extract(segment_list, context=context)
        except ExtractorUnavailableError as exc:
            logger.debug(
                "Extractor %s unavailable; trying next in chain: %s",
                extractor.name,
                exc,
            )
            last_error = exc
            continue
        except Exception:  # noqa: BLE001 - degrade to the next extractor
            logger.warning(
                "Extractor %s failed; falling back to the next extractor",
                extractor.name,
                exc_info=True,
            )
            continue
    if last_error is not None:
        raise last_error
    raise ExtractorUnavailableError("no extractor produced a project graph result")
