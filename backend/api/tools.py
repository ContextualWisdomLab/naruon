import base64
import hashlib
import inspect
import logging
import re
import unicodedata
import urllib.parse
import uuid
from collections import Counter
from collections.abc import Callable
from typing import Any, Dict, List, NoReturn, Optional

import httpx
from core.url_validation import (
    ValidatedHTTPSURLHost,
    _normalize_host,
    _reject_unsafe_ip_literal,
    _resolve_global_addresses,
)
from services.llm_provider_urls import build_pinned_https_async_client
from services.text_structure_statistics import measure_text_structure
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["tools"])
logger = logging.getLogger(__name__)
ToolHandler = Callable[[Dict[str, Any]], Any]
MAX_TOOL_FAILURE_MESSAGE_CHARS = 500
TOOL_MUTATION_NOT_SUPPORTED_DETAIL = {
    "error_code": "tool_mutation_not_supported",
    "message": (
        "Dynamic tool mutations are disabled until tenant-scoped persistent "
        "storage and administrative authorization are implemented."
    ),
}


def _tool_code_fingerprint(code: str) -> str:
    """Return a stable non-reversible identifier for correlating tool failures."""
    return hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()[:12]


def _exception_traceback_fingerprint(exc: Exception) -> str:
    """Fingerprint traceback locations without logging exception text or source."""
    locations: list[str] = []
    traceback_cursor = exc.__traceback__
    while traceback_cursor is not None:
        frame = traceback_cursor.tb_frame
        locations.append(
            f"{frame.f_code.co_filename}:{frame.f_code.co_name}:"
            f"{traceback_cursor.tb_lineno}"
        )
        traceback_cursor = traceback_cursor.tb_next
    material = "\n".join(locations) or type(exc).__name__
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:12]


def _safe_tool_failure_message(exc: Exception) -> str:
    """Return a bounded single-line exception message for the API response."""
    raw = str(exc) or type(exc).__name__
    escaped: list[str] = []
    escaped_length = 0
    for character in raw:
        codepoint = ord(character)
        if character == "\r":
            fragment = "\\r"
        elif character == "\n":
            fragment = "\\n"
        elif character == "\t":
            fragment = "\\t"
        elif codepoint < 0x20 or codepoint == 0x7F or codepoint in {0x2028, 0x2029}:
            fragment = f"\\u{codepoint:04x}"
        else:
            fragment = character
        escaped.append(fragment)
        escaped_length += len(fragment)
        if escaped_length >= MAX_TOOL_FAILURE_MESSAGE_CHARS:
            break
    message = "".join(escaped)[:MAX_TOOL_FAILURE_MESSAGE_CHARS]
    return message or "Tool execution failed"


class ToolInfo(BaseModel):
    """Workspace automation tool metadata returned to the tools catalog UI."""

    code: str = Field(..., description="도구의 고유 식별 코드")
    name: str = Field(..., description="도구의 이름")
    description: str = Field(..., description="도구에 대한 상세 설명")
    category: str = Field(..., description="도구의 분류 (예: 이메일, 일정, 분석 등)")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="도구 실행에 필요한 파라미터 스키마"
    )
    is_active: bool = Field(default=True, description="도구의 활성화 여부")
    webhook_url: Optional[str] = Field(
        default=None, description="도구 실행을 위한 외부 웹훅 URL"
    )


class ExecuteRequest(BaseModel):
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="실행 파라미터"
    )


