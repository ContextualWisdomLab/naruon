import pytest

from services.contact_information_extractor import extract_contact_information
from services.text_structure_statistics import measure_text_structure


def test_contact_information_preserves_first_occurrence_and_deduplicates() -> None:
    result = extract_contact_information(
        "Primary: Ada.Example@example.com, backup ada.example@EXAMPLE.com, "
        "mobile +82 10-1234-5678, desk (415) 555-0123."
    )

    assert result.email_addresses == ("Ada.Example@example.com",)
    assert result.phone_numbers == ("+82 10-1234-5678", "(415) 555-0123")


def test_contact_information_supports_unicode_email_without_normalizing_output() -> None:
    result = extract_contact_information("문의: 사용자@예시.한국")

    assert result.email_addresses == ("사용자@예시.한국",)
    assert result.phone_numbers == ()


def test_contact_information_rejects_incidental_long_numbers() -> None:
    result = extract_contact_information(
        "invoice 2026090512345678 and account 12345678901234567890"
    )

    assert result.phone_numbers == ()


def test_contact_information_rejects_oversized_input() -> None:
    with pytest.raises(ValueError, match="must not exceed 100000 characters"):
        extract_contact_information("x" * 100_001)


def test_text_structure_statistics_are_descriptive_not_readability_scores() -> None:
    result = measure_text_structure("One short sentence. Two words!")

    assert result.character_count == 30
    assert result.non_whitespace_character_count == 26
    assert result.whitespace_token_count == 5
    assert result.sentence_boundary_count == 2
    assert result.segmentation_contract == "whitespace-and-terminal-punctuation-v1"
    assert not hasattr(result, "readability_score")


def test_text_structure_statistics_keep_cjk_contract_explicit() -> None:
    result = measure_text_structure("첫 문장입니다. 次の文です。")

    assert result.whitespace_token_count == 3
    assert result.sentence_boundary_count == 2


def test_text_structure_statistics_handle_empty_input() -> None:
    result = measure_text_structure("")

    assert result.character_count == 0
    assert result.non_whitespace_character_count == 0
    assert result.whitespace_token_count == 0
    assert result.sentence_boundary_count == 0


def test_text_structure_statistics_reject_oversized_input() -> None:
    with pytest.raises(ValueError, match="must not exceed 100000 characters"):
        measure_text_structure("x" * 100_001)
