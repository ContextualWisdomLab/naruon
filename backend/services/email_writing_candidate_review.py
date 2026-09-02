"""Parse and request strict contextual LLM email-writing candidates.

The candidate layer transports model judgments but never manufactures semantic
findings locally. Deterministic logic is limited to strict JSON/schema validation,
Unicode/resource safety, revision-bound selector bounds, overlap checks, authorized
evidence locators, canonical hashes, and orchestration-mode binding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)

from services.contextual_orchestrator_client import ChatMessage, OrchestrationMode
from services.email_writing_context_service import EmailWritingContextBundle
from services.email_writing_contracts import (
    DiagnosticPriority,
    EmailWritingDocumentGuidance,
    EmailWritingTextPositionSelector,
    MAX_DIAGNOSTICS,
    MAX_GUIDANCE_ITEMS,
    StrictEmailWritingJsonError,
    parse_strict_email_writing_json,
)
from services.email_writing_prompt import (
    EmailWritingCandidatePrompt,
    build_email_writing_candidate_prompt,
    candidate_evidence_ids,
)

CandidateCategory = Literal[
    "spelling",
    "grammar",
    "spacing",
    "punctuation",
    "clarity",
    "conciseness",
    "structure",
    "tone",
    "pragmatics",
    "technical_precision",
    "actionability",
]

_LANGUAGE_TAG_RE = re.compile(
    r"^(?=.{2,63}$)[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$"
)
_EVIDENCE_ID_RE = re.compile(r"^(?:draft|reply_objective|email:[1-9][0-9]*)$")
_BIDI_CONTROL_RANGES = (
    (0x202A, 0x202E),
    (0x2066, 0x2069),
)


class EmailWritingCandidateError(ValueError):
    """Stable payload-redacted candidate parsing or completion failure."""

    def __init__(self, code: str) -> None:
        """Create an error that exposes only one stable public code."""
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        """Return a representation that cannot contain authored or model text."""
        return f"EmailWritingCandidateError({self.code!r})"


class _CandidateModel(BaseModel):
    """Strict base model for untrusted candidate output."""

    model_config = ConfigDict(extra="forbid", strict=True)


def _contains_surrogate(value: str) -> bool:
    """Return whether one string contains a non-scalar Unicode surrogate."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _validate_inert_text(value: str, *, maximum: int, allow_empty: bool) -> str:
    """Validate bounded Unicode text without assigning semantic meaning."""
    if not allow_empty and not value:
        raise ValueError("candidate_text_empty")
    if len(value) > maximum:
        raise ValueError("candidate_text_limit")
    if _contains_surrogate(value):
        raise ValueError("candidate_text_unicode")
    return value


def _contains_unsafe_replacement_control(value: str) -> bool:
    """Detect transport controls that could obscure or mutate displayed text."""
    for character in value:
        codepoint = ord(character)
        if (codepoint < 32 and character not in {"\t", "\n", "\r"}) or codepoint == 127:
            return True
        if any(start <= codepoint <= end for start, end in _BIDI_CONTROL_RANGES):
            return True
    return False


