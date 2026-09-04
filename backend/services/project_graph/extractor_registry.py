"""Named, versioned extractor seam for the Naruon project knowledge graph.

Naruon owns project-graph semantics and selector policy. It does not own LLM
provider credentials, provider/model/pool selection, or a raw OpenAI-compatible
transport to contextual-orchestrator. LLM-backed selectors therefore remain
fail-closed until contextual-orchestrator publishes an immutable consumer
release whose API/client/schema can be consumed at this boundary.

The deterministic keyword extractor remains an explicit non-LLM product mode.
It is never used as a silent substitute for an LLM-backed request.
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
from .llm_extractor import LLM_EXTRACTOR_NAME, LLM_EXTRACTOR_VERSION
from .models import ProjectSemanticExtractionResult, ProjectSourceSegment

logger = logging.getLogger(__name__)

SELECTOR_KEYWORD = "keyword"
SELECTOR_LLM = "llm"
SELECTOR_ORCHESTRATOR = "orchestrator"


class ExtractorUnavailableError(RuntimeError):
    """The selected extractor cannot truthfully execute in this context."""


@dataclass(frozen=True)
class KgExtractorContext:
    """Authority-free per-run extractor context.

    No provider credential, raw contextual-orchestrator URL, provider/model id,
    group, pool, or compatibility diagnostic belongs here. A future LLM-backed
    implementation must consume an immutable contextual-orchestrator client/
    schema contract and add only contract-defined capability inputs at this
    boundary.
    """


@runtime_checkable
class KgExtractor(Protocol):
    """Stable named/versioned contract implemented by project-graph extractors."""

    name: str
    version: str
    requires_llm_capability: bool

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        raise NotImplementedError


class DeterministicKeywordExtractor:
    """Deterministic project-graph extraction selected explicitly as ``keyword``."""

    name = DETERMINISTIC_EXTRACTOR_NAME
    version = DETERMINISTIC_EXTRACTOR_VERSION
    routed_via_orchestrator = False
    requires_llm_capability = False

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        del context
        return extract_project_semantics(segments)


class LlmGroundedExtractor:
    """Fail-closed placeholder for LLM-backed project-graph capability.

    ``llm`` direct-provider mode is policy-disabled. ``orchestrator`` mode is
    also unavailable while contextual-orchestrator has no immutable consumer
    release. Importantly, this class does not call the local grounded LLM
    transport or read credentials, endpoint URLs, model ids, provider names,
    groups, or pool ids. A future implementation must replace this placeholder
    with the released contextual-orchestrator API/client/schema; local runtime
    configuration is not a substitute for that release.
    """

    name = LLM_EXTRACTOR_NAME
    version = LLM_EXTRACTOR_VERSION
    requires_llm_capability = True

    def __init__(self, *, routed_via_orchestrator: bool = False) -> None:
        self.routed_via_orchestrator = routed_via_orchestrator

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        del segments, context
        if not self.routed_via_orchestrator:
            raise ExtractorUnavailableError(
                "direct-provider LLM extraction is disabled: Naruon must use "
                "contextual-orchestrator's released consumer contract"
            )

        raise ExtractorUnavailableError(
            "contextual-orchestrator released consumer contract is unavailable; "
            "project-graph LLM extraction remains fail-closed"
        )


class KgExtractorRegistry:
    """Selector-keyed extractor registry with explicit fallback semantics."""

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
        return self._by_selector[SELECTOR_KEYWORD]

    def resolve_chain(self, selector: str) -> list[KgExtractor]:
        fallback = self.fallback
        if selector not in self._by_selector:
            raise ExtractorUnavailableError(
                f"unrecognized PROJECT_GRAPH_EXTRACTOR selector: {selector!r}"
            )
        primary = self._by_selector[selector]
        if primary is fallback:
            return [fallback]
        if primary.requires_llm_capability:
            return [primary]
        return [primary, fallback]


def build_default_registry() -> KgExtractorRegistry:
    """Build the registry containing Naruon's three stable selector identities."""
    registry = KgExtractorRegistry()
    registry.register(SELECTOR_KEYWORD, DeterministicKeywordExtractor())
    registry.register(SELECTOR_LLM, LlmGroundedExtractor(routed_via_orchestrator=False))
    registry.register(
        SELECTOR_ORCHESTRATOR, LlmGroundedExtractor(routed_via_orchestrator=True)
    )
    return registry


default_registry = build_default_registry()


def resolve_extractor_chain(
    selector: str,
    *,
    registry: KgExtractorRegistry | None = None,
) -> list[KgExtractor]:
    """Return the ordered extractor chain for a stable selector."""
    return (registry or default_registry).resolve_chain(selector)


async def run_extraction(
    segments: Iterable[ProjectSourceSegment],
    *,
    selector: str,
    context: KgExtractorContext,
    registry: KgExtractorRegistry | None = None,
) -> ProjectSemanticExtractionResult:
    """Run the chain and preserve the exact terminal failure when none succeeds."""
    chain = resolve_extractor_chain(selector, registry=registry)
    segment_list = list(segments)
    last_error: Exception | None = None
    for extractor in chain:
        try:
            return await extractor.extract(segment_list, context=context)
        except ExtractorUnavailableError as exc:
            logger.debug("Extractor %s unavailable: %s", extractor.name, exc)
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - chain policy owns fallback semantics
            logger.warning("Extractor %s failed", extractor.name, exc_info=True)
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ExtractorUnavailableError("no extractor produced a project graph result")