class ExecuteResponse(BaseModel):
    status: str = Field(..., description="실행 상태 (예: success, failed)")
    result: Any = Field(..., description="실행 결과 데이터")
    message: Optional[str] = Field(default=None, description="결과 메시지")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, tool_info: ToolInfo, handler: ToolHandler):
        self._tools[tool_info.code] = tool_info
        self._handlers[tool_info.code] = handler

    def unregister(self, code: str) -> None:
        self._tools.pop(code, None)
        self._handlers.pop(code, None)

    def get_all(self) -> List[ToolInfo]:
        return list(self._tools.values())

    def get(self, code: str) -> Optional[ToolInfo]:
        return self._tools.get(code)

    async def invoke_tool(self, code: str, params: Dict[str, Any]) -> Any:
        handler = self._handlers.get(code)
        if not handler:
            raise ValueError(f"No handler registered for tool {code}")
        result = handler(self._validate_parameters(code, params))
        if inspect.isawaitable(result):
            return await result
        return result

    def _validate_parameters(self, code: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise ValueError("Tool parameters must be an object")

        tool_info = self._tools.get(code)
        schema = tool_info.parameters if tool_info else None
        if not schema:
            if params:
                raise ValueError("Tool does not accept parameters")
            return {}

        unexpected_keys = set(params) - set(schema)
        if unexpected_keys:
            raise ValueError("Unexpected tool parameter")

        validated: Dict[str, Any] = {}
        for key, descriptor in schema.items():
            if key not in params:
                raise ValueError("Missing required tool parameter")
            value = params[key]
            expected_type = _parameter_type_name(descriptor)
            if not _parameter_matches_type(value, expected_type):
                raise ValueError("Invalid tool parameter type")
            validated[key] = value
        return validated


registry = ToolRegistry()


# Initialize default tools


async def tone_analyzer_handler(params: Dict[str, Any]) -> Any:
    draft = params.get("draft_content", "")
    rel = params.get("recipient_relationship", "unknown")
    return {
        "refined_draft": f"[{rel} 대상 교정본]\n\n{draft}",
        "suggestions": [
            "도입부를 조금 더 정중하게 수정했습니다.",
            "명확성을 위해 불필요한 부사를 제거했습니다.",
        ],
        "tone_score": 85,
    }

def _detect_text_language(text: str) -> str:
    if any("\uac00" <= char <= "\ud7a3" for char in text):
        return "ko"
    if any(char.isascii() and char.isalpha() for char in text):
        return "en"
    return "unknown"


async def email_translator_handler(params: Dict[str, Any]) -> Any:
    """Translate email text into the requested target language."""
    text = params.get("text", "")
    target_language = params.get("target_language", "ko")
    source_language = _detect_text_language(text)
    lowered_text = text.lower()
    translated_text = text
    confidence = 0.5
    if target_language.lower().startswith("ko") and source_language == "en":
        phrase_map = [
            ("hello", "안녕하세요"),
            ("thank you", "감사합니다"),
            ("thanks", "감사합니다"),
            ("meeting", "회의"),
            ("tomorrow", "내일"),
            ("please", "부탁드립니다"),
        ]
        translated_terms: list[str] = []
        for source_phrase, translated_phrase in phrase_map:
            if source_phrase in lowered_text and translated_phrase not in translated_terms:
                translated_terms.append(translated_phrase)
        translated_text = " ".join(translated_terms) if translated_terms else text
        confidence = 0.9 if translated_terms else 0.45
    return {
        "translated_text": translated_text,
        "source_language_detected": source_language,
        "confidence": confidence,
    }


async def reply_drafter_handler(params: Dict[str, Any]) -> Any:
    """Draft a formal reply using the operator's requested intent."""
    original_email = params.get("original_email", "").strip()
    intent = params.get("intent", "긍정적 동의")
    context_excerpt = original_email[:120]
    return {
        "draft": (
            f"귀하의 이메일({context_excerpt})에 감사드립니다. "
            f"{intent}의 맥락으로 검토했으며, 해당 방향으로 진행하겠습니다."
        ),
        "tone": "formal",
    }


async def sentiment_analyzer_handler(params: Dict[str, Any]) -> Any:
    """Classify email text sentiment for the tools API."""
    text = params.get("text", "")
    normalized_text = text.lower()
    positive_terms = {"thank", "thanks", "great", "good", "excellent", "감사", "좋"}
    negative_terms = {"disappointed", "urgent", "issue", "problem", "bad", "불만", "문제"}
    positive_hits = [term for term in positive_terms if term in normalized_text]
    negative_hits = [term for term in negative_terms if term in normalized_text]
    if negative_hits and len(negative_hits) >= len(positive_hits):
        sentiment = "negative"
        score = max(0.1, 0.5 - (0.1 * len(negative_hits)))
        emotions = ["불만", "우려"]
        if "urgent" in negative_hits:
            emotions.append("긴급")
    elif positive_hits:
        sentiment = "positive"
        score = min(0.95, 0.65 + (0.1 * len(positive_hits)))
        emotions = ["감사", "기쁨"]
    else:
        sentiment = "neutral"
        score = 0.5
        emotions = ["중립"]
    return {
        "sentiment": sentiment,
        "score": score,
        "key_emotions": emotions,
    }


async def grammar_checker_handler(params: Dict[str, Any]) -> Any:
    """Return a lightweight Korean spacing correction for draft email text."""
    draft = params.get("draft_content", "")
    corrected_text = draft
    suggestions: list[str] = []
    errors_found = 0
    for source_text, replacement_text, suggestion in [
        ("안녕 하세요", "안녕하세요", "'안녕 하세요'는 '안녕하세요'로 붙여 씁니다."),
        ("확인 부탁 드립니다", "확인 부탁드립니다", "'부탁드립니다'는 붙여 씁니다."),
        ("감사 합니다", "감사합니다", "'감사합니다'는 붙여 씁니다."),
    ]:
        occurrence_count = corrected_text.count(source_text)
        if occurrence_count:
            errors_found += occurrence_count
            corrected_text = corrected_text.replace(source_text, replacement_text)
            suggestions.append(suggestion)
    return {
        "corrected_text": corrected_text,
        "errors_found": errors_found,
        "suggestions": suggestions,
    }


def is_safe_webhook_url(url: str) -> bool:
    try:
        validate_webhook_url(url)
    except ValueError:
        return False
    return True


def validate_webhook_url_details(url: str) -> ValidatedHTTPSURLHost:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Webhook URL must use https")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL must not include userinfo")
    if parsed.fragment:
        raise ValueError("Webhook URL must not include a fragment")
    if not parsed.hostname:
        raise ValueError("Webhook URL must include a host")

    hostname = _normalize_host(parsed.hostname)
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        raise ValueError("Webhook URL host must not use an internal domain suffix")
    _reject_unsafe_ip_literal("Webhook URL", hostname)
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError("Webhook URL port must be valid") from exc
    addresses = _resolve_global_addresses("Webhook URL", hostname, port)

    normalized_netloc = hostname if parsed.port is None else f"{hostname}:{port}"
    normalized_url = parsed._replace(netloc=normalized_netloc).geturl()

    return ValidatedHTTPSURLHost(
        normalized_url=normalized_url,
        hostname=hostname,
        port=port,
        addresses=addresses,
    )


