import pytest

from services.net_defaults import (
    SMTP_IMPLICIT_TLS_PORT,
    infer_address_port,
    infer_port,
    split_host_port,
)


def test_infer_default_ports_per_protocol():
    assert infer_port("imap") == 993
    assert infer_port("pop3") == 995
    assert infer_port("smtp") == 587
    assert infer_port("caldav") == 443
    assert infer_port("carddav") == 443
    assert infer_port("webdav") == 443


def test_infer_port_is_case_insensitive():
    assert infer_port("IMAP") == 993
    assert infer_port("  CardDAV ") == 443


def test_smtp_implicit_tls_selects_465():
    assert infer_port("smtp", implicit_tls=True) == SMTP_IMPLICIT_TLS_PORT
    # implicit_tls only affects smtp defaults, not other protocols.
    assert infer_port("imap", implicit_tls=True) == 993


def test_explicit_port_always_wins():
    assert infer_port("imap", 143) == 143
    assert infer_port("smtp", 2525) == 2525
    # An explicit port wins even over the implicit-TLS default.
    assert infer_port("smtp", 587, implicit_tls=True) == 587


def test_non_positive_provided_port_falls_back_to_default():
    assert infer_port("imap", 0) == 993
    assert infer_port("pop3", -1) == 995


def test_unsupported_protocol_raises():
    with pytest.raises(ValueError):
        infer_port("ftp")


def test_out_of_range_port_raises():
    with pytest.raises(ValueError):
        infer_port("imap", 70000)


def test_split_host_port_bare_host():
    assert split_host_port("imap.example.com") == ("imap.example.com", None)


def test_split_host_port_with_port():
    assert split_host_port("imap.example.com:143") == ("imap.example.com", 143)


def test_split_host_port_ipv6_literal_without_port():
    # A bare IPv6 literal (multiple colons) must not be mistaken for host:port.
    assert split_host_port("2001:db8::1") == ("2001:db8::1", None)


def test_split_host_port_bracketed_ipv6_with_port():
    assert split_host_port("[2001:db8::1]:993") == ("2001:db8::1", 993)


def test_split_host_port_bracketed_ipv6_without_port():
    assert split_host_port("[2001:db8::1]") == ("2001:db8::1", None)


def test_infer_address_port_fills_missing_port():
    assert infer_address_port("imap", "imap.example.com") == (
        "imap.example.com",
        993,
    )


def test_infer_address_port_preserves_explicit_port():
    assert infer_address_port("smtp", "smtp.example.com:2525") == (
        "smtp.example.com",
        2525,
    )
