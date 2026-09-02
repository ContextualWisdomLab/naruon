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
* :func:`resolve_extractor_chain` / :func:`run_extraction`, which resolve an
  extractor chain per selector.

**Fallback is opt-in per extractor kind, not universal.** An extractor that
sets ``requires_llm_capability = True`` (both :data:`SELECTOR_LLM` and
:data:`SELECTOR_ORCHESTRATOR` today) resolves to a chain containing *only
itself* — if it is unavailable or fails, :func:`run_extraction` propagates
that error rather than silently substituting the deterministic keyword
extractor's output. This is deliberate product policy, not an oversight: a
keyword-derived semantic result must never masquerade as successful LLM
work (naruon#1525, exact-head review 2026-09-02). Only :data:`SELECTOR_KEYWORD`
resolves to the deterministic extractor — that remains an intentional,
always-available, non-LLM product mode, not a hidden fallback for a failed
or misconfigured request. An *unrecognized* selector value (a
``PROJECT_GRAPH_EXTRACTOR`` typo, for instance) is exactly such a
misconfiguration and is treated the same way: :meth:`KgExtractorRegistry.
resolve_chain` raises :class:`ExtractorUnavailableError` rather than
silently substituting keyword extraction, so a typo cannot persist
keyword-derived graphs under a caller's belief that LLM extraction ran.

**Neither LLM-backed selector is operational right now**, for related but
distinct reasons:

* :data:`SELECTOR_LLM` (direct-provider mode) is **disabled by policy**.
  Naruon holds no production LLM provider/model authority outside a released
  contextual-orchestrator consumer contract (see ADR-0005 Revision 8); every
  call unconditionally raises :class:`ExtractorUnavailableError`, regardless
  of any credentials or model configured in :class:`KgExtractorContext`.
* :data:`SELECTOR_ORCHESTRATOR` is **not yet operational**, pending
  contextual-orchestrator's first release. Configuring
  ``context.orchestrator_base_url`` alone is not sufficient: as of this
  module's last revision, ``ContextualWisdomLab/contextual-orchestrator`` has
  published no release, so no caller can also resolve a legitimate
  ``context.orchestrator_model``, and every orchestrator-routed request fails
  closed as a result (see :func:`LlmGroundedExtractor.extract` and ADR-0005
  Revisions 7–8). Configuring the endpoint now is still useful groundwork —
  it is the transport half of a two-part precondition — but it does not by
  itself enable extraction.

Routing LLM extraction through **contextual-orchestrator** is modelled as a
transport concern only: the orchestrator is an OpenAI-compatible gateway, so
the ``orchestrator`` selector reuses the same grounded LLM extractor but
points its SSRF-allowlisted client at the orchestrator base URL resolved by
the caller (:class:`KgExtractorContext`). This module does **not** choose a
provider, model, or virtual pool id on the caller's behalf — that authority
belongs to whatever populates ``context.orchestrator_model`` (a contextual-
orchestrator consumer contract's resolved value, once one exists); nothing
populates it today. If the endpoint is unset, the resolved model is blank,
or the provider credentials are missing, the extractor raises
:class:`ExtractorUnavailableError`, and :func:`run_extraction` propagates it
rather than substituting a different algorithm's output — the caller
(``email_import_service.py::_persist_project_graph_projection``) already
treats project-graph population as best-effort at a higher layer, so this
does not fail the email import itself, only its graph projection.
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

    Raised for a precondition the extractor cannot satisfy — missing LLM
    credentials, an unconfigured orchestrator endpoint, a policy-disabled
    mode — and also, from :meth:`KgExtractorRegistry.resolve_chain` itself,
    for an unrecognized ``PROJECT_GRAPH_EXTRACTOR`` selector (a
    misconfiguration, not an implicit request for keyword mode). What
    :func:`run_extraction` does with an instance of this raised by an
    extractor's ``extract`` depends on the resolved chain: for
    :data:`SELECTOR_KEYWORD`, the chain has no other member, so this (or any
    exception) simply propagates; for a plugin extractor whose
    ``requires_llm_capability`` is ``False``, the runner advances to the
    deterministic fallback instead. Neither :data:`SELECTOR_LLM` nor
    :data:`SELECTOR_ORCHESTRATOR` falls back — both set
    ``requires_llm_capability = True`` specifically so this error (or any
    other) propagates rather than being silently absorbed. A plugin that
    omits ``requires_llm_capability`` entirely does not get a default
    either way: :meth:`KgExtractorRegistry.resolve_chain` reads the
    attribute directly and raises :class:`AttributeError`, not this
    exception, so a non-conforming extractor fails loudly rather than
    silently inheriting the fallback-permitting behavior.
    """


@dataclass(frozen=True, slots=True)
class KgExtractorContext:
    """Per-run resources an extractor may consume.

    Deliberately small and provider-agnostic so extractors stay decoupled from
    import-service internals (no ambient session/settings authority).
    ``api_key`` is the shared credential presented to whichever endpoint is
    targeted; ``orchestrator_base_url`` is the OpenAI-compatible contextual-
    orchestrator gateway an orchestrator-routed extractor targets, and
    ``orchestrator_model`` is a contextual-orchestrator consumer contract's
    resolved model/pool value for that request — nothing populates it today
    because no such contract has been released yet (ADR-0005 Revision 8), so
    orchestrator-routed extraction correctly stays unavailable until both a
    release exists and a caller resolves this field from it.

    There is deliberately no direct-provider ``base_url``/``model`` field:
    :data:`SELECTOR_LLM` (direct-provider mode) is policy-disabled (ADR-0005
    Revision 8) and never reads either, so carrying them here would be dead
    configuration that could be mistaken for a live capability.
    """

    api_key: str | None = None
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

    ``requires_llm_capability`` is part of this contract, not an optional
    extra an implementer might not discover: :meth:`KgExtractorRegistry.
    resolve_chain` reads it to decide whether an unavailable or failed
    request may resolve to a different algorithm's output. Set it ``True``
    for any extractor whose failure must be reported truthfully rather than
    silently substituted (every LLM-backed extractor); set it ``False`` for
    an extractor that is fine being a fallback candidate (the deterministic
    keyword extractor, or a future non-LLM plugin that accepts the same
    role). Declaring it explicitly, on every implementation, is the point —
    there is deliberately no attribute default on the Protocol itself.
    """

    name: str
    version: str
    requires_llm_capability: bool

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
    """The deterministic keyword baseline — always available, never an LLM proxy.

    Pure and dependency-free: it needs no credentials and always produces a
    result. It is the terminal element of any chain that permits a fallback
    (see :attr:`requires_llm_capability`) and the sole element of a chain
    explicitly requesting :data:`SELECTOR_KEYWORD` — an intentional,
    always-on, non-LLM product mode in its own right, not merely a rescue
    path for a failed LLM request.
    """

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
        return extract_project_semantics(segments)


class LlmGroundedExtractor:
    """The grounded LLM extractor, in direct-provider or orchestrator-routed mode.

    Both modes would run the identical grounded extraction core
    (:func:`extract_project_semantics_llm`, which enforces segment citations)
    over whichever OpenAI-compatible endpoint the request is routed to — but
    as of ADR-0005 Revision 8, direct-provider mode (``routed_via_orchestrator
    = False``) is policy-disabled outright: Naruon holds no production LLM
    provider/model authority outside a released contextual-orchestrator
    consumer contract, so :meth:`extract` raises unconditionally for it,
    before looking at any other context field. Orchestrator mode targets the
    contextual-orchestrator gateway resolved into the context and forwards
    ``context.orchestrator_model`` verbatim — this class has no model
    selection authority of its own even there; nothing populates that field
    until contextual-orchestrator ships a release.

    ``requires_llm_capability = True`` on every instance of this class tells
    :meth:`KgExtractorRegistry.resolve_chain` not to append the deterministic
    keyword extractor behind it: an unavailable or failed LLM-backed request
    must propagate, never silently resolve to a different algorithm's output.
    """

    name = LLM_EXTRACTOR_NAME
    version = LLM_EXTRACTOR_VERSION
    requires_llm_capability = True

    def __init__(self, *, routed_via_orchestrator: bool = False) -> None:
        self.routed_via_orchestrator = routed_via_orchestrator

    def _resolve_base_url(self, context: KgExtractorContext) -> str | None:
        # Only ever reached in orchestrator mode: extract() raises before
        # calling this in direct-provider mode.
        if not context.orchestrator_base_url:
            raise ExtractorUnavailableError(
                "contextual-orchestrator endpoint is not configured"
            )
        return context.orchestrator_base_url

    async def extract(
        self,
        segments: list[ProjectSourceSegment],
        *,
        context: KgExtractorContext,
    ) -> ProjectSemanticExtractionResult:
        if not self.routed_via_orchestrator:
            # Unconditional: no credential, model, or endpoint in `context`
            # can make direct-provider mode available. This is a policy
            # disable, not a missing-configuration gate -- see ADR-0005
            # Revision 8 (naruon#1525, exact-head review 2026-09-02).
            raise ExtractorUnavailableError(
                "direct-provider LLM extraction is disabled: all LLM-backed "
                "KG extraction must route through contextual-orchestrator's "
                "released consumer contract (none exists yet), and Naruon "
                "holds no production LLM provider/model authority outside "
                "that boundary (see ADR-0005 Revision 8)"
            )
        if not context.api_key:
            raise ExtractorUnavailableError("LLM provider credentials are not resolved")
        base_url = self._resolve_base_url(context)
        model = context.orchestrator_model
        if not model or not model.strip():
            # An unset, blank, or whitespace-only model must fail closed
            # rather than be sent as an invalid model id, only discovered
            # after a network round-trip. This is presently *always* the
            # outcome -- contextual-orchestrator has no released consumer
            # contract yet (0 GitHub Releases as of ADR-0005 Revision 7), so
            # no caller populates context.orchestrator_model, and this
            # extractor has no authority to invent a value for it.
            raise ExtractorUnavailableError(
                "contextual-orchestrator has published no consumer "
                "release yet, so no orchestrator_model is available to "
                "route this request (see ADR-0005 Revision 7)"
            )
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
    resolution appends the deterministic keyword extractor as a terminal
    fallback *unless* the resolved extractor sets
    ``requires_llm_capability = True`` (see :class:`LlmGroundedExtractor`),
    in which case the chain contains only that extractor and an unavailable
    or failed request propagates instead of silently degrading. An
    unrecognized selector is treated as a misconfiguration, not an implicit
    request for ``keyword`` mode: only an explicit :data:`SELECTOR_KEYWORD`
    resolves to the deterministic extractor. A registered extractor that
    omits ``requires_llm_capability`` (despite the :class:`KgExtractor`
    Protocol declaring it with no default) is *not* treated as
    ``False`` -- resolution raises :class:`AttributeError` instead, so a
    non-conforming plugin fails loudly rather than silently keeping the
    fallback its author may not have intended.
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
        fallback = self.fallback  # KeyError if the registry itself has no keyword extractor
        if selector not in self._by_selector:
            # A typo or otherwise-unrecognized PROJECT_GRAPH_EXTRACTOR value
            # is a misconfiguration, not an implicit request for keyword
            # mode: silently substituting keyword extraction here would let
            # a typo persist keyword-derived graphs indefinitely under the
            # caller's belief that the requested capability ran (Devin
            # Review, naruon#1525, exact-head bb889797 follow-up).
            raise ExtractorUnavailableError(
                f"unrecognized PROJECT_GRAPH_EXTRACTOR selector: {selector!r}"
            )
        primary = self._by_selector[selector]
        if primary is fallback:
            return [fallback]
        # Direct attribute access, not getattr(..., False): the Protocol
        # declares requires_llm_capability with no default specifically so
        # a non-conforming extractor (a dynamically loaded plugin that
        # forgot to declare it, most plausibly) fails loudly with
        # AttributeError at resolution time instead of silently inheriting
        # the unsafe "keeps the keyword fallback" default (Devin Review,
        # naruon#1525, exact-head 5857c7f follow-up: a getattr default here
        # made the "no default" contract purely aspirational).
        if primary.requires_llm_capability:
            return [primary]
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
    """Ordered extractor chain for ``selector``.

    Raises :class:`ExtractorUnavailableError` for an unrecognized selector.
    Otherwise the deterministic keyword extractor is the last (or only)
    element, unless the resolved extractor sets ``requires_llm_capability
    = True``, in which case it is the only element.
    """
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
    favour of the next member of the chain, if one exists. Whether one exists
    depends on the resolved extractor: :meth:`KgExtractorRegistry.
    resolve_chain` appends the deterministic keyword extractor only behind an
    extractor that does *not* set ``requires_llm_capability = True``. For
    :data:`SELECTOR_LLM` and :data:`SELECTOR_ORCHESTRATOR` the chain has no
    other member, so the loop below ends immediately and the trailing
    ``raise`` propagates the real failure -- not a "no extractor available"
    placeholder -- because both branches below now always record it as
    ``last_error``, whichever kind of exception it was.
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
        except Exception as exc:  # noqa: BLE001 - degrade to the next extractor
            logger.warning(
                "Extractor %s failed; falling back to the next extractor",
                extractor.name,
                exc_info=True,
            )
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise ExtractorUnavailableError("no extractor produced a project graph result")
