import pytest
from services import email_client
from services.email_client import (
    IMAP_HOST_NOT_ALLOWED,
    IMAP_PORT_NOT_ALLOWED,
    POP3_HOST_NOT_ALLOWED,
    POP3_PORT_NOT_ALLOWED,
    validate_imap_host,
    validate_imap_port,
    validate_imap_destination,
    validate_pop3_host,
    validate_pop3_port,
    validate_pop3_destination
)
import socket


@pytest.fixture
def smtp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        yield sock
    finally:
        sock.close()


def test_validate_imap_host(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "imap.example.com")
    assert validate_imap_host("imap.example.com", resolve_host=False) == "imap.example.com"
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        validate_imap_host("bad.example.com", resolve_host=False)

def test_validate_imap_port(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_PORTS", "993, 143")
    assert validate_imap_port(993) == 993
    assert validate_imap_port(143) == 143
    with pytest.raises(ValueError, match=IMAP_PORT_NOT_ALLOWED):
        validate_imap_port(110)

def test_validate_imap_destination(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "imap.example.com")
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_PORTS", "993")
    host, port = validate_imap_destination("imap.example.com", 993, resolve_host=False)
    assert host == "imap.example.com"
    assert port == 993

def test_validate_pop3_host(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "pop3.example.com")
    assert validate_pop3_host("pop3.example.com", resolve_host=False) == "pop3.example.com"
    with pytest.raises(ValueError, match=POP3_HOST_NOT_ALLOWED):
        validate_pop3_host("bad.example.com", resolve_host=False)

def test_validate_pop3_port(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_PORTS", "995, 110")
    assert validate_pop3_port(995) == 995
    assert validate_pop3_port(110) == 110
    with pytest.raises(ValueError, match=POP3_PORT_NOT_ALLOWED):
        validate_pop3_port(993)

def test_validate_pop3_destination(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "pop3.example.com")
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_PORTS", "995")
    host, port = validate_pop3_destination("pop3.example.com", 995, resolve_host=False)
    assert host == "pop3.example.com"
    assert port == 995

def test_validate_imap_host_ip_literal(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "1.1.1.1")
    assert validate_imap_host("1.1.1.1", resolve_host=False) == "1.1.1.1"

    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "imap.example.com")
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        validate_imap_host("127.0.0.1", resolve_host=False)

    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        validate_imap_host("192.168.1.1", resolve_host=False)

def test_validate_pop3_host_ip_literal(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "1.1.1.1")
    assert validate_pop3_host("1.1.1.1", resolve_host=False) == "1.1.1.1"

    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "pop3.example.com")
    with pytest.raises(ValueError, match=POP3_HOST_NOT_ALLOWED):
        validate_pop3_host("127.0.0.1", resolve_host=False)

    with pytest.raises(ValueError, match=POP3_HOST_NOT_ALLOWED):
        validate_pop3_host("192.168.1.1", resolve_host=False)

def test_validate_imap_host_legacy_ip(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "*")
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        validate_imap_host("0x7f.0.0.1", resolve_host=False)

def test_validate_pop3_host_legacy_ip(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "*")
    with pytest.raises(ValueError, match=POP3_HOST_NOT_ALLOWED):
        validate_pop3_host("0x7f.0.0.1", resolve_host=False)

def test_validate_imap_host_resolve(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_HOSTS", "imap.example.com")
    def mock_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 993))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    assert validate_imap_host("imap.example.com", resolve_host=True) == "imap.example.com"

    def mock_getaddrinfo_private(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 993))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_private)
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        validate_imap_host("imap.example.com", resolve_host=True)

def test_validate_pop3_host_resolve(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_POP3_HOSTS", "pop3.example.com")
    def mock_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 995))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    assert validate_pop3_host("pop3.example.com", resolve_host=True) == "pop3.example.com"

    def mock_getaddrinfo_private(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 995))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_private)
    with pytest.raises(ValueError, match=POP3_HOST_NOT_ALLOWED):
        validate_pop3_host("pop3.example.com", resolve_host=True)

