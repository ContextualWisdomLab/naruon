"""Strict transport contracts for Naruon's LLM-native email writing guidance.

This module deliberately performs only deterministic transport and integrity
validation. It never decides whether authored prose is correct, clear, polite,
technically sound, or otherwise semantically acceptable. Those judgments belong
to the model workflow and its independently calibrated Judge.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

MAX_DRAFT_CHARS = 200_000
MAX_REPLY_OBJECTIVE_CHARS = 4_000
MAX_DIAGNOSTICS = 64
MAX_GUIDANCE_ITEMS = 32
MAX_JSON_ARRAY_ITEMS = 1_000
MAX_JSON_DEPTH = 16
MAX_JSON_NODES = 20_000
MAX_JSON_BYTES = 1_000_000
MAX_SAFE_INTEGER = 2**53 - 1

_LANGUAGE_TAG_RE = re.compile(
    r"^(?=.{2,63}$)[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$"
)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

ReviewMode = Literal["incremental", "deep"]
ReviewStatus = Literal[
    "completed",
    "abstained",
    "unavailable",
    "stale",
    "rejected",
    "context_insufficient",
    "judge_disagreement",
]
DiagnosticPriority = Literal["advisory", "important", "critical"]
FeedbackAction = Literal[
    "applied",
    "ignored",
    "dismissed",
    "requested_explanation",
    "stale",
    "conflict",
]
OrchestrationMode = Literal["route", "conduct"]


class StrictEmailWritingJsonError(ValueError):
    """Raised when raw JSON violates the bounded deterministic parse contract."""

    def __init__(self, code: str) -> None:
        """Create a redacted parser error identified only by a stable code."""
        super().__init__(code)
        self.code = code


class _StrictTransportModel(BaseModel):
    """Base class that rejects coercion and unexpected transport fields."""

    model_config = ConfigDict(extra="forbid", strict=True)


def _contains_surrogate(value: str) -> bool:
    """Return whether a string contains a non-scalar Unicode surrogate."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _validate_text(value: str, *, maximum: int, allow_empty: bool = True) -> str:
    """Validate one bounded Unicode-scalar transport string."""
    if not allow_empty and not value:
        raise ValueError("text_empty")
    if len(value) > maximum:
        raise ValueError("text_limit")
    if _contains_surrogate(value):
        raise ValueError("invalid_unicode")
    return value


def _validate_identifier(value: str) -> str:
    """Validate one opaque non-secret identifier used in public evidence."""
    _validate_text(value, maximum=128, allow_empty=False)
    if _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError("identifier_invalid")
    return value


class EmailWritingDocumentRevision(_StrictTransportModel):
    """Strong SHA-256 document revision bound to one canonical Inkspan document."""

    algorithm: Literal["SHA-256"]
    digest_hex: StrictStr
    strong_entity_tag: StrictStr

    @field_validator("digest_hex")
    @classmethod
    def validate_digest_hex(cls, value: str) -> str:
        """Require a lowercase 32-byte SHA-256 digest encoded as hexadecimal."""
        if _DIGEST_RE.fullmatch(value) is None:
            raise ValueError("revision_digest_invalid")
        return value

    @model_validator(mode="after")
    def validate_entity_tag(self) -> "EmailWritingDocumentRevision":
        """Require the strong entity tag to encode exactly the declared digest."""
        expected = f'"sha256-{self.digest_hex}"'
        if self.strong_entity_tag != expected:
            raise ValueError("revision_entity_tag_invalid")
        return self


class EmailWritingTextPositionSelector(_StrictTransportModel):
    """W3C TextPositionSelector expressed in Unicode-code-point offsets."""

    type: Literal["TextPositionSelector"]
    start: StrictInt
    end: StrictInt

    @model_validator(mode="after")
    def validate_offsets(self) -> "EmailWritingTextPositionSelector":
        """Require ordered non-negative offsets safe to exchange with JavaScript."""
        if self.start < 0 or self.end < 0:
            raise ValueError("selector_negative")
        if self.start > self.end:
            raise ValueError("selector_order")
        if self.end > MAX_SAFE_INTEGER:
            raise ValueError("selector_limit")
        return self


