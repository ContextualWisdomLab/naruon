"""Regression contract for standards-compliant JSON formatting."""

import json
from decimal import Decimal

import pytest

from api.tools import _render_json_value, json_formatter_handler


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