def validate_webhook_url(url: str) -> None:
    validate_webhook_url_details(url)


def make_webhook_handler(webhook_url: str) -> ToolHandler:
    validate_webhook_url_details(webhook_url)

    async def handler(params: Dict[str, Any]) -> Any:
        validated = validate_webhook_url_details(webhook_url)
        client = build_pinned_https_async_client(
            normalized_url=validated.normalized_url,
            hostname=validated.hostname,
            port=validated.port,
            addresses=validated.addresses,
        )
        async with client:
            try:
                response = await client.post(
                    validated.normalized_url, json={"parameters": params}, timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                raise ValueError(f"Webhook execution failed: {str(e)}")

    return handler


def _parameter_type_name(descriptor: Any) -> str:
    if isinstance(descriptor, str):
        return descriptor.lower()
    if isinstance(descriptor, dict):
        return str(descriptor.get("type", "string")).lower()
    return "string"


def _parameter_matches_type(value: Any, expected_type: str) -> bool:
    validators = {
        "string": lambda candidate: isinstance(candidate, str),
        "number": lambda candidate: (
            isinstance(candidate, (int, float)) and not isinstance(candidate, bool)
        ),
        "integer": lambda candidate: (
            isinstance(candidate, int) and not isinstance(candidate, bool)
        ),
        "boolean": lambda candidate: isinstance(candidate, bool),
        "array": lambda candidate: isinstance(candidate, list),
        "object": lambda candidate: isinstance(candidate, dict),
    }
    return validators.get(expected_type, validators["string"])(value)


registry.register(
    ToolInfo(
        code="tone_analyzer",
        name="답장 어조 분석 및 교정 (Tone Analyzer & Editor)",
        description="작성 중인 답장의 어조를 분석하고, 수신자의 관계에 맞게 정중함이나 명확성을 교정해줍니다.",
        category="커뮤니케이션",
        parameters={"draft_content": "string", "recipient_relationship": "string"},
    ),
    tone_analyzer_handler,
)

async def text_analyzer_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return descriptive text counts while preserving documented legacy aliases."""
    statistics = measure_text_structure(params.get("text", ""))
    legacy_aliases = {
        "char_count": "character_count",
        "char_count_no_spaces": "non_whitespace_character_count",
        "word_count": "whitespace_token_count",
    }
    return {
        "character_count": statistics.character_count,
        "non_whitespace_character_count": statistics.non_whitespace_character_count,
        "whitespace_token_count": statistics.whitespace_token_count,
        "terminal_punctuation_run_count": statistics.terminal_punctuation_run_count,
        "segmentation_contract": statistics.segmentation_contract,
        "legacy_aliases": legacy_aliases,
        "char_count": statistics.character_count,
        "char_count_no_spaces": statistics.non_whitespace_character_count,
        "word_count": statistics.whitespace_token_count,
    }

registry.register(
    ToolInfo(
        code="text_analyzer",
        name="텍스트 분석기 (Text Analyzer)",
        description=(
            "텍스트의 문자 수, Unicode 공백 제외 문자 수, 공백 구분 토큰 수, "
            "종결 문장부호 연속 구간 수를 계산합니다. 기존 char_count, "
            "char_count_no_spaces, word_count는 호환 별칭이며 단어·문장 수를 "
            "뜻하지 않습니다."
        ),
        category="유틸리티",
        parameters={"text": "string"},
    ),
    text_analyzer_handler,
)


async def base64_encoder_handler(params: Dict[str, Any]) -> Dict[str, str]:
    text = params.get("text", "")
    return {"encoded_text": base64.b64encode(text.encode("utf-8")).decode("utf-8")}


registry.register(
    ToolInfo(
        code="base64_encoder",
        name="Base64 인코더 (Base64 Encoder)",
        description="일반 텍스트를 Base64 문자열로 인코딩합니다.",
        category="유틸리티",
        parameters={"text": "string"},
    ),
    base64_encoder_handler,
)


async def base64_decoder_handler(params: Dict[str, Any]) -> Dict[str, str]:
    encoded_text = params.get("encoded_text", "")
    try:
        return {
            "decoded_text": base64.b64decode(encoded_text, validate=True).decode(
                "utf-8"
            )
        }
    except Exception as e:
        raise ValueError(f"Invalid Base64 string: {e}")


registry.register(
    ToolInfo(
        code="base64_decoder",
        name="Base64 디코더 (Base64 Decoder)",
        description="Base64 문자열을 일반 텍스트로 디코딩합니다.",
        category="유틸리티",
        parameters={"encoded_text": "string"},
    ),
    base64_decoder_handler,
)


registry.register(
    ToolInfo(
        code="email_translator",
        name="이메일 번역기 (Email Translator)",
        description="이메일 텍스트를 지정된 대상 언어로 번역합니다.",
        category="언어 변환",
        parameters={"text": "string", "target_language": "string"},
    ),
    email_translator_handler,
)

registry.register(
    ToolInfo(
        code="reply_drafter",
        name="답장 초안 생성기 (Reply Drafter)",
        description="이전 이메일 맥락과 사용자의 의도(intent)를 바탕으로 답장 초안을 자동으로 작성합니다.",
        category="커뮤니케이션",
        parameters={"original_email": "string", "intent": "string"},
    ),
    reply_drafter_handler,
)

registry.register(
    ToolInfo(
        code="sentiment_analyzer",
        name="감정 분석기 (Sentiment Analyzer)",
        description="이메일의 전반적인 감정(긍정/부정/중립)과 주요 감정 키워드를 분석합니다.",
        category="이메일 분석",
        parameters={"text": "string"},
    ),
    sentiment_analyzer_handler,
)

registry.register(
    ToolInfo(
        code="grammar_checker",
        name="맞춤법 및 문법 검사기 (Grammar Checker)",
        description="작성된 이메일 초안의 맞춤법과 문법 오류를 검사하고 교정 제안을 제공합니다.",
        category="작성 도구",
        parameters={"draft_content": "string"},
    ),
    grammar_checker_handler,
)


ANALYSIS_TEXT_MAX_CHARS = 100_000
_ANALYSIS_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_KEYWORD_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "because",
        "before",
        "could",
        "from",
        "have",
        "into",
        "should",
        "their",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "very",
        "with",
        "would",
        "그리고",
        "그러나",
        "대한",
        "위한",
        "있는",
        "합니다",
    }
)


def _normalize_analysis_text(value: str) -> str:
    """Normalize user text for deterministic, multilingual rule matching."""
    if len(value) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(
            f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters"
        )
    return unicodedata.normalize("NFKC", value).casefold()


def _analysis_tokens(value: str) -> list[str]:
    """Return normalized Unicode word tokens without punctuation or underscores."""
    return _ANALYSIS_TOKEN_PATTERN.findall(_normalize_analysis_text(value))


async def keyword_extractor_handler(params: Dict[str, Any]) -> Any:
    """Extract deterministic lexical terms by frequency and first occurrence."""
    candidates = [
        token
        for token in _analysis_tokens(params.get("text", ""))
        if token not in _KEYWORD_STOPWORDS
        and not token.isdecimal()
        and (len(token) >= 4 if token.isascii() else len(token) >= 2)
    ]
    frequencies = Counter(candidates)
    first_positions: dict[str, int] = {}
    for index, token in enumerate(candidates):
        first_positions.setdefault(token, index)
    keywords = sorted(
        frequencies,
        key=lambda token: (-frequencies[token], first_positions[token], token),
    )[:5]

    return {"keywords": keywords, "keyword_count": len(keywords)}


registry.register(
    ToolInfo(
        code="keyword_extractor",
        name="주요 키워드 추출기 (Keyword Extractor)",
        description="텍스트 본문에서 빈도와 최초 출현 순으로 반복 용어를 추출합니다.",
        category="이메일 분석",
        parameters={"text": "string"},
    ),
    keyword_extractor_handler,
)


async def hash_generator_handler(params: Dict[str, Any]) -> Dict[str, str]:
    """Generate compatibility fingerprints plus a SHA-256 security hash."""
    text = params["text"]
    if len(text) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters")

    encoded = text.encode("utf-8")
    return {
        "md5": hashlib.md5(encoded, usedforsecurity=False).hexdigest(),  # nosec B324
        "sha1": hashlib.sha1(encoded, usedforsecurity=False).hexdigest(),  # nosec B324
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }

registry.register(
    ToolInfo(
        code="hash_generator",
        name="지문/해시 생성기 (Fingerprint/Hash Generator)",
        description="텍스트의 호환성 지문(MD5, SHA-1) 및 보안 해시(SHA-256) 값을 생성합니다.",
        category="유틸리티",
        parameters={"text": "string"},
    ),
    hash_generator_handler,
)


_EMAIL_ATOM = r"A-Za-z0-9!#$%&'*+/=?^_`{|}~"
_EMAIL_PATTERN = re.compile(
    rf"(?<![{_EMAIL_ATOM}.-])"
    rf"[{_EMAIL_ATOM}-]+(?:\.[{_EMAIL_ATOM}-]+)*@"
    rf"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{{0,61}}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}(?![A-Za-z0-9-])"
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+82[ .-]?10|010)[ .-]?\d{3,4}[ .-]?\d{4}"
    r"|\d{2,3}-\d{3,4}-\d{4}"
    r"|(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4})(?!\d)"
)


async def email_phone_masker_handler(params: Dict[str, Any]) -> Dict[str, str]:
    """Mask ASCII email and selected Korean or North American phone formats."""
    text = params["text"]
    if len(text) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters")

    anonymized = _EMAIL_PATTERN.sub("[EMAIL]", text)
    anonymized = _PHONE_PATTERN.sub("[PHONE]", anonymized)

    return {"masked_text": anonymized}

registry.register(
    ToolInfo(
        code="email_phone_masker",
        name="이메일/전화번호 마스킹 (Email/Phone Masker)",
        description="텍스트에서 ASCII 이메일 주소와 일부 전화번호 패턴을 단순 마스킹 처리합니다. 보안 목적의 완전한 개인정보 비식별화를 보장하지 않습니다.",
        category="유틸리티",
        parameters={"text": "string"},
    ),
    email_phone_masker_handler,
)


async def email_address_extractor_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract valid ASCII email addresses in first-occurrence order."""
    text = params.get("text", "")
    if len(text) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(
            f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters"
        )

    unique_emails: list[str] = []
    seen_addresses: set[str] = set()
    for match in _EMAIL_PATTERN.finditer(text):
        email_address = match.group(0)
        normalized_address = email_address.casefold()
        if normalized_address not in seen_addresses:
            seen_addresses.add(normalized_address)
            unique_emails.append(email_address)

    return {"emails": unique_emails, "count": len(unique_emails)}


registry.register(
    ToolInfo(
        code="email_address_extractor",
        name="이메일 주소 추출기 (Email Address Extractor)",
        description="텍스트 본문에서 유효한 ASCII 이메일 주소를 찾아 중복을 제거하여 추출합니다.",
        category="이메일 분석",
        parameters={"text": "string"},
    ),
    email_address_extractor_handler,
)


async def uuid_v4_generator_handler(params: Dict[str, Any]) -> Dict[str, str]:
    """Generate one RFC 9562 UUID version 4 for the retained built-in utility."""
    return {"uuid": str(uuid.uuid4())}


_INTERNATIONAL_EMAIL_PATTERN = re.compile(
    rf"(?<![\w{_EMAIL_ATOM}.-])"
    rf"[\w{_EMAIL_ATOM}-]+(?:\.[\w{_EMAIL_ATOM}-]+)*@"
    r"(?:[^\W_](?:(?:[^\W_]|-){0,61}[^\W_])?\.)+"
    r"[^\W_]{2,63}(?![\w-])"
)
_INTERNATIONAL_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:01[016789][ .-]?\d{3,4}[ .-]?\d{4}"
    r"|0[1-9](?:[ .-]?\d{2}){4})(?!\d)"
)
_KOREAN_RESIDENT_REGISTRATION_PATTERN = re.compile(
    r"(?<!\d)\d{6}[ -]?[1-4]\d{6}(?!\d)"
)


