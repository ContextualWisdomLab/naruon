import base64
import inspect
import json
import logging
import urllib.parse
from collections.abc import Callable
from typing import Any, Dict, List, Optional

import httpx
from core.url_validation import (
    _normalize_host,
    _reject_unsafe_ip_literal,
    _resolve_global_addresses,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["tools"])
logger = logging.getLogger(__name__)
ToolHandler = Callable[[Dict[str, Any]], Any]


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


class ToolCreate(BaseModel):
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


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description="도구의 이름")
    description: Optional[str] = Field(
        default=None, description="도구에 대한 상세 설명"
    )
    category: Optional[str] = Field(default=None, description="도구의 분류")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="도구 실행에 필요한 파라미터 스키마"
    )
    is_active: Optional[bool] = Field(default=None, description="도구의 활성화 여부")
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

async def mock_handler(params: Dict[str, Any]) -> str:
    encoded = json.dumps(params, ensure_ascii=False, sort_keys=True)
    return f"Mock execution successful with params: {encoded}"


async def thread_summarizer_handler(params: Dict[str, Any]) -> Any:
    thread_id = params.get("thread_id", "")
    return {
        "summary": f"이메일 스레드 {thread_id}에 대한 요약입니다. 여러 논의 사항이 정리되었습니다.",
        "key_points": ["일정 조율 완료", "계약서 초안 검토 필요"],
        "unresolved_questions": ["최종 승인자 확인"],
    }


async def action_item_extractor_handler(params: Dict[str, Any]) -> Any:
    return {
        "action_items": [
            {"task": "문서 검토 및 피드백 작성", "deadline": "2023-10-25T12:00:00Z"},
            {"task": "주간 회의 자료 준비", "deadline": "2023-10-26T09:00:00Z"},
        ],
        "source_length": len(params.get("email_content", "")),
    }


async def sender_dag_analytics_handler(params: Dict[str, Any]) -> Any:
    sender = params.get("sender_email", "")
    return {
        "sender": sender,
        "importance": "high",
        "department": "엔지니어링 팀",
        "recent_interactions": 15,
    }


async def meeting_candidate_finder_handler(params: Dict[str, Any]) -> Any:
    return {
        "candidates": [
            {"time": "2023-10-26T14:00:00Z", "location": "온라인 (Zoom)"},
            {"time": "2023-10-27T10:00:00Z", "location": "회의실 A"},
        ],
        "context_preview": params.get("email_content", "")[:30] + "...",
    }


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



async def email_translator_handler(params: Dict[str, Any]) -> Any:
    text = params.get("text", "")
    target_language = params.get("target_language", "ko")
    return {
        "translated_text": f"[{target_language} 번역본] {text}",
        "source_language_detected": "en",
        "confidence": 0.95,
    }


async def spam_phishing_detector_handler(params: Dict[str, Any]) -> Any:
    email_content = params.get("email_content", "")
    sender_domain = params.get("sender_domain", "")
    is_suspicious = "password" in email_content.lower() or "bank" in email_content.lower()
    return {
        "is_spam": False,
        "is_phishing": is_suspicious,
        "risk_score": 80 if is_suspicious else 10,
        "warnings": ["의심스러운 키워드 포함됨"] if is_suspicious else [],
    }


async def reply_drafter_handler(params: Dict[str, Any]) -> Any:
    original_email = params.get("original_email", "")
    intent = params.get("intent", "긍정적 동의")
    return {
        "draft": f"귀하의 이메일에 감사드립니다. {intent}의 맥락으로 다음과 같이 회신합니다...",
        "tone": "formal",
    }


async def sentiment_analyzer_handler(params: Dict[str, Any]) -> Any:
    text = params.get("text", "")
    is_positive = "thank" in text.lower() or "great" in text.lower()
    return {
        "sentiment": "positive" if is_positive else "neutral",
        "score": 0.85 if is_positive else 0.5,
        "key_emotions": ["감사", "기쁨"] if is_positive else ["중립"],
    }


async def grammar_checker_handler(params: Dict[str, Any]) -> Any:
    draft = params.get("draft_content", "")
    return {
        "corrected_text": draft.replace("안녕 하세요", "안녕하세요"),
        "errors_found": 1 if "안녕 하세요" in draft else 0,
        "suggestions": ["'안녕 하세요'는 '안녕하세요'로 붙여 쓰는 것이 맞습니다."] if "안녕 하세요" in draft else [],
    }


def is_safe_webhook_url(url: str) -> bool:
    try:
        validate_webhook_url(url)
    except ValueError:
        return False
    return True


def validate_webhook_url(url: str) -> None:
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
    _resolve_global_addresses("Webhook URL", hostname, port)