def test_parse_allowed_ports_invalid_and_non_egress(monkeypatch, caplog):
    monkeypatch.setattr(email_client.settings, "ALLOWED_IMAP_PORTS", "993, invalid, 25")
    with caplog.at_level(email_client.logging.WARNING):
        ports = email_client._parse_allowed_imap_ports()
        assert 993 in ports
        assert 25 not in ports
        assert "Ignoring invalid IMAP port policy entry" in caplog.text
        assert "Ignoring non-IMAP port policy entry" in caplog.text

def test_normalize_mail_host_empty_hostname(monkeypatch):
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._normalize_mail_host("http://", IMAP_HOST_NOT_ALLOWED)

def test_looks_like_ip_literal_ipv6():
    assert email_client._looks_like_ip_literal("2001:db8::1") is True

def test_is_legacy_numeric_ip_component_invalid():
    assert email_client._is_legacy_numeric_ip_component("") is False
    assert email_client._is_legacy_numeric_ip_component("0xg") is False

def test_resolve_all_public_mail_addresses_empty_result(monkeypatch):
    def mock_getaddrinfo(*args, **kwargs):
        return []
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._resolve_all_public_mail_addresses("imap.example.com", 993, IMAP_HOST_NOT_ALLOWED)

def test_resolve_all_public_mail_addresses_gaierror(monkeypatch):
    def mock_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("lookup failed")
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._resolve_all_public_mail_addresses("imap.example.com", 993, IMAP_HOST_NOT_ALLOWED)

def test_normalize_mail_host_empty_whitespace():
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._normalize_mail_host("   ", IMAP_HOST_NOT_ALLOWED)

def test_normalize_mail_host_invalid_chars():
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._normalize_mail_host("imap.example.com/path", IMAP_HOST_NOT_ALLOWED)

def test_normalize_mail_host_localhost():
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._normalize_mail_host("localhost", IMAP_HOST_NOT_ALLOWED)
    with pytest.raises(ValueError, match=IMAP_HOST_NOT_ALLOWED):
        email_client._normalize_mail_host("localhost.localdomain", IMAP_HOST_NOT_ALLOWED)

def test_validate_smtp_host_looks_like_ip_literal(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "*")
    with pytest.raises(ValueError, match=email_client.SMTP_HOST_NOT_ALLOWED):
        email_client.validate_smtp_host("0x7f.0.0.1", resolve_host=False)

def test_validate_smtp_destination_no_resolve(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "smtp.example.com")
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_PORTS", "587")
    dest = email_client.validate_smtp_destination("smtp.example.com", 587, resolve_host=False)
    assert dest.hostname == "smtp.example.com"
    assert dest.port == 587
    assert dest.family == socket.AF_UNSPEC
    assert dest.socktype == socket.SOCK_STREAM

def test_resolve_smtp_connect_address_empty(monkeypatch):
    monkeypatch.setattr(email_client, "_resolve_all_public_smtp_addresses", lambda host, port: [])
    with pytest.raises(ValueError, match=email_client.SMTP_HOST_NOT_ALLOWED):
        email_client._resolve_smtp_connect_address("smtp.example.com", 587)

def test_validate_pinned_smtp_sockaddr_empty():
    with pytest.raises(ValueError, match=email_client.SMTP_HOST_NOT_ALLOWED):
        email_client._validate_pinned_smtp_sockaddr(())

