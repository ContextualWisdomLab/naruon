import pytest
from api.tools import _detect_text_language, sentiment_analyzer_handler, url_extractor_handler, json_formatter_handler
import json

def test_detect_text_language_unknown():
    assert _detect_text_language("12345") == "unknown"
    assert _detect_text_language("!@#$") == "unknown"

def test_detect_text_language_ko():
    assert _detect_text_language("안녕하세요") == "ko"

@pytest.mark.asyncio
async def test_sentiment_analyzer_positive():
    params = {"text": "thank you very much!"}
    result = await sentiment_analyzer_handler(params)
    assert result["sentiment"] == "positive"
    assert "감사" in result["key_emotions"]

@pytest.mark.asyncio
async def test_sentiment_analyzer_neutral():
    params = {"text": "hello this is a neutral text."}
    result = await sentiment_analyzer_handler(params)
    assert result["sentiment"] == "neutral"
    assert "중립" in result["key_emotions"]

@pytest.mark.asyncio
async def test_url_extractor_handler():
    params = {"text": "Check out https://github.com and http://example.org for more info."}
    result = await url_extractor_handler(params)
    assert result["count"] == 2
    assert "https://github.com" in result["urls"]
    assert "http://example.org" in result["urls"]

@pytest.mark.asyncio
async def test_json_formatter_handler_valid():
    params = {"json_string": '{"key": "value"}'}
    result = await json_formatter_handler(params)
    assert result["is_valid"] == True
    assert '"key": "value"' in result["formatted_json"]

@pytest.mark.asyncio
async def test_json_formatter_handler_invalid():
    params = {"json_string": '{"key": "value"'}
    result = await json_formatter_handler(params)
    assert result["is_valid"] == False
    assert result["formatted_json"] == ""
    assert "error" in result
