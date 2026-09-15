import pytest

from api.tools import email_phone_masker_handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_text", "expected_text"),
    [
        (
            "국내 연락처는 010 1234 5678입니다.",
            "국내 연락처는 [PHONE]입니다.",
        ),
        (
            "해외 표기는 +82 10 1234 5678입니다.",
            "해외 표기는 [PHONE]입니다.",
        ),
        (
            "기존 표기는 010-1234-5678입니다.",
            "기존 표기는 [PHONE]입니다.",
        ),
        (
            "북미 연락처는 +1 (415) 555-2671입니다.",
            "북미 연락처는 [PHONE]입니다.",
        ),
    ],
)
async def test_email_phone_masker_masks_common_korean_phone_formats(
    source_text: str,
    expected_text: str,
) -> None:
    """Mask common domestic and +82 Korean phone representations."""
    result = await email_phone_masker_handler({"text": source_text})

    assert result["masked_text"] == expected_text


@pytest.mark.asyncio
async def test_email_phone_masker_rejects_malformed_email_domain() -> None:
    """Do not consume malformed addresses while masking valid neighbors."""
    result = await email_phone_masker_handler(
        {"text": "Keep a@b..com visible; mask support@example.com."}
    )

    assert result["masked_text"] == "Keep a@b..com visible; mask [EMAIL]."
