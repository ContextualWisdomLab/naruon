"""Regression contract for standards-compliant JSON formatting."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))

from api.tools import _render_json_value, json_formatter_handler
from main import app


def _base64url_encode(raw: bytes) -> str:
    """Encode JWT material using unpadded base64url."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token() -> str:
    """Build a short-lived signed member session for API boundary regressions."""
    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload_segment = _base64url_encode(
        json.dumps(
            {
                "ver": 1,
                "iss": "naruon-control-plane",
                "aud": "naruon-api",
                "sub": "json-contract-test",
                "role": "member",
                "org": "org-acme",
                "groups": ["group-1"],
                "workspace": "workspace-org-acme",
                "exp": int(time.time()) + 300,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        os.environ["AUTH_SESSION_HMAC_SECRET"].encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _execute_formatter(json_string: str) -> dict[str, object]:
    """Execute the formatter through the authenticated HTTP boundary."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/json_formatter/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"json_string": json_string}},
        )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_json_formatter_preserves_high_precision_decimal_value() -> None:
    """Formatting must not round a valid high-precision JSON decimal."""
    result = await json_formatter_handler(
        {"json_string": '{"value":1.0000000000000001}'}
    )

    parsed = json.loads(result["formatted_json"], parse_float=Decimal)
    assert parsed["value"] == Decimal("1.0000000000000001")


@pytest.mark.asyncio
async def test_json_formatter_preserves_large_finite_exponent() -> None:
    """A large finite JSON exponent must not be serialized as Infinity."""
    result = await json_formatter_handler({"json_string": '{"value":1e400}'})

    assert "Infinity" not in result["formatted_json"]
    parsed = json.loads(result["formatted_json"], parse_float=Decimal)
    assert parsed["value"] == Decimal("1e400")


@pytest.mark.asyncio
@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
async def test_json_formatter_rejects_non_standard_numeric_constants(
    constant: str,
) -> None:
    """RFC-compliant JSON excludes NaN and infinity constants."""
    with pytest.raises(ValueError, match="Invalid JSON string"):
        await json_formatter_handler({"json_string": f'{{"value":{constant}}}'})


def test_json_formatter_api_preserves_precise_and_large_numbers() -> None:
    """The authenticated API must preserve numeric values, not only the handler."""
    precise = _execute_formatter('{"value":1.0000000000000001}')
    assert precise["status"] == "success"
    precise_result = precise["result"]
    assert isinstance(precise_result, dict)
    precise_parsed = json.loads(
        str(precise_result["formatted_json"]), parse_float=Decimal
    )
    assert precise_parsed["value"] == Decimal("1.0000000000000001")

    large = _execute_formatter('{"value":1e400}')
    assert large["status"] == "success"
    large_result = large["result"]
    assert isinstance(large_result, dict)
    formatted_large = str(large_result["formatted_json"])
    assert "Infinity" not in formatted_large
    assert json.loads(formatted_large, parse_float=Decimal)["value"] == Decimal("1e400")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_json_formatter_api_rejects_non_standard_numeric_constants(
    constant: str,
) -> None:
    """The authenticated API must reject every non-standard numeric constant."""
    data = _execute_formatter(f'{{"value":{constant}}}')
    assert data["status"] == "failed"
    assert "Invalid JSON string" in str(data["message"])


@pytest.mark.asyncio
async def test_json_formatter_preserves_nested_json_value_types() -> None:
    """Rendering must preserve booleans, null, integers, strings, and containers."""
    raw = '{"values":[true,false,null,42,"한글",{},[]]}'

    result = await json_formatter_handler({"json_string": raw})

    assert json.loads(result["formatted_json"]) == {
        "values": [True, False, None, 42, "한글", {}, []]
    }


def test_json_renderer_rejects_non_finite_or_unknown_internal_values() -> None:
    """Internal rendering must fail closed for impossible non-JSON values."""
    with pytest.raises(ValueError, match="finite"):
        _render_json_value(Decimal("NaN"))
    with pytest.raises(ValueError, match="Unsupported JSON value type"):
        _render_json_value(object())