def make_webhook_handler(webhook_url: str) -> ToolHandler:
    validate_webhook_url(webhook_url)

    async def handler(params: Dict[str, Any]) -> Any:
        validate_webhook_url(webhook_url)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    webhook_url, json={"parameters": params}, timeout=10.0
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
        code="thread_summarizer",
        name="이메일 맥락 요약 (Thread Summarizer)",
        description="긴 이메일 스레드를 분석하여 핵심 맥락, 결정 사항, 미해결 질문을 추출합니다.",
        category="이메일 분석",
        parameters={"thread_id": "string"},
    ),
    thread_summarizer_handler,
)

registry.register(
    ToolInfo(
        code="action_item_extractor",
        name="실행 항목 자동 추출 (Action Item Extractor)",
        description="이메일 본문에서 사용자가 수행해야 할 작업(Task)과 마감일을 자동으로 식별합니다.",
        category="작업 관리",
        parameters={"email_content": "string"},
    ),
    action_item_extractor_handler,
)

registry.register(
    ToolInfo(
        code="sender_dag_analytics",
        name="발신자 관계 분석 (Sender DAG Analytics)",
        description="과거 이메일 기록을 바탕으로 발신자와의 관계(조직도 상 위치, 중요도 등)를 분석합니다.",
        category="관계 인텔리전스",
        parameters={"sender_email": "string"},
    ),
    sender_dag_analytics_handler,
)

registry.register(
    ToolInfo(
        code="meeting_candidate_finder",
        name="일정 후보 추출 (Meeting Candidate Finder)",
        description="이메일 텍스트에서 회의나 약속으로 예상되는 시간대와 장소를 추출하여 캘린더 등록 초안을 생성합니다.",
        category="일정 관리",
        parameters={"email_content": "string"},
    ),
    meeting_candidate_finder_handler,
)

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

async def text_analyzer_handler(params: Dict[str, Any]) -> Dict[str, int]:
    text = params.get("text", "")
    char_count = len(text)
    char_count_no_spaces = len(
        text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    )
    return {
        "char_count": char_count,
        "char_count_no_spaces": char_count_no_spaces,
        "word_count": len(text.split()),
    }

registry.register(
    ToolInfo(
        code="text_analyzer",
        name="텍스트 분석기 (Text Analyzer)",
        description="텍스트의 글자 수, 단어 수, 공백 제외 글자 수를 분석합니다.",
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
<<<<<<< HEAD


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
        code="spam_phishing_detector",
        name="스팸 및 피싱 탐지기 (Spam & Phishing Detector)",
        description="이메일 본문과 발신자 도메인을 분석하여 스팸 및 피싱 위험도를 평가합니다.",
        category="보안",
        parameters={"email_content": "string", "sender_domain": "string"},
    ),
    spam_phishing_detector_handler,
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
        category="작성 도조",
        parameters={"draft_content": "string"},
    ),
    grammar_checker_handler,
)

=======
>>>>>>> origin/develop

@router.get("/tools", response_model=list[ToolInfo])
def get_tools() -> list[ToolInfo]:
    """
    Naruon AI 이메일 워크스페이스에서 사용할 수 있는 분석 및 실행 도구 목록을 반환합니다.
    """
    return registry.get_all()


@router.post("/tools", response_model=ToolInfo, status_code=201)
def create_tool(tool_data: ToolCreate) -> ToolInfo:
    """
    새로운 도구를 등록합니다.
    """
    if registry.get(tool_data.code):
        raise HTTPException(
            status_code=400, detail="Tool with this code already exists"
        )

    tool_info = ToolInfo(**tool_data.model_dump())

    if tool_info.webhook_url:
        try:
            handler = make_webhook_handler(tool_info.webhook_url)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid or unsafe webhook URL: {e}"
            )
    else:
        handler = mock_handler

    registry.register(tool_info, handler)
    return tool_info


@router.get("/tools/{code}", response_model=ToolInfo)
def get_tool(code: str) -> ToolInfo:
    """
    특정 도구의 상세 정보를 반환합니다.
    """
    tool = registry.get(code)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.patch("/tools/{code}", response_model=ToolInfo)
def update_tool(code: str, tool_data: ToolUpdate) -> ToolInfo:
    """
    특정 도구의 정보를 업데이트합니다.
    """
    tool = registry.get(code)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    update_data = tool_data.model_dump(exclude_unset=True)

    # Validate webhook URL first to avoid state inconsistency
    handler = None
    if "webhook_url" in update_data:
        if update_data["webhook_url"]:
            try:
                handler = make_webhook_handler(update_data["webhook_url"])
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid or unsafe webhook URL: {e}"
                )
        else:
            handler = mock_handler

    # Apply updates safely
    for key, value in update_data.items():
        setattr(tool, key, value)

    if handler:
        registry.register(tool, handler)

    return tool


@router.delete("/tools/{code}", status_code=204)
def delete_tool(code: str) -> None:
    """
    특정 도구를 삭제(등록 해제)합니다.
    """
    tool = registry.get(code)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    registry.unregister(code)


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
        logger.exception("Tool execution failed", extra={"tool_code": code})
        return ExecuteResponse(
            status="failed",
            result=None,
            message=str(e),
        )
