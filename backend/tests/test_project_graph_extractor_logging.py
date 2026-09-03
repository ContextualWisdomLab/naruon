"""Regression tests for truthful project-graph extractor failure logging."""

import logging

import pytest

from services.project_graph.extractor_registry import (
    DeterministicKeywordExtractor,
    KgExtractorContext,
    KgExtractorRegistry,
    run_extraction,
)


class _FailingLlmExtractor:
    name = "failing-llm"
    version = "test"
    requires_llm_capability = True

    async def extract(self, segments, *, context):
        raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_terminal_llm_failure_does_not_claim_a_fallback(caplog) -> None:
    """A one-member LLM chain must not log that it fell back before re-raising."""

    registry = KgExtractorRegistry()
    registry.register("keyword", DeterministicKeywordExtractor())
    registry.register("failing-llm", _FailingLlmExtractor())

    with caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError, match="provider down"):
            await run_extraction(
                [],
                selector="failing-llm",
                context=KgExtractorContext(),
                registry=registry,
            )

    assert "Extractor failing-llm failed" in caplog.text
    assert "falling back" not in caplog.text.lower()