@pytest.mark.asyncio
async def test_connect_validated_smtp_socket_exception(monkeypatch):
    destination = email_client.ValidatedSmtpDestination(
        hostname="smtp.example.com",
        port=587,
        family=socket.AF_INET,
        socktype=socket.SOCK_STREAM,
        proto=6,
        sockaddr=("8.8.8.8", 587),
    )
    async def mock_sock_connect(*args, **kwargs):
        raise socket.error("connection refused")
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "sock_connect", mock_sock_connect)
    with pytest.raises(socket.error, match="connection refused"):
        await email_client._connect_validated_smtp_socket(destination)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_not_socket(monkeypatch):
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock="not-a-socket",
        use_tls=True
    )
    async def mock_super_create_connection(*args, **kwargs):
        return "super-result"
    monkeypatch.setattr(email_client.aiosmtplib.SMTP, "_create_connection", mock_super_create_connection)
    result = await client._create_connection(timeout=10.0)
    assert result == "super-result"

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_not_tls(monkeypatch, smtp_socket):
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=False
    )
    async def mock_super_create_connection(*args, **kwargs):
        sock.close()
        return "super-result"
    monkeypatch.setattr(email_client.aiosmtplib.SMTP, "_create_connection", mock_super_create_connection)
    result = await client._create_connection(timeout=10.0)
    assert result == "super-result"

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_connect_timeout(monkeypatch, smtp_socket):
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        raise email_client.asyncio.TimeoutError()
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))

    with pytest.raises(email_client.SMTPConnectTimeoutError, match="Timed out connecting to smtp.example.com"):
        await client._create_connection(timeout=10.0)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_connect_oserror(monkeypatch, smtp_socket):
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        raise OSError("network down")
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))

    with pytest.raises(email_client.SMTPConnectError, match="Error connecting to smtp.example.com: network down"):
        await client._create_connection(timeout=10.0)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_read_response_disconnected(monkeypatch, smtp_socket):
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        return ("transport", "protocol")
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))
    class MockLoop:
        async def create_connection(self, protocol_factory, *args, **kwargs):
            return ("transport", protocol_factory())
    monkeypatch.setattr(email_client.asyncio, "get_running_loop", lambda: MockLoop())

    def MockProtocol(*args, **kwargs):
        class InnerMockProtocol:
            async def read_response(self, timeout):
                raise email_client.SMTPServerDisconnected("disconnected")
        return InnerMockProtocol()
    monkeypatch.setattr(email_client, "SMTPProtocol", MockProtocol)

    with pytest.raises(email_client.SMTPConnectError, match="Error connecting to smtp.example.com: disconnected"):
        await client._create_connection(timeout=10.0)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_read_response_timeout(monkeypatch, smtp_socket):
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        return ("transport", "protocol")
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))
    class MockLoop:
        async def create_connection(self, protocol_factory, *args, **kwargs):
            return ("transport", protocol_factory())
    monkeypatch.setattr(email_client.asyncio, "get_running_loop", lambda: MockLoop())

    def MockProtocol(*args, **kwargs):
        class InnerMockProtocol:
            async def read_response(self, timeout):
                raise email_client.SMTPTimeoutError("timeout")
        return InnerMockProtocol()
    monkeypatch.setattr(email_client, "SMTPProtocol", MockProtocol)

    with pytest.raises(email_client.SMTPConnectTimeoutError, match="Timed out waiting for server ready message"):
        await client._create_connection(timeout=10.0)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_read_response_not_ready(monkeypatch, smtp_socket):
    from aiosmtplib.response import SMTPResponse
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        return ("transport", "protocol")
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))
    class MockLoop:
        async def create_connection(self, protocol_factory, *args, **kwargs):
            return ("transport", protocol_factory())
    monkeypatch.setattr(email_client.asyncio, "get_running_loop", lambda: MockLoop())

    def MockProtocol(*args, **kwargs):
        class InnerMockProtocol:
            async def read_response(self, timeout):
                return SMTPResponse(code=500, message="Service unavailable")
        return InnerMockProtocol()
    monkeypatch.setattr(email_client, "SMTPProtocol", MockProtocol)

    with pytest.raises(email_client.SMTPConnectResponseError, match="500"):
        await client._create_connection(timeout=10.0)