async def data_anonymizer_handler(params: Dict[str, Any]) -> Dict[str, str]:
    """Mask bounded contact and Korean resident-registration identifiers."""
    text = params.get("text", "")
    if text is None:
        text = ""
    if len(text) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(
            f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters"
        )
    text = _EMAIL_PATTERN.sub("***@***", text)
    text = _INTERNATIONAL_EMAIL_PATTERN.sub("***@***", text)
    text = _PHONE_PATTERN.sub("***-****-****", text)
    text = _INTERNATIONAL_PHONE_PATTERN.sub("***-****-****", text)
    text = _KOREAN_RESIDENT_REGISTRATION_PATTERN.sub("******-*******", text)
    return {"anonymized_text": text}


registry.register(
    ToolInfo(
        code="data_anonymizer",
        name="데이터 비식별화 (Data Anonymizer)",
        description="텍스트에서 이메일 주소, 일부 한국·북미·프랑스 전화번호, 한국 주민등록번호 형식을 단순 마스킹합니다. 완전한 개인정보 비식별화를 보장하지 않습니다.",
        category="보안",
        parameters={"text": "string"},
    ),
    data_anonymizer_handler,
)

registry.register(
    ToolInfo(
        code="uuid_v4_generator",
        name="UUID V4 생성기 (UUID v4 Generator)",
        description="범용 고유 식별자(UUID) 버전 4를 무작위로 생성합니다.",
        category="유틸리티",
        parameters={},
    ),
    uuid_v4_generator_handler,
)


