"""Regression contract for the retained UUID v4 built-in tool."""

from __future__ import annotations

import uuid

import pytest

from api.tools import registry


@pytest.mark.asyncio
async def test_uuid_v4_generator_remains_available_after_mutation_freeze() -> None:
    """Keep the safe built-in utility while disabling only dynamic mutations."""
    tool = registry.get("uuid_v4_generator")

    assert tool is not None
    assert tool.parameters == {}
    result = await registry.invoke_tool("uuid_v4_generator", {})
    generated_uuid = uuid.UUID(result["uuid"])
    assert generated_uuid.version == 4
