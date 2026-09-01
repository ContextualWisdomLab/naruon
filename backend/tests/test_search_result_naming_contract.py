"""Naming-contract regressions for Context Search result identities."""

from api.search import SearchResultItem


def test_search_result_uses_email_id_internally_with_legacy_wire_alias() -> None:
    """Keep the public ``id`` key while owning a semantic ``email_id`` field."""
    search_result = SearchResultItem(
        email_id=17,
        subject="Subject",
        sender="sender@example.com",
        date="2026-09-01T00:00:00Z",
        snippet="evidence",
        score=0.9,
    )

    assert "email_id" in SearchResultItem.model_fields
    assert "id" not in SearchResultItem.model_fields
    assert search_result.email_id == 17
    assert search_result.model_dump(by_alias=True)["id"] == 17


def test_search_result_accepts_existing_wire_id_during_deserialization() -> None:
    """Preserve compatibility for clients still sending or replaying the wire key."""
    search_result = SearchResultItem.model_validate(
        {
            "id": 23,
            "subject": None,
            "sender": "sender@example.com",
            "date": "2026-09-01T00:00:00Z",
            "snippet": "",
            "score": 0.5,
        }
    )

    assert search_result.email_id == 23
    assert search_result.model_dump(by_alias=True)["id"] == 23
