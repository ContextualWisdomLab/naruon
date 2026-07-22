"""Real live-account smoke test.

After seeding the ``NARUON_TEST_*{N}`` accounts into the DB, this connects each
configured protocol and asserts reachability:

    IMAP    login + SELECT INBOX
    POP3    STAT
    SMTP    EHLO + STARTTLS (or implicit-TLS EHLO on 465)
    CalDAV  PROPFIND
    CardDAV auto-discovery + PROPFIND

A protocol whose address (or CardDAV discovery) is unavailable is skipped
cleanly rather than failing. The whole check is gated behind an opt-in flag so
the normal unit CI never runs it:

    NARUON_LIVE_SMOKE=1   (or LIVE_BASE_URL set)

Run directly on the mail-egress runner:

    python3 backend/tests/live/mail_smoke_test.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.live.seed_test_accounts import (  # noqa: E402
    LiveAccountSpec,
    parse_test_accounts,
)

logger = logging.getLogger("naruon.live.mail_smoke")

LIVE_FLAG_ENV = "NARUON_LIVE_SMOKE"


def live_smoke_enabled(environ: dict[str, str] | None = None) -> bool:
    environ = environ if environ is not None else dict(os.environ)
    return bool(
        environ.get(LIVE_FLAG_ENV)
        or environ.get("LIVE_BASE_URL")
        # Presence of account-1 secrets implies an intentional live run.
        or environ.get("NARUON_TEST_EMAIL1")
    )


@dataclass
class ProtocolResult:
    protocol: str
    account_index: int
    reachable: bool
    skipped: bool = False
    detail: str = ""


@dataclass
class SmokeReport:
    results: list[ProtocolResult] = field(default_factory=list)

    @property
    def reached(self) -> list[ProtocolResult]:
        return [r for r in self.results if r.reachable and not r.skipped]

    @property
    def failures(self) -> list[ProtocolResult]:
        return [r for r in self.results if not r.reachable and not r.skipped]

    @property
    def skipped(self) -> list[ProtocolResult]:
        return [r for r in self.results if r.skipped]


async def _check_imap(spec: LiveAccountSpec) -> ProtocolResult:
    from services.email_client import (
        connect_validated_imap_socket,
        validate_imap_destination,
    )
    from services.imap_worker import _build_pinned_imap_client

    assert spec.imap is not None
    destination = validate_imap_destination(spec.imap.host, spec.imap.port)
    ssl_context = ssl.create_default_context()
    imap_socket = await connect_validated_imap_socket(destination)
    try:
        client = _build_pinned_imap_client(destination, imap_socket, ssl_context)
        try:
            await asyncio.wait_for(client.wait_hello_from_server(), timeout=30)
            if not spec.email or not spec.password:
                return ProtocolResult("imap", spec.index, False, detail="missing creds")
            resp, _ = await client.login(spec.email, spec.password)
            if resp != "OK":
                return ProtocolResult("imap", spec.index, False, detail="login failed")
            select_resp, _ = await client.select("INBOX")
            ok = select_resp == "OK"
            return ProtocolResult(
                "imap", spec.index, ok, detail="select ok" if ok else "select failed"
            )
        finally:
            try:
                await client.logout()
            except Exception:  # noqa: BLE001
                pass
    finally:
        imap_socket.close()


async def _check_pop3(spec: LiveAccountSpec) -> ProtocolResult:
    import poplib

    from services.email_client import validate_pop3_destination

    assert spec.pop3 is not None
    host, port = validate_pop3_destination(spec.pop3.host, spec.pop3.port)

    def _stat() -> tuple[int, int]:
        client = poplib.POP3_SSL(host, port, timeout=30)
        try:
            client.user(spec.email)
            client.pass_(spec.password or "")
            return client.stat()
        finally:
            try:
                client.quit()
            except Exception:  # noqa: BLE001
                pass

    if not spec.email or not spec.password:
        return ProtocolResult("pop3", spec.index, False, detail="missing creds")
    count, _size = await asyncio.to_thread(_stat)
    return ProtocolResult("pop3", spec.index, True, detail=f"stat count={count}")


async def _check_smtp(spec: LiveAccountSpec) -> ProtocolResult:
    import aiosmtplib

    from services.email_client import validate_smtp_destination
    from services.net_defaults import SMTP_IMPLICIT_TLS_PORT

    assert spec.smtp is not None
    destination = validate_smtp_destination(spec.smtp.host, spec.smtp.port)
    implicit_tls = destination.port == SMTP_IMPLICIT_TLS_PORT
    client = aiosmtplib.SMTP(
        hostname=destination.hostname,
        port=destination.port,
        use_tls=implicit_tls,
        timeout=30,
    )
    try:
        await client.connect()
        await client.ehlo()
        if not implicit_tls and client.supports_extension("starttls"):
            await client.starttls()
            await client.ehlo()
        return ProtocolResult(
            "smtp",
            spec.index,
            True,
            detail="implicit-tls ehlo" if implicit_tls else "starttls ehlo",
        )
    finally:
        try:
            await client.quit()
        except Exception:  # noqa: BLE001
            pass


async def _check_caldav(spec: LiveAccountSpec) -> ProtocolResult:
    import httpx

    assert spec.caldav_url is not None
    headers = {"Depth": "0", "Content-Type": "application/xml; charset=utf-8"}
    auth = (spec.email, spec.password or "") if spec.email else None
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/>'
        "</D:prop></D:propfind>"
    ).encode("utf-8")
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        response = await client.request(
            "PROPFIND", spec.caldav_url, headers=headers, content=body, auth=auth
        )
    reachable = response.status_code in {200, 207, 401, 403}
    return ProtocolResult(
        "caldav", spec.index, reachable, detail=f"status={response.status_code}"
    )


async def _check_carddav(spec: LiveAccountSpec) -> ProtocolResult:
    from services.carddav_client import CardDavClient
    from services.carddav_discovery import discover_carddav_base_url

    base_url = spec.carddav_url
    if base_url is None:
        base_url = await discover_carddav_base_url(spec.email)
    if base_url is None:
        # CardDAV was configured (explicit address or discovery requested) but
        # no endpoint resolved. That is a failure, not a skip -- skipping here
        # would let the run report CardDAV coverage it never exercised.
        return ProtocolResult(
            "carddav", spec.index, False, skipped=False, detail="no discovery"
        )
    client = CardDavClient(
        base_url,
        username=spec.email or None,
        password=spec.password,
    )
    probe = await client.list_address_books()
    return ProtocolResult(
        "carddav",
        spec.index,
        probe.reachable,
        detail=f"status={probe.status_code}",
    )


_CHECKS = {
    "imap": (_check_imap, lambda s: s.imap is not None),
    "pop3": (_check_pop3, lambda s: s.pop3 is not None),
    "smtp": (_check_smtp, lambda s: s.smtp is not None),
    "caldav": (_check_caldav, lambda s: s.caldav_url is not None),
    "carddav": (
        _check_carddav,
        lambda s: s.carddav_url is not None or s.carddav_needs_discovery,
    ),
}


async def run_smoke(environ: dict[str, str] | None = None) -> SmokeReport:
    environ = environ if environ is not None else dict(os.environ)
    specs = parse_test_accounts(environ)
    report = SmokeReport()

    for spec in specs:
        for protocol, (check, is_configured) in _CHECKS.items():
            if not is_configured(spec):
                continue
            try:
                result = await check(spec)
            except Exception as exc:  # noqa: BLE001 - report, do not crash the run
                result = ProtocolResult(
                    protocol,
                    spec.index,
                    False,
                    detail=f"error: {type(exc).__name__}",
                )
            report.results.append(result)
    return report


class SmokeError(RuntimeError):
    """A seeding/verification failure that must fail the smoke run closed."""


async def seed_and_smoke(environ: dict[str, str] | None = None) -> SmokeReport:
    """Seed the accounts, then run the smoke checks against the live providers.

    Fails closed: a seed exception, an empty seed (no accounts / no protocols),
    or a required CardDAV discovery that produced no endpoint raises
    ``SmokeError`` instead of yielding a green run that proved nothing about the
    DB-backed path.
    """
    from tests.live.seed_test_accounts import seed_test_accounts

    environ = environ if environ is not None else dict(os.environ)
    try:
        summaries = await seed_test_accounts(environ)
    except Exception as exc:  # noqa: BLE001 - surface as a hard smoke failure
        raise SmokeError(f"seed failed: {type(exc).__name__}: {exc}") from exc

    if not summaries:
        raise SmokeError(
            "no NARUON_TEST_EMAIL{N} accounts were seeded; nothing to verify."
        )
    seeded_protocols = sum(len(summary.get("protocols") or []) for summary in summaries)
    if seeded_protocols == 0:
        raise SmokeError("seeding produced no configured protocols; check the secrets.")
    discovery_failures = [
        summary["user_id"]
        for summary in summaries
        if summary.get("carddav_discovery_failed")
    ]
    if discovery_failures:
        raise SmokeError(
            "required CardDAV discovery found no endpoint for: "
            + ", ".join(str(user_id) for user_id in discovery_failures)
        )
    return await run_smoke(environ)


def main() -> int:
    logging.basicConfig(level="INFO")
    if not live_smoke_enabled():
        print("Live smoke disabled (set NARUON_LIVE_SMOKE=1 to run). Nothing to do.")
        return 0

    try:
        report = asyncio.run(seed_and_smoke())
    except SmokeError as exc:
        print(f"Mail smoke test FAILED: {exc}")
        return 1

    for result in report.results:
        state = "SKIP" if result.skipped else ("OK" if result.reachable else "FAIL")
        print(
            f"[{state}] account={result.account_index} "
            f"{result.protocol}: {result.detail}"
        )

    if report.failures:
        print(f"Mail smoke test FAILED: {len(report.failures)} unreachable protocol(s)")
        return 1
    if not report.reached:
        # Every configured protocol was skipped -- nothing was actually
        # exercised, so this is not a pass.
        print("Mail smoke test FAILED: no protocol was reachable-tested.")
        return 1
    print(
        f"Mail smoke test passed "
        f"({len(report.reached)} reachable, {len(report.skipped)} skipped)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