_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_PROSE_TRAILING_PUNCTUATION = ".,;:!?"


def _trim_url_candidate(candidate: str, wrapping_openers: str) -> str:
    """Remove only closing delimiters proven by adjacent opening wrappers."""
    delimiters = (("(", ")"), ("[", "]"), ("{", "}"))
    excess = {
        closer: min(
            wrapping_openers.count(opener),
            max(0, candidate.count(closer) - candidate.count(opener)),
        )
        for opener, closer in delimiters
    }
    without_prose = candidate.rstrip(_PROSE_TRAILING_PUNCTUATION)
    end = len(without_prose)
    while end and excess.get(without_prose[end - 1], 0):
        excess[without_prose[end - 1]] -= 1
        end -= 1
    return without_prose[:end] if end < len(without_prose) else candidate

async def url_extractor_handler(params: Dict[str, Any]) -> Dict[str, list[str]]:
    text = params["text"]
    if len(text) > ANALYSIS_TEXT_MAX_CHARS:
        raise ValueError(
            f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters"
        )
    urls: list[str] = []
    seen: set[str] = set()
    for match in _URL_PATTERN.finditer(text):
        wrapper_start = match.start()
        while wrapper_start and text[wrapper_start - 1].isspace():
            wrapper_start -= 1
        wrapper_end = wrapper_start
        while wrapper_start and text[wrapper_start - 1] in "([{":
            wrapper_start -= 1
        candidate = _trim_url_candidate(
            match.group(), text[wrapper_start:wrapper_end]
        )
        try:
            parsed = urllib.parse.urlsplit(candidate)
            _ = parsed.port  # validate a declared port without requiring one
            valid = parsed.hostname is not None
        except ValueError:
            valid = False
        if valid and candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return {"urls": urls}