class EmailWritingProvenance(_StrictTransportModel):
    """Redacted model-workflow provenance safe for browser transport."""

    workflow_id: StrictStr
    workflow_version: StrictStr
    judge_policy_version: StrictStr
    rubric_version: StrictStr
    model_profile_id: StrictStr
    orchestration_mode: OrchestrationMode
    prompt_hash: StrictStr

    @field_validator(
        "workflow_id",
        "workflow_version",
        "judge_policy_version",
        "rubric_version",
        "model_profile_id",
    )
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Require bounded opaque identifiers without model or provider payloads."""
        return _validate_identifier(value)

    @field_validator("prompt_hash")
    @classmethod
    def validate_prompt_hash(cls, value: str) -> str:
        """Require a content hash rather than the plaintext prompt."""
        if _HASH_RE.fullmatch(value) is None:
            raise ValueError("prompt_hash_invalid")
        return value


class EmailWritingReviewRequest(_StrictTransportModel):
    """Client review request bound to one exact draft revision and projection."""

    source_email_id: StrictInt
    document_revision: EmailWritingDocumentRevision
    projection_name: Literal["inkspan-prosemirror-text"]
    projection_version: Literal[1]
    draft_plain_text: StrictStr
    language_tag: StrictStr
    review_mode: ReviewMode
    changed_selector: EmailWritingTextPositionSelector | None = None
    reply_objective: StrictStr | None = None

    @field_validator("source_email_id")
    @classmethod
    def validate_source_email_id(cls, value: int) -> int:
        """Require a positive server-resolvable source email identifier."""
        if value <= 0:
            raise ValueError("source_email_id_invalid")
        return value

    @field_validator("draft_plain_text")
    @classmethod
    def validate_draft(cls, value: str) -> str:
        """Bound the draft without interpreting its language or meaning."""
        return _validate_text(value, maximum=MAX_DRAFT_CHARS)

    @field_validator("reply_objective")
    @classmethod
    def validate_objective(cls, value: str | None) -> str | None:
        """Bound optional untrusted author guidance without classifying it."""
        if value is None:
            return None
        return _validate_text(value, maximum=MAX_REPLY_OBJECTIVE_CHARS)

    @field_validator("language_tag")
    @classmethod
    def validate_language_tag(cls, value: str) -> str:
        """Validate a bounded BCP-47-compatible language-tag transport subset."""
        _validate_text(value, maximum=63, allow_empty=False)
        if _LANGUAGE_TAG_RE.fullmatch(value) is None:
            raise ValueError("language_tag_invalid")
        return value

    @model_validator(mode="after")
    def validate_review_mode(self) -> "EmailWritingReviewRequest":
        """Enforce incremental/deep selector rules and selector draft bounds."""
        if self.review_mode == "incremental":
            if self.changed_selector is None:
                raise ValueError("changed_selector_required")
        elif self.changed_selector is not None:
            raise ValueError("changed_selector_forbidden")
        if (
            self.changed_selector is not None
            and self.changed_selector.end > len(self.draft_plain_text)
        ):
            raise ValueError("changed_selector_out_of_range")
        return self


class EmailWritingDiagnostic(_StrictTransportModel):
    """One model/Judge-admitted passage diagnostic bound to the reviewed draft."""

    diagnostic_id: StrictStr
    document_revision: EmailWritingDocumentRevision
    projection_name: Literal["inkspan-prosemirror-text"]
    projection_version: Literal[1]
    selector: EmailWritingTextPositionSelector
    category_code: StrictStr
    priority: DiagnosticPriority
    title: StrictStr
    explanation: StrictStr
    suggested_replacement: StrictStr | None = None
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    provenance: EmailWritingProvenance

    @field_validator("diagnostic_id")
    @classmethod
    def validate_diagnostic_id(cls, value: str) -> str:
        """Validate the opaque diagnostic identifier."""
        return _validate_identifier(value)

    @field_validator("category_code")
    @classmethod
    def validate_category_code(cls, value: str) -> str:
        """Validate the category identifier without assigning semantic meaning."""
        if _CATEGORY_RE.fullmatch(value) is None:
            raise ValueError("category_code_invalid")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Bound the model-produced title as inert Unicode text."""
        return _validate_text(value, maximum=512, allow_empty=False)

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, value: str) -> str:
        """Bound the model-produced explanation as inert Unicode text."""
        return _validate_text(value, maximum=4_000, allow_empty=False)

    @field_validator("suggested_replacement")
    @classmethod
    def validate_replacement(cls, value: str | None) -> str | None:
        """Bound an optional plain-text replacement without interpreting it."""
        if value is None:
            return None
        return _validate_text(value, maximum=20_000)


class EmailWritingDocumentGuidance(_StrictTransportModel):
    """Non-mutating whole-document guidance returned alongside passage diagnostics."""

    purpose_summary: StrictStr
    reader_interpretation: StrictStr
    missing_requests: list[StrictStr] = Field(max_length=MAX_GUIDANCE_ITEMS)
    structure_suggestion: StrictStr

    @field_validator("purpose_summary", "reader_interpretation", "structure_suggestion")
    @classmethod
    def validate_guidance_text(cls, value: str) -> str:
        """Bound whole-document guidance as inert text."""
        return _validate_text(value, maximum=4_000)

    @field_validator("missing_requests")
    @classmethod
    def validate_missing_requests(cls, value: list[str]) -> list[str]:
        """Bound each non-mutating missing-request description."""
        return [
            _validate_text(item, maximum=1_024, allow_empty=False) for item in value
        ]


