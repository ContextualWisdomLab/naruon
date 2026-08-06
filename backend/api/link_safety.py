"""Fail-closed URL classification for the public link safety tool."""

from typing import Any
from urllib.parse import unquote, urlparse

from api.tools import ToolInfo, registry

_MALFORMED_WARNING = "Path traversal or malformed URL detected"
_SUSPICIOUS_DOMAIN_MARKERS = (
    ".ru",
    ".tk",
    ".zip",
    ".xyz",
    "free-",
    "login-",
    "secure-",
)


def _high_risk_result() -> dict[str, Any]:
    """Return the stable fail-closed payload for malformed or traversal input."""
    return {
        "is_https": False,
        "has_suspicious_domain": True,
        "risk_level": "High",
        "warnings": [_MALFORMED_WARNING],
    }


def _contains_path_traversal(path: str) -> bool:
    """Detect traversal after URL decoding and slash normalization."""
    decoded_path = unquote(path).replace("\\", "/")
    return any(segment == ".." for segment in decoded_path.split("/"))


async def link_safety_verifier_handler(params: dict[str, Any]) -> dict[str, Any]:
    """Classify only well-formed HTTP(S) URLs and fail closed otherwise."""
    raw_url = str(params.get("url", "")).strip()
    try:
        parsed_url = urlparse(raw_url)
        normalized_domain = parsed_url.hostname.lower() if parsed_url.hostname else ""
        parsed_url.port
    except ValueError:
        return _high_risk_result()

    normalized_scheme = parsed_url.scheme.lower()
    if normalized_scheme not in {"http", "https"} or not normalized_domain:
        return _high_risk_result()
    if _contains_path_traversal(parsed_url.path):
        return _high_risk_result()

    is_https = normalized_scheme == "https"
    has_suspicious_domain = any(
        marker in normalized_domain for marker in _SUSPICIOUS_DOMAIN_MARKERS
    )
    risk_level = "Low"
    if not is_https or has_suspicious_domain:
        risk_level = "High" if not is_https and has_suspicious_domain else "Medium"

    return {
        "is_https": is_https,
        "has_suspicious_domain": has_suspicious_domain,
        "risk_level": risk_level,
    }


def register_link_safety_verifier() -> None:
    """Replace the provisional verifier with the parser-backed implementation."""
    registry.register(
        ToolInfo(
            code="link_safety_verifier",
            name="링크 안전성 검증기 (Link Safety Verifier)",
            description=(
                "전달된 URL의 구조, HTTPS 여부와 의심스러운 도메인을 검사하여 "
                "위험도를 평가합니다."
            ),
            category="보안",
            parameters={"url": "string"},
        ),
        link_safety_verifier_handler,
    )
