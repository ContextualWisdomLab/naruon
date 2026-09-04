"""Regression contract for bounded Korean and North American phone masking."""

import pytest
from fastapi.testclient import TestClient

from api.tools import email_phone_masker_handler
from main import app
from tests.test_tools_api import _signed_session_token


_SUPPORTED_PHONE_CASES = (
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
        "북미 연락처는 +1 (123) 456-7890입니다.",
        "북미 연락처는 [PHONE]입니다.",
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("source_text", "expected_text"), _SUPPORTED_PHONE_CASES)
async def test_email_phone_masker_masks_supported_phone_formats(
    source_text: str,
    expected_text: str,
) -> None:
    """Mask selected Korean and North American phone representations."""
    result = await email_phone_masker_handler({"text": source_text})

    assert result["masked_text"] == expected_text


@pytest.mark.parametrize(("source_text", "expected_text"), _SUPPORTED_PHONE_CASES)
def test_execute_email_phone_masker_masks_supported_phone_formats(
    source_text: str,
    expected_text: str,
) -> None:
    """Preserve the same masking contract through authenticated tool execution."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/email_phone_masker/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": source_text}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result"]["masked_text"] == expected_text