class EmailWritingReviewResponse(_StrictTransportModel):
    """Validated browser response containing only admitted guidance and redacted evidence."""

    review_session_id: StrictStr
    document_revision: EmailWritingDocumentRevision
    projection_name: Literal["inkspan-prosemirror-text"]
    projection_version: Literal[1]
    review_status: ReviewStatus
    diagnostics: list[EmailWritingDiagnostic] = Field(max_length=MAX_DIAGNOSTICS)
    document_guidance: EmailWritingDocumentGuidance
    context_limitations: list[StrictStr] = Field(max_length=MAX_GUIDANCE_ITEMS)
    abstained_claims: list[StrictStr] = Field(max_length=MAX_GUIDANCE_ITEMS)
    provenance: EmailWritingProvenance

    @field_validator("review_session_id")
    @classmethod
    def validate_review_session_id(cls, value: str) -> str:
        """Validate the opaque review session identifier."""
        return _validate_identifier(value)

    @field_validator("context_limitations", "abstained_claims")
    @classmethod
    def validate_evidence_notes(cls, value: list[str]) -> list[str]:
        """Bound context limitations and abstention notes as inert text."""
        return [
            _validate_text(item, maximum=4_000, allow_empty=False) for item in value
        ]

    @model_validator(mode="after")
    def validate_unique_diagnostics(self) -> "EmailWritingReviewResponse":
        """Reject duplicate diagnostic identities within one review response."""
        identifiers = [item.diagnostic_id for item in self.diagnostics]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("diagnostic_id_duplicate")
        return self


class EmailWritingFeedbackRequest(_StrictTransportModel):
    """Privacy-minimized author action reported for one reviewed diagnostic."""

    diagnostic_id: StrictStr
    document_revision: EmailWritingDocumentRevision
    feedback_action: FeedbackAction
    resulting_document_revision: EmailWritingDocumentRevision | None = None

    @field_validator("diagnostic_id")
    @classmethod
    def validate_diagnostic_id(cls, value: str) -> str:
        """Validate the diagnostic identifier without copying authored text."""
        return _validate_identifier(value)

    @model_validator(mode="after")
    def validate_resulting_revision(self) -> "EmailWritingFeedbackRequest":
        """Require a resulting revision only for an explicitly applied mutation."""
        if self.feedback_action == "applied":
            if self.resulting_document_revision is None:
                raise ValueError("resulting_revision_required")
        elif self.resulting_document_revision is not None:
            raise ValueError("resulting_revision_forbidden")
        return self


ModelT = TypeVar("ModelT", bound=BaseModel)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate member names."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictEmailWritingJsonError("duplicate_key")
        result[key] = value
    return result


def _reject_non_finite_constant(_: str) -> None:
    """Reject JSON extensions such as NaN and Infinity."""
    raise StrictEmailWritingJsonError("non_finite_number")


def _validate_json_shape(value: Any) -> None:
    """Enforce iterative nesting, collection-size, and total-node bounds."""
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise StrictEmailWritingJsonError("node_limit")
        if depth > MAX_JSON_DEPTH:
            raise StrictEmailWritingJsonError("nesting_limit")
        if isinstance(current, dict):
            if len(current) > MAX_JSON_ARRAY_ITEMS:
                raise StrictEmailWritingJsonError("object_limit")
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            if len(current) > MAX_JSON_ARRAY_ITEMS:
                raise StrictEmailWritingJsonError("array_limit")
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str) and _contains_surrogate(current):
            raise StrictEmailWritingJsonError("invalid_unicode")


def parse_strict_email_writing_json(
    source: str | bytes,
    model: type[ModelT],
) -> ModelT:
    """Parse bounded strict JSON and validate it against one exact Pydantic model.

    Duplicate keys, non-finite numeric extensions, excessive nesting, oversized
    collections, malformed UTF-8, trailing/invalid JSON, and oversized payloads
    fail before any model-level semantic workflow can consume the value.
    """
    if isinstance(source, bytes):
        if len(source) > MAX_JSON_BYTES:
            raise StrictEmailWritingJsonError("payload_limit")
        try:
            text = source.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise StrictEmailWritingJsonError("invalid_unicode") from error
    elif isinstance(source, str):
        try:
            encoded_size = len(source.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise StrictEmailWritingJsonError("invalid_unicode") from error
        if encoded_size > MAX_JSON_BYTES:
            raise StrictEmailWritingJsonError("payload_limit")
        text = source
    else:
        raise StrictEmailWritingJsonError("source_type")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except StrictEmailWritingJsonError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        raise StrictEmailWritingJsonError("invalid_json") from error

    _validate_json_shape(value)
    return model.model_validate(value)
