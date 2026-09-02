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
  ordered fallback chain whose **terminal element is always the deterministic
  keyword extractor** — encoding "rule-based extraction is fallback/reference
  only" structurally rather than in an ad-hoc branch.

**The** ``orchestrator`` **selector is not operational yet.** Configuring
``context.orchestrator_base_url`` alone is not sufficient to route a request
through it: as of this module's last revision,
``ContextualWisdomLab/contextual-orchestrator`` has published no release, so
no caller can also resolve a legitimate ``context.orchestrator_model``, and
every orchestrator-routed request fails closed to the deterministic keyword
extractor as a result (see :func:`LlmGroundedExtractor.extract` and ADR-0005
Revision 7). Configuring the endpoint now is still useful groundwork — it is
the transport half of a two-part precondition — but it does not by itself
enable extraction.

Routing LLM extraction through **contextual-orchestrator** is modelled as a
transport concern only: the orchestrator is an OpenAI-compatible gateway, so
the ``orchestrator`` selector reuses the same grounded LLM extractor but
points its SSRF-allowlisted client at the orchestrator base URL resolved by
the caller (:class:`KgExtractorContext`). This module does **not** choose a
provider, model, or virtual pool id on the caller's behalf in either mode —
that authority belongs to whatever populates ``context.model`` (a direct
provider config, read only by :data:`SELECTOR_LLM`) or ``context.
orchestrator_model`` (a contextual-orchestrator consumer contract's
resolved value, read only by :data:`SELECTOR_ORCHESTRATOR` — the two fields
are kept separate precisely so a direct-provider setting can never leak into
an orchestrator-routed request as a substitute model id). If the endpoint is
unset, the resolved model is blank, or the provider credentials are
missing, the extractor raises :class:`ExtractorUnavailableError` and the
runner fails
closed to the deterministic reference extractor — the projection is
best-effort and never lost.
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

    ``model`` and ``orchestrator_model`` are deliberately separate fields, not
    one field reused across modes: ``model`` is the caller's direct-provider
    setting (e.g. the tenant's configured OpenAI model) and must never reach
    the orchestrator gateway, which resolves its own model/pool id from a
    contextual-orchestrator consumer contract instead. ``orchestrator_model``
    is that contract-resolved value; today no caller populates it, because
    contextual-orchestrator has published no release for Naruon to consume
    (see ADR-0005 Revision 7), so orchestrator-routed extraction correctly
    stays unavailable until both a release exists and a caller resolves this
    field from it.
    """

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    orchestrator_base_url: str | None = None
    orchestrator_model: str | None = None


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
    """The deterministic keyword baseline — the structural fallback extractor.

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
    the tenant's provider directly. This class has no provider/model/pool
    selection authority of its own in either mode — direct-provider mode
    forwards ``context.model`` (the caller's own configuration) verbatim,
    orchestrator mode forwards ``context.orchestrator_model`` (a contextual-
    orchestrator released consumer contract's resolved value, once one
    exists) verbatim, and the two fields are never substituted for each
    other.
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

    def _resolve_model(self, context: KgExtractorContext) -> str | None:
        # Neither mode picks a model on the caller's behalf, and the two modes
        # deliberately read different fields: context.model is the caller's
        # direct-provider setting and must never be forwarded to the
        # orchestrator gateway as a substitute model/pool id (that would be
        # the exact bypass ADR-0005 Revision 7 closes -- see
        # email_import_service.py, which sets context.model to
        # settings.OPENAI_MODEL unconditionally, regardless of selector).
        # context.orchestrator_model is the contextual-orchestrator
        # consumer-contract value instead; no caller populates it today
        # because no contract has been released, so this correctly resolves
        # to None and orchestrator-routed extraction fails closed.
        if self.routed_via_orchestrator:
            return context.orchestrator_model
        return context.model

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        if not context.api_key:
            raise ExtractorUnavailableError("LLM provider credentials are not resolved")
        base_url = self._resolve_base_url(context)
        model = self._resolve_model(context)
        if not model or not model.strip():
            # An unset, blank, or whitespace-only model must fail closed
            # rather than be sent as an invalid model id (only discovered
            # after a network round-trip) or silently substituted with a
            # hardcoded value -- but the two modes fail for genuinely
            # different reasons, so the message says which, truthfully
            # (Devin Review flagged the previous shared "credentials are not
            # resolved" message as misleading here: api_key can easily be
            # present while only the model is unresolved). For orchestrator
            # mode this is presently *always* the outcome -- contextual-
            # orchestrator has no released consumer contract yet (0 GitHub
            # Releases as of ADR-0005 Revision 7), so no caller populates
            # context.orchestrator_model, and this extractor has no
            # authority to invent a value for it.
            if self.routed_via_orchestrator:
                raise ExtractorUnavailableError(
                    "contextual-orchestrator has published no consumer "
                    "release yet, so no orchestrator_model is available to "
                    "route this request (see ADR-0005 Revision 7)"
                )
            raise ExtractorUnavailableError("LLM provider model is not configured")
        return await extract_project_semantics_llm(
            segments,
            api_key=context.api_key,
            base_url=base_url,
            model=model,
        )


class KgExtractorRegistry:
    """Selector-keyed registry of extractors with a guaranteed keyword fallback.

    The registry is the pluggable seam: a plugin or a new extractor registers a
    :class:`KgExtractor` under a selector key and becomes selectable via
    ``PROJECT_GRAPH_EXTRACTOR`` without touching the ingest pipeline. Chain
    resolution always appends the deterministic keyword extractor as the
    terminal fallback.
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
