"""Structural regression for Search API exception-redaction wiring."""

from pathlib import Path


def test_search_api_uses_canonical_redacted_traceback_boundary() -> None:
    source_path = Path(__file__).parents[1] / "api" / "search.py"
    source = source_path.read_text(encoding="utf-8")

    assert "from core.safe_logging import redacted_exception_info" in source
    assert 'logger.error("Search failed", exc_info=redacted_exception_info(e))' in source
    assert 'raise HTTPException(status_code=500, detail="Search failed") from None' in source
    assert 'logger.error("Grounded answer failed", exc_info=redacted_exception_info(e))' in source
    assert 'raise HTTPException(status_code=500, detail="Answer failed") from None' in source
    assert 'logger.error("Search failed", exc_info=True)' not in source
    assert 'logger.error("Grounded answer failed", exc_info=True)' not in source