class EmailWritingCandidateDiagnostic(_CandidateModel):
    """One model-proposed passage diagnostic before independent Judge admission."""

    selector: EmailWritingTextPositionSelector
    category_code: CandidateCategory
    priority: DiagnosticPriority
    title: StrictStr
    explanation: StrictStr
    suggested_replacement: StrictStr | None = None
    candidate_confidence: float = Field(
        strict=True,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
    )
    candidate_evidence_ids: list[StrictStr] = Field(
        min_length=1,
        max_length=MAX_GUIDANCE_ITEMS,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Require a short non-empty inert title."""
        return _validate_inert_text(value, maximum=512, allow_empty=False)

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, value: str) -> str:
        """Require a bounded non-empty evidence-grounded conclusion."""
        return _validate_inert_text(value, maximum=4_000, allow_empty=False)

    @field_validator("suggested_replacement")
    @classmethod
    def validate_replacement(cls, value: str | None) -> str | None:
        """Accept only bounded plain text without unsafe display controls."""
        if value is None:
            return None
        normalized = _validate_inert_text(value, maximum=20_000, allow_empty=True)
        if _contains_unsafe_replacement_control(normalized):
            raise ValueError("candidate_replacement_control")
        return normalized

    @field_validator("candidate_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        """Require unique bounded evidence locators from the published grammar."""
        if len(value) != len(set(value)):
            raise ValueError("candidate_evidence_duplicate")
        for evidence_id in value:
            if _EVIDENCE_ID_RE.fullmatch(evidence_id) is None:
                raise ValueError("candidate_evidence_invalid")
        return value


class EmailWritingCandidateOutput(_CandidateModel):
    """Exact model output accepted for independent Judge evaluation."""

    diagnostics: list[EmailWritingCandidateDiagnostic] = Field(
        max_length=MAX_DIAGNOSTICS
    )
    document_guidance: EmailWritingDocumentGuidance
    context_limitations: list[StrictStr] = Field(max_length=MAX_GUIDANCE_ITEMS)
    review_language: StrictStr
    abstained_claims: list[StrictStr] = Field(max_length=MAX_GUIDANCE_ITEMS)

    @field_validator("context_limitations", "abstained_claims")
    @classmethod
    def validate_notes(cls, value: list[str]) -> list[str]:
        """Bound non-empty context and abstention notes as inert text."""
        return [
            _validate_inert_text(item, maximum=4_000, allow_empty=False)
            for item in value
        ]

    @field_validator("review_language")
    @classmethod
    def validate_review_language(cls, value: str) -> str:
        """Require a bounded BCP-47-compatible language-tag subset."""
        _validate_inert_text(value, maximum=63, allow_empty=False)
        if _LANGUAGE_TAG_RE.fullmatch(value) is None:
            raise ValueError("candidate_language_invalid")
        return value


@dataclass(frozen=True, slots=True)
class ParsedEmailWritingCandidate:
    """Strict candidate output plus a canonical payload digest."""

    output: EmailWritingCandidateOutput
    payload_hash: str


@dataclass(frozen=True, slots=True)
class EmailWritingCandidateReviewResult:
    """Candidate result and privacy-preserving prompt/payload evidence."""

    output: EmailWritingCandidateOutput
    orchestration_mode: OrchestrationMode
    prompt_hash: str
    prompt_template_hash: str
    candidate_payload_hash: str


class EmailWritingCandidatePort(Protocol):
    """Minimal async contextual-orchestrator surface used by the reviewer."""

    async def complete_candidate(
        self,
        messages: Sequence[ChatMessage],
        *,
        mode: OrchestrationMode,
    ) -> Mapping[str, object]:
        """Return one strict candidate completion envelope."""


def _canonical_payload_hash(output: EmailWritingCandidateOutput) -> str:
    """Hash canonical validated output without retaining plaintext evidence."""
    canonical = json.dumps(
        output.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_candidate_selectors_and_evidence(
    output: EmailWritingCandidateOutput,
    bundle: EmailWritingContextBundle,
) -> None:
    """Validate exact draft bounds, non-overlap, and authorized evidence locators."""
    allowed_evidence = frozenset(candidate_evidence_ids(bundle))
    ordered_ranges: list[tuple[int, int]] = []
    for diagnostic in output.diagnostics:
        start = diagnostic.selector.start
        end = diagnostic.selector.end
        if start == end:
            raise EmailWritingCandidateError("candidate_selector_empty")
        if end > len(bundle.current_draft):
            raise EmailWritingCandidateError("candidate_selector_out_of_range")
        if not set(diagnostic.candidate_evidence_ids).issubset(allowed_evidence):
            raise EmailWritingCandidateError("candidate_evidence_unknown")
        ordered_ranges.append((start, end))

    ordered_ranges.sort()
    previous_end = -1
    for start, end in ordered_ranges:
        if start < previous_end:
            raise EmailWritingCandidateError("candidate_selector_overlap")
        previous_end = end


def parse_email_writing_candidate_review(
    source: str | bytes,
    bundle: EmailWritingContextBundle,
) -> ParsedEmailWritingCandidate:
    """Parse exact strict JSON and bind candidate spans to one authorized draft."""
    try:
        output = parse_strict_email_writing_json(
            source,
            EmailWritingCandidateOutput,
        )
    except (StrictEmailWritingJsonError, ValidationError):
        raise EmailWritingCandidateError("candidate_payload_invalid") from None

    _validate_candidate_selectors_and_evidence(output, bundle)
    return ParsedEmailWritingCandidate(
        output=output,
        payload_hash=_canonical_payload_hash(output),
    )


def _extract_candidate_answer(
    response: object,
    expected_mode: OrchestrationMode,
) -> str:
    """Validate the Task 5 completion envelope without exposing its contents."""
    try:
        if not isinstance(response, Mapping):
            raise TypeError
        if set(response.keys()) != {"answer", "mode", "trace"}:
            raise ValueError
        answer = response["answer"]
        mode = response["mode"]
        trace = response["trace"]
        if not isinstance(answer, str):
            raise TypeError
        if mode != expected_mode:
            raise ValueError
        if not isinstance(trace, list):
            raise TypeError
    except (KeyError, TypeError, ValueError):
        raise EmailWritingCandidateError("candidate_completion_invalid") from None
    return answer


class EmailWritingCandidateReviewer:
    """Request and strictly validate one contextual candidate review."""

    def __init__(self, port: EmailWritingCandidatePort) -> None:
        """Create a reviewer over the bounded Task 5 orchestration port."""
        self._port = port

    async def review(
        self,
        bundle: EmailWritingContextBundle,
    ) -> EmailWritingCandidateReviewResult:
        """Run contextual candidate generation with mode-specific reasoning effort."""
        prompt: EmailWritingCandidatePrompt = build_email_writing_candidate_prompt(
            bundle
        )
        mode: OrchestrationMode = (
            "route" if bundle.review_mode == "incremental" else "conduct"
        )
        response = await self._port.complete_candidate(prompt.messages, mode=mode)
        answer = _extract_candidate_answer(response, mode)
        parsed = parse_email_writing_candidate_review(answer, bundle)
        return EmailWritingCandidateReviewResult(
            output=parsed.output,
            orchestration_mode=mode,
            prompt_hash=prompt.prompt_hash,
            prompt_template_hash=prompt.template_hash,
            candidate_payload_hash=parsed.payload_hash,
        )
