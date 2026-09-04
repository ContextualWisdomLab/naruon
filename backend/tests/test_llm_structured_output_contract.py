"""Provider-agnostic structured payload validation contracts.

These tests intentionally validate Naruon's payload models without asserting a
provider URL, model id, API key, OpenAI SDK transport, or contextual-orchestrator
wire shape. Runtime transport authority belongs to the released
contextual-orchestrator consumer contract rather than this repository.
"""

import pytest
from pydantic import BaseModel, ValidationError

from services.llm_service import ExtractionResult
from services.project_graph.llm_extractor import ExtractionPayload
from services.rag_service import GroundedAnswerPayload


@pytest.mark.parametrize(
    ("payload_model", "valid_payload"),
    [
        (ExtractionResult, {"summary": "s", "action_items": []}),
        (ExtractionPayload, {"objects": [], "relations": []}),
        (GroundedAnswerPayload, {"answer": "a", "cited_email_ids": []}),
    ],
)
def test_structured_payload_models_forbid_unknown_top_level_fields(
    payload_model: type[BaseModel],
    valid_payload: dict[str, object],
) -> None:
    """Reject fields outside the product-owned structured payload schema."""

    schema = payload_model.model_json_schema()

    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        payload_model.model_validate({**valid_payload, "unexpected_field": True})


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {
            "objects": [
                {
                    "object_type": "requirement",
                    "title": "t",
                    "summary": "s",
                    "source_segment_uids": ["segment-1"],
                    "confidence": 0.8,
                    "unexpected_field": True,
                }
            ],
            "relations": [],
        },
        {
            "objects": [],
            "relations": [
                {
                    "source_local_key": "a",
                    "target_local_key": "b",
                    "relation_type": "depends_on",
                    "confidence": 0.8,
                    "unexpected_field": True,
                }
            ],
        },
    ],
)
def test_project_graph_nested_payloads_forbid_unknown_fields(
    invalid_payload: dict[str, object],
) -> None:
    """Keep nested project-graph object and relation schemas fail closed."""

    with pytest.raises(ValidationError):
        ExtractionPayload.model_validate(invalid_payload)


def test_structured_payload_models_reject_scalar_coercion() -> None:
    """Keep machine-readable identifiers strict instead of coercing strings."""

    with pytest.raises(ValidationError):
        GroundedAnswerPayload.model_validate(
            {"answer": "grounded", "cited_email_ids": ["123"]}
        )

    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {"summary": "s", "action_items": [], "confidence": "90"}
        )
