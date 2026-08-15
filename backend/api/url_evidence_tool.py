"""Bounded, non-fetching HTTP(S) URL evidence extraction.

This module identifies URL-shaped evidence in caller-provided text, preserves
exact source spans, and returns a deterministic normalized representation for
comparison. It never resolves DNS, opens sockets, follows redirects, or fetches
remote resources; downstream code must make any egress decision separately.
"""

from __future__ import annotations

import ipaddress
import re
import urllib.parse
from typing import Any

from api.tools import ToolInfo, registry

MAX_INPUT_UTF8_BYTES = 1_048_576
MAX_URL_MATCHES = 100
MAX_URL_CANDIDATE_UTF8_BYTES = 4_096

_URL_CANDIDATE_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_MALFORMED_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_ESCAPE_RE = re.compile(r"%([0-9A-Fa-f]{2})")
_TRAILING_PROSE = ".,;:!?"
_BALANCED_CLOSERS = {")": "(", "]": "[", "}": "{"}
_INVALID_WARNING_CODES = {
    "invalid_host",
    "invalid_port",
    "invalid_url",
    "malformed_percent_encoding",
    "missing_host",
}


def _trim_terminal_punctuation(candidate: str) -> str:
    """Remove prose punctuation while preserving balanced URL delimiters."""
    trimmed = candidate
    while trimmed:
        terminal = trimmed[-1]
        if terminal in _TRAILING_PROSE:
            trimmed = trimmed[:-1]
            continue
        opener = _BALANCED_CLOSERS.get(terminal)
        if opener is not None and trimmed.count(terminal) > trimmed.count(opener):
            trimmed = trimmed[:-1]
            continue
        break
    return trimmed


def _canonicalize_percent_escapes(value: str) -> str:
    """Uppercase hexadecimal digits in valid percent escapes without decoding."""
    return _PERCENT_ESCAPE_RE.sub(lambda match: f"%{match.group(1).upper()}", value)


def _normalize_host(host: str) -> tuple[str, bool]:
    """Return a deterministic host spelling and whether it is an IPv6 literal."""
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        normalized = host.encode("idna").decode("ascii").lower()
        return normalized, False
    return parsed_ip.compressed.lower(), parsed_ip.version == 6


def _normalized_authority(
    parsed: urllib.parse.SplitResult,
    normalized_host: str,
    is_ipv6: bool,
    port: int | None,
) -> str:
    """Rebuild an authority while preserving userinfo and an explicit port."""
    userinfo = ""
    if "@" in parsed.netloc:
        userinfo = f"{parsed.netloc.rsplit('@', 1)[0]}@"
    host_text = f"[{normalized_host}]" if is_ipv6 else normalized_host
    port_text = f":{port}" if port is not None else ""
    return f"{userinfo}{host_text}{port_text}"


def _invalid_match(
    raw_value: str,
    source_start: int,
    source_end: int,
    warning_codes: list[str],
) -> dict[str, Any]:
    """Build a stable invalid evidence record when structural parsing fails."""
    scheme = raw_value.partition(":")[0].lower()
    return {
        "raw_value": raw_value,
        "normalized_value": _canonicalize_percent_escapes(raw_value),
        "source_start": source_start,
        "source_end": source_end,
        "scheme_code": scheme,
        "host_value": "",
        "contains_userinfo": "@" in raw_value.partition("//")[2].partition("/")[0],
        "validation_status": "invalid",
        "warning_codes": warning_codes,
    }


def _classify_candidate(
    raw_value: str,
    source_start: int,
    source_end: int,
) -> dict[str, Any]:
    """Parse one bounded candidate into an auditable URL evidence record."""
    warning_codes: list[str] = []
    malformed_percent = _MALFORMED_PERCENT_RE.search(raw_value) is not None
    if malformed_percent:
        warning_codes.append("malformed_percent_encoding")

    try:
        parsed = urllib.parse.urlsplit(raw_value)
    except ValueError:
        if "invalid_url" not in warning_codes:
            warning_codes.append("invalid_url")
        return _invalid_match(raw_value, source_start, source_end, warning_codes)

    contains_userinfo = "@" in parsed.netloc
    if contains_userinfo:
        warning_codes.append("userinfo_present")

    host = parsed.hostname
    if host is None or host == "":
        warning_codes.append("missing_host")
        return _invalid_match(raw_value, source_start, source_end, warning_codes)

    try:
        normalized_host, is_ipv6 = _normalize_host(host)
    except UnicodeError:
        warning_codes.append("invalid_host")
        return _invalid_match(raw_value, source_start, source_end, warning_codes)

    try:
        port = parsed.port
    except ValueError:
        warning_codes.append("invalid_port")
        return _invalid_match(raw_value, source_start, source_end, warning_codes)

    normalized_value = urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            _normalized_authority(parsed, normalized_host, is_ipv6, port),
            _canonicalize_percent_escapes(parsed.path),
            _canonicalize_percent_escapes(parsed.query),
            _canonicalize_percent_escapes(parsed.fragment),
        )
    )
    validation_status = (
        "invalid"
        if any(code in _INVALID_WARNING_CODES for code in warning_codes)
        else "warning"
        if warning_codes
        else "valid"
    )
    return {
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "source_start": source_start,
        "source_end": source_end,
        "scheme_code": parsed.scheme.lower(),
        "host_value": normalized_host,
        "contains_userinfo": contains_userinfo,
        "validation_status": validation_status,
        "warning_codes": warning_codes,
    }


async def url_evidence_handler(params: dict[str, Any]) -> dict[str, Any]:
    """Extract bounded absolute HTTP(S) URL evidence without network activity.

    Args:
        params: Validated tool parameters containing the source ``text``.

    Returns:
        A deterministic list of URL occurrences in source order plus the match
        count. Repeated spellings remain separate occurrences.

    Raises:
        ValueError: If the UTF-8 input, one URL candidate, or the number of URL
            occurrences exceeds the declared resource boundary.
    """
    text = params["text"]
    payload = text.encode("utf-8")
    if len(payload) > MAX_INPUT_UTF8_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_UTF8_BYTES} UTF-8 bytes")

    matches: list[dict[str, Any]] = []
    for source_match in _URL_CANDIDATE_RE.finditer(text):
        raw_candidate = source_match.group(0)
        raw_value = _trim_terminal_punctuation(raw_candidate)
        candidate_bytes = raw_value.encode("utf-8")
        if len(candidate_bytes) > MAX_URL_CANDIDATE_UTF8_BYTES:
            raise ValueError(
                f"URL candidate exceeds {MAX_URL_CANDIDATE_UTF8_BYTES} UTF-8 bytes"
            )
        if len(matches) >= MAX_URL_MATCHES:
            raise ValueError(f"URL match limit exceeds {MAX_URL_MATCHES}")

        source_start = source_match.start()
        source_end = source_start + len(raw_value)
        matches.append(_classify_candidate(raw_value, source_start, source_end))

    return {"matches": matches, "match_count": len(matches)}


def register_url_evidence_tool() -> None:
    """Register the URL evidence extractor once in the built-in tool catalog."""
    if registry.get("url_evidence_extractor") is not None:
        return

    registry.register(
        ToolInfo(
            code="url_evidence_extractor",
            name="URL evidence extractor",
            description=(
                "Locate absolute HTTP(S) URLs without fetching them. Use the "
                "returned source spans, normalized value, and warning codes to "
                "review exact URL evidence before taking any network action."
            ),
            category="유틸리티",
            parameters={"text": "string"},
        ),
        url_evidence_handler,
    )