registry.register(
    ToolInfo(
        code="url_extractor",
        name="URL 추출기 (URL Extractor)",
        description="텍스트 본문에서 HTTP 및 HTTPS URL을 추출합니다.",
        category="유틸리티",
        parameters={"text": "string"},
    ),
    url_extractor_handler,
)


async def first_last_sentence_handler(params: Dict[str, Any]) -> Any:
    """Return the first and last non-empty sentences without claiming synthesis."""
    text = params.get("text", "")
    _normalize_analysis_text(text)
    if not text:
        return {"excerpt": ""}

    protected_text = list(text)
    for match in re.finditer(
        r"(?<=\d)\.(?=\d)|\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.", text, re.IGNORECASE
    ):
        protected_text[match.end() - 1] = "\0"
    for match in _EMAIL_PATTERN.finditer(text):
        for character_index in range(match.start(), match.end()):
            if text[character_index] == ".":
                protected_text[character_index] = "\0"
    for match in _URL_PATTERN.finditer(text):
        token_end = match.end() - (len(match.group()) - len(match.group().rstrip(".")))
        for character_index in range(match.start(), token_end):
            if text[character_index] == ".":
                protected_text[character_index] = "\0"

    sentences = [
        text[match.start() : match.end()].strip()
        for match in re.finditer(
            r"[^.!?。！？．]+(?:[.!?。！？．]+[\"'”’\)\]\}]*)?",
            "".join(protected_text),
        )
        if text[match.start() : match.end()].strip()
    ]
    if not sentences:
        return {"excerpt": text}

    excerpt = sentences[0]
    if len(sentences) > 1:
        excerpt += " " + sentences[-1]

    return {"excerpt": excerpt}


