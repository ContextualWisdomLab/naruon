"""Naming and compatibility contract for prompt response identifiers."""

from __future__ import annotations

import datetime

from api.prompts import PromptResponse


def test_prompt_response_uses_semantic_internal_identifier_and_legacy_wire_alias() -> None:
    """Keep the owned identifier specific while preserving the established ``id`` wire key."""
    assert "prompt_record_id" in PromptResponse.model_fields
    assert "id" not in PromptResponse.model_fields

    now = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
    prompt_response = PromptResponse(
        id=17,
        prompt_uid="prompt-example",
        title="Example",
        is_shared=False,
        created_by="user-example",
        created_at=now,
        updated_at=now,
    )

    assert prompt_response.prompt_record_id == 17
    serialized_response = prompt_response.model_dump(by_alias=True)
    assert serialized_response["id"] == 17
    assert "prompt_record_id" not in serialized_response
