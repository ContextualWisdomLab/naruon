import pytest

from api.tools import registry, text_analyzer_handler


@pytest.mark.asyncio
async def test_text_analyzer_exposes_descriptive_measurement_contract() -> None:
    result = await text_analyzer_handler(
        {"text": "A\u00a0B 3.14... https://example.com/a."}
    )

    assert result["character_count"] == 34
    assert result["non_whitespace_character_count"] == 31
    assert result["whitespace_token_count"] == 4
    assert result["terminal_punctuation_run_count"] == 4
    assert result["segmentation_contract"] == (
        "whitespace-and-terminal-punctuation-runs-v2"
    )
    assert result["legacy_aliases"] == {
        "char_count": "character_count",
        "char_count_no_spaces": "non_whitespace_character_count",
        "word_count": "whitespace_token_count",
    }
    assert result["char_count"] == result["character_count"]
    assert result["char_count_no_spaces"] == result["non_whitespace_character_count"]
    assert result["word_count"] == result["whitespace_token_count"]


def test_text_analyzer_catalog_discloses_legacy_alias_semantics() -> None:
    tool = registry.get("text_analyzer")

    assert tool is not None
    assert "공백 구분 토큰 수" in tool.description
    assert "호환 별칭" in tool.description
    assert "단어·문장 수를 뜻하지 않습니다" in tool.description
