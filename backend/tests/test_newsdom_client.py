"""SSRF / allowlist tests for the NewsDOM sidecar client.

These exercise the pure URL-normalization layer (no DNS / no network) plus the
request-time configuration guards.
"""

import pytest

from core.config import settings
from services.newsdom_client import (
    NEWSDOM_BASE_URL_NOT_ALLOWED,
    NEWSDOM_MAX_PARSE_UPLOAD_BYTES,
    NewsdomConfigurationError,
    NewsdomPayloadTooLargeError,
    NewsdomRequestError,
    _normalize_newsdom_base_url,
    request_pdf_dom,
)


@pytest.fixture
def newsdom_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_NEWSDOM_HOSTS", "newsdom.example.com")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_NEWSDOM_PROVIDERS", False)
    return settings


def test_allowlisted_https_host_is_normalized(newsdom_allowlist):
    normalized, hostname, port = _normalize_newsdom_base_url(
        "https://newsdom.example.com/parse-root/"
    )
    assert hostname == "newsdom.example.com"
    assert port == 443
    assert normalized == "https://newsdom.example.com/parse-root/"


def test_host_not_in_allowlist_is_rejected(newsdom_allowlist):
    with pytest.raises(ValueError) as excinfo:
        _normalize_newsdom_base_url("https://evil.example.com")
    assert str(excinfo.value) == NEWSDOM_BASE_URL_NOT_ALLOWED


def test_plain_http_remote_host_is_rejected(newsdom_allowlist):
    # Even an allowlisted host may not be reached over plain http when local
    # providers are disabled.
    with pytest.raises(ValueError):
        _normalize_newsdom_base_url("http://newsdom.example.com")


def test_ip_literal_host_is_rejected(newsdom_allowlist):
    with pytest.raises(ValueError):
        _normalize_newsdom_base_url("https://169.254.169.254")


def test_userinfo_is_rejected(newsdom_allowlist):
    with pytest.raises(ValueError):
        _normalize_newsdom_base_url("https://user:pass@newsdom.example.com")


def test_localhost_rejected_unless_local_providers_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_NEWSDOM_HOSTS", "newsdom")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_NEWSDOM_PROVIDERS", False)
    with pytest.raises(ValueError):
        _normalize_newsdom_base_url("http://localhost:8000")


def test_docker_container_host_allowed_when_local_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_NEWSDOM_HOSTS", "newsdom")
    monkeypatch.setattr(settings, "ALLOW_LOCAL_NEWSDOM_PROVIDERS", True)
    normalized, hostname, port = _normalize_newsdom_base_url("http://newsdom:8000")
    assert hostname == "newsdom"
    assert port == 8000
    assert normalized == "http://newsdom:8000"


def test_empty_base_url_normalizes_to_none(newsdom_allowlist):
    assert _normalize_newsdom_base_url(None) == (None, None, None)
    assert _normalize_newsdom_base_url("") == (None, None, None)


@pytest.mark.asyncio
async def test_request_pdf_dom_rejects_empty_payload(newsdom_allowlist):
    with pytest.raises(NewsdomRequestError):
        await request_pdf_dom(
            base_url="https://newsdom.example.com",
            api_token=None,
            pdf_bytes=b"",
        )


@pytest.mark.asyncio
async def test_request_pdf_dom_rejects_payload_above_sidecar_contract_before_network(
    newsdom_allowlist,
):
    with pytest.raises(NewsdomPayloadTooLargeError):
        await request_pdf_dom(
            base_url="https://newsdom.example.com",
            api_token=None,
            pdf_bytes=b"%PDF-" + b"A" * NEWSDOM_MAX_PARSE_UPLOAD_BYTES,
        )


@pytest.mark.asyncio
async def test_request_pdf_dom_raises_config_error_without_base_url(newsdom_allowlist):
    with pytest.raises(NewsdomConfigurationError):
        await request_pdf_dom(
            base_url=None,
            api_token=None,
            pdf_bytes=b"%PDF-1.7",
        )


@pytest.mark.asyncio
async def test_request_pdf_dom_rejects_disallowed_host(newsdom_allowlist):
    with pytest.raises(ValueError) as excinfo:
        await request_pdf_dom(
            base_url="https://evil.example.com",
            api_token=None,
            pdf_bytes=b"%PDF-1.7",
        )
    assert str(excinfo.value) == NEWSDOM_BASE_URL_NOT_ALLOWED