@pytest.mark.asyncio
async def test_pinned_implicit_tls_smtp_read_response_success(monkeypatch, smtp_socket):
    from aiosmtplib.response import SMTPResponse
    sock = smtp_socket
    client = email_client._PinnedImplicitTlsSMTP(
        tls_server_hostname="smtp.example.com",
        hostname=None,
        port=None,
        sock=sock,
        use_tls=True
    )
    async def mock_wait_for(coro, timeout):
        try:
            await coro
        except TypeError:
            # The monkeypatched connection path intentionally passes None.
            del coro
        return ("transport", "protocol")
    monkeypatch.setattr(email_client.asyncio, "wait_for", mock_wait_for)
    monkeypatch.setattr(client, "_get_tls_context", lambda: None)
    monkeypatch.setattr(email_client.asyncio.get_running_loop(), "create_connection", lambda *args, **kwargs: mock_wait_for(None, None))
    class MockLoop:
        async def create_connection(self, protocol_factory, *args, **kwargs):
            return ("transport", protocol_factory())
    monkeypatch.setattr(email_client.asyncio, "get_running_loop", lambda: MockLoop())

    def MockProtocol(*args, **kwargs):
        class InnerMockProtocol:
            async def read_response(self, timeout):
                return SMTPResponse(code=email_client.SMTPStatus.ready, message="Ready")
        return InnerMockProtocol()
    monkeypatch.setattr(email_client, "SMTPProtocol", MockProtocol)

    response = await client._create_connection(timeout=10.0)
    assert response.code == email_client.SMTPStatus.ready

def test_validate_smtp_host_ip_literal(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "1.1.1.1")
    assert email_client.validate_smtp_host("1.1.1.1", resolve_host=False) == "1.1.1.1"

def test_build_smtp_client_non_465(smtp_socket):
    sock = smtp_socket
    client = email_client._build_smtp_client(smtp_socket=sock, smtp_server="smtp.example.com", smtp_port=587)
    assert not client.use_tls
    assert client.sock == sock
    sock.close()

@pytest.mark.asyncio
async def test_send_email_general_exception(monkeypatch):
    async def mock_connect(*args, **kwargs):
        raise TypeError("Something went wrong")
    monkeypatch.setattr(email_client, "_connect_validated_smtp_socket", mock_connect)
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_PORTS", "587")
    def mock_resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 587))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_resolve)
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "smtp.example.com")

    params = email_client.EmailMessageParams(
        to_address="test@example.com",
        subject="Test",
        body="Body",
    )
    smtp_config = email_client.SmtpConfig(
        smtp_server="smtp.example.com",
        smtp_port=587,
    )
    with pytest.raises(Exception, match="Failed to send email: Something went wrong"):
        await email_client.send_email(params, smtp_config)

@pytest.mark.asyncio
async def test_send_email_value_error_re_raised(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "smtp.example.com")
    def mock_validate(*args, **kwargs):
        raise ValueError("SMTP_HOST_NOT_ALLOWED")
    monkeypatch.setattr(email_client, "validate_smtp_destination", mock_validate)

    params = email_client.EmailMessageParams(
        to_address="test@example.com",
        subject="Test",
        body="Body",
    )
    smtp_config = email_client.SmtpConfig(
        smtp_server="smtp.example.com",
        smtp_port=587,
    )
    with pytest.raises(ValueError, match="SMTP_HOST_NOT_ALLOWED"):
        await email_client.send_email(params, smtp_config)

@pytest.mark.asyncio
async def test_send_email_value_error_re_raised_correctly(monkeypatch):
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_HOSTS", "smtp.example.com")
    monkeypatch.setattr(email_client.settings, "ALLOWED_SMTP_PORTS", "587")

    async def mock_connect(*args, **kwargs):
        raise ValueError("SMTP_HOST_NOT_ALLOWED_MOCK")
    monkeypatch.setattr(email_client, "_connect_validated_smtp_socket", mock_connect)

    import socket
    def mock_resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 587))]
    monkeypatch.setattr(email_client.socket, "getaddrinfo", mock_resolve)

    params = email_client.EmailMessageParams(
        to_address="test@example.com",
        subject="Test",
        body="Body",
    )
    smtp_config = email_client.SmtpConfig(
        smtp_server="smtp.example.com",
        smtp_port=587,
    )
    with pytest.raises(ValueError, match="SMTP_HOST_NOT_ALLOWED_MOCK"):
        await email_client.send_email(params, smtp_config)
