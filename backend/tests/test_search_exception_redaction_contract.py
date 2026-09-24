"""Regression coverage for Search exception-redaction wiring."""

from pathlib import Path


SEARCH_API = Path(__file__).parents[1] / "api" / "search.py"


def test_search_api_uses_canonical_redacted_traceback_boundary() -> None:
    source = SEARCH_API.read_text(encoding="utf-8")

    assert "from core.safe_logging import redacted_exception_info" in source
    assert 'logger.error("Search failed", exc_info=redacted_exception_info(e))' in source
    assert 'raise HTTPException(status_code=500, detail="Search failed") from None' in source
    assert (
        'logger.error("Grounded answer failed", exc_info=redacted_exception_info(e))'
        in source
    )
    assert 'raise HTTPException(status_code=500, detail="Answer failed") from None' in source

    forbidden = (
        'logger.error("Search failed", exc_info=True)',
        'logger.error("Grounded answer failed", exc_info=True)',
        'raise HTTPException(status_code=500, detail="Search failed") from e',
        'raise HTTPException(status_code=500, detail="Answer failed") from e',
    )
    assert all(token not in source for token in forbidden)
