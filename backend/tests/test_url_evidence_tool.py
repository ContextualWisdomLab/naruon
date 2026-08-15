"""Regression tests for Naruon's bounded URL-evidence extractor."""

import socket

import pytest

import main
from api.tools import registry
from api.url_evidence_tool import register_url_evidence_tool


@pytest.fixture(autouse=True)
def _ensure_url_evidence_tool_registered() -> None:
    """Keep tests independent of import order while preserving idempotent startup."""
    register_url_evidence_tool()


def test_application_bootstrap_registers_url_evidence_tool() -> None:
    """Loading the FastAPI application must expose the built-in URL evidence tool."""
    assert main.app is not None
    tool = registry.get("url_evidence_extractor")
    assert tool is not None
    assert tool.parameters == {"text": "string"}


def test_url_evidence_registration_is_idempotent() -> None:
    """Repeated startup registration must preserve the existing catalog entry."""
    original = registry.get("url_evidence_extractor")

    assert original is not None
    register_url_evidence_tool()

    assert registry.get("url_evidence_extractor") is original


@pytest.mark.asyncio
async def test_url_evidence_preserves_unicode_offsets_and_balanced_parentheses() -> None:
    """Evidence spans must point back to exact source while trailing prose is excluded."""
    text = "참고 (https://Example.COM/a_(b)?q=%ed%95%9c#frag), 끝"

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert result["match_count"] == 1
    [match] = result["matches"]
    assert match == {
        "raw_value": "https://Example.COM/a_(b)?q=%ed%95%9c#frag",
        "normalized_value": "https://example.com/a_(b)?q=%ED%95%9C#frag",
        "source_start": text.index("https://"),
        "source_end": text.index("), 끝"),
        "scheme_code": "https",
        "host_value": "example.com",
        "contains_userinfo": False,
        "validation_status": "valid",
        "warning_codes": [],
    }
    assert text[match["source_start"] : match["source_end"]] == match["raw_value"]


@pytest.mark.asyncio
async def test_url_evidence_trims_only_unbalanced_terminal_delimiters() -> None:
    """Balanced square/curly path delimiters survive while prose closers are removed."""
    text = "https://example.com/a[1]] https://example.com/b{c}}"

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert [item["raw_value"] for item in result["matches"]] == [
        "https://example.com/a[1]",
        "https://example.com/b{c}",
    ]


@pytest.mark.asyncio
async def test_url_evidence_preserves_repeated_source_locations() -> None:
    """Repeated URL spellings remain separate auditable occurrences."""
    text = "https://example.com/a 그리고 https://example.com/a"

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert result["match_count"] == 2
    first, second = result["matches"]
    assert first["raw_value"] == second["raw_value"] == "https://example.com/a"
    assert first["source_start"] == 0
    assert second["source_start"] == text.rindex("https://")
    assert first["source_end"] < second["source_start"]


@pytest.mark.asyncio
async def test_url_evidence_normalizes_idna_ipv6_ipv4_and_flags_userinfo() -> None:
    """Host normalization is deterministic and credential-bearing URLs are surfaced."""
    text = (
        "https://user:pw@BÜCHER.example/경로 "
        "https://[2001:0db8:0:0:0:0:0:1]:8443/a "
        "HTTP://127.0.0.1:443/a"
    )

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert result["match_count"] == 3
    first, second, third = result["matches"]
    assert first["host_value"] == "xn--bcher-kva.example"
    assert first["normalized_value"] == "https://user:pw@xn--bcher-kva.example/경로"
    assert first["contains_userinfo"] is True
    assert first["validation_status"] == "warning"
    assert first["warning_codes"] == ["userinfo_present"]

    assert second["host_value"] == "2001:db8::1"
    assert second["normalized_value"] == "https://[2001:db8::1]:8443/a"
    assert second["contains_userinfo"] is False
    assert second["validation_status"] == "valid"
    assert second["warning_codes"] == []

    assert third["host_value"] == "127.0.0.1"
    assert third["normalized_value"] == "http://127.0.0.1:443/a"
    assert third["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_url_evidence_ignores_other_schemes_and_retains_invalid_http_evidence() -> None:
    """Only HTTP(S) candidates are evidence, including malformed candidates for audit."""
    text = "ftp://ignored.example https:///missing https://example.com/%zz"

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert result["match_count"] == 2
    missing_host, malformed_percent = result["matches"]
    assert missing_host["raw_value"] == "https:///missing"
    assert missing_host["validation_status"] == "invalid"
    assert missing_host["warning_codes"] == ["missing_host"]
    assert malformed_percent["raw_value"] == "https://example.com/%zz"
    assert malformed_percent["validation_status"] == "invalid"
    assert malformed_percent["warning_codes"] == ["malformed_percent_encoding"]


@pytest.mark.asyncio
async def test_url_evidence_retains_parser_host_and_port_failures() -> None:
    """Malformed absolute HTTP(S) candidates remain inspectable with stable reasons."""
    oversized_label = "a" * 64
    text = (
        "https://[::1/a "
        f"https://{oversized_label}.example/a "
        "https://example.com:99999/a"
    )

    result = await registry.invoke_tool("url_evidence_extractor", {"text": text})

    assert result["match_count"] == 3
    parser_error, host_error, port_error = result["matches"]
    assert parser_error["validation_status"] == "invalid"
    assert parser_error["warning_codes"] == ["invalid_url"]
    assert host_error["validation_status"] == "invalid"
    assert host_error["warning_codes"] == ["invalid_host"]
    assert port_error["validation_status"] == "invalid"
    assert port_error["warning_codes"] == ["invalid_port"]


@pytest.mark.asyncio
async def test_url_evidence_never_resolves_or_connects_to_extracted_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extraction must remain pure even when a URL names an external host."""

    def _network_forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("URL evidence extraction must not perform network I/O")

    monkeypatch.setattr(socket, "getaddrinfo", _network_forbidden)
    monkeypatch.setattr(socket, "create_connection", _network_forbidden)

    result = await registry.invoke_tool(
        "url_evidence_extractor", {"text": "See https://example.com/a?q=1#proof."}
    )

    assert result["match_count"] == 1
    assert result["matches"][0]["normalized_value"] == "https://example.com/a?q=1#proof"


@pytest.mark.asyncio
async def test_url_evidence_enforces_utf8_input_byte_limit() -> None:
    """The one-mebibyte input boundary is measured after UTF-8 encoding."""
    accepted = await registry.invoke_tool(
        "url_evidence_extractor", {"text": "a" * 1_048_576}
    )
    assert accepted == {"matches": [], "match_count": 0}

    with pytest.raises(ValueError, match="Input exceeds 1048576 UTF-8 bytes"):
        await registry.invoke_tool(
            "url_evidence_extractor", {"text": "é" * 524_289}
        )


@pytest.mark.asyncio
async def test_url_evidence_fails_closed_on_excessive_matches() -> None:
    """A bounded evidence response must reject rather than silently truncate matches."""
    text = " ".join(f"https://host{index}.example" for index in range(101))

    with pytest.raises(ValueError, match="URL match limit exceeds 100"):
        await registry.invoke_tool("url_evidence_extractor", {"text": text})


@pytest.mark.asyncio
async def test_url_evidence_fails_closed_on_oversized_candidate() -> None:
    """A single pathological candidate must not bypass the per-match byte bound."""
    text = "https://example.com/" + ("a" * 4_077)

    assert len(text.encode("utf-8")) == 4_097
    with pytest.raises(ValueError, match="URL candidate exceeds 4096 UTF-8 bytes"):
        await registry.invoke_tool("url_evidence_extractor", {"text": text})
