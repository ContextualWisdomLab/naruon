"""Focused regression tests for canonical origin rendering."""

from core.config import canonical_origin


def test_canonical_origin_http_default_port():
    """Omit HTTP's default port while normalizing scheme and host casing."""
    assert canonical_origin("http", "example.com", 80) == "http://example.com"
    assert canonical_origin("HTTP", "example.com", 80) == "http://example.com"
    assert canonical_origin("http", "EXAMPLE.COM", 80) == "http://example.com"


def test_canonical_origin_https_default_port():
    """Omit HTTPS's default port."""
    assert canonical_origin("https", "example.com", 443) == "https://example.com"


def test_canonical_origin_custom_port():
    """Preserve explicit non-default HTTP and HTTPS ports."""
    assert canonical_origin("http", "example.com", 8080) == "http://example.com:8080"
    assert canonical_origin("https", "example.com", 8443) == "https://example.com:8443"


def test_canonical_origin_none_port():
    """Render an origin without a port when the caller supplies none."""
    assert canonical_origin("http", "example.com", None) == "http://example.com"
    assert canonical_origin("https", "example.com", None) == "https://example.com"


def test_canonical_origin_ipv6_host():
    """Bracket IPv6 hosts exactly once and preserve non-default ports."""
    assert canonical_origin("http", "2001:db8::1", 80) == "http://[2001:db8::1]"
    assert canonical_origin("http", "[2001:db8::1]", 80) == "http://[2001:db8::1]"
    assert canonical_origin("https", "2001:db8::1", 443) == "https://[2001:db8::1]"
    assert canonical_origin("http", "2001:db8::1", 8080) == "http://[2001:db8::1]:8080"


def test_canonical_origin_other_schemes():
    """Non-HTTP schemes retain explicit ports and omit absent ports."""
    assert canonical_origin("ws", "example.com", 80) == "ws://example.com:80"
    assert canonical_origin("wss", "example.com", 443) == "wss://example.com:443"
    assert canonical_origin("ftp", "example.com", 21) == "ftp://example.com:21"
    assert canonical_origin("ws", "example.com", None) == "ws://example.com"