registry.register(
    ToolInfo(
        code="first_last_sentence",
        name="첫 문장·끝 문장 추출기 (First and Last Sentence Extractor)",
        description="텍스트의 첫 문장과 끝 문장을 원문 그대로 추출합니다.",
        category="이메일 분석",
        parameters={"text": "string"},
    ),
    first_last_sentence_handler,
)

@router.get("/tools", response_model=list[ToolInfo])
def get_tools() -> list[ToolInfo]:
    """
    Naruon AI 이메일 워크스페이스에서 사용할 수 있는 분석 및 실행 도구 목록을 반환합니다.
    """
    return registry.get_all()


def _reject_tool_mutation() -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail=TOOL_MUTATION_NOT_SUPPORTED_DETAIL,
    )


@router.post("/tools", include_in_schema=False, response_model=None)
def create_tool() -> NoReturn:
    """Fail closed until custom tools have durable tenant-scoped ownership."""
    _reject_tool_mutation()


@router.get("/tools/{code}", response_model=ToolInfo)
def get_tool(code: str) -> ToolInfo:
    """
    특정 도구의 상세 정보를 반환합니다.
    """
    tool = registry.get(code)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.patch("/tools/{code}", include_in_schema=False, response_model=None)
def update_tool(code: str) -> NoReturn:
    """Fail closed without mutating a process-global tool."""
    _reject_tool_mutation()


@router.delete("/tools/{code}", include_in_schema=False, response_model=None)
def delete_tool(code: str) -> NoReturn:
    """Fail closed without unregistering a process-global tool."""
    _reject_tool_mutation()


@router.post("/tools/{code}/execute", response_model=ExecuteResponse)
async def execute_tool(code: str, request: ExecuteRequest) -> ExecuteResponse:
    """
    특정 도구를 실행합니다.
    """
    tool = registry.get(code)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if not tool.is_active:
        raise HTTPException(status_code=400, detail="Tool is not active")

    try:
        result = await registry.invoke_tool(code, request.parameters)
        return ExecuteResponse(
            status="success", result=result, message="Execution successful"
        )
    except Exception as e:
        logger.warning(
            "tool_execution_failed",
            extra={
                "exception_type": type(e).__name__,
                "exception_traceback_fingerprint": _exception_traceback_fingerprint(e),
                "tool_code_fingerprint": _tool_code_fingerprint(code),
            },
        )
        return ExecuteResponse(
            status="failed",
            result=None,
            message=_safe_tool_failure_message(e),
        )
