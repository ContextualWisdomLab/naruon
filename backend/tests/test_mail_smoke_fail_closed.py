"""The live smoke must fail closed instead of passing vacuously.

Regression coverage for the confirmed false-green defects: a swallowed seed
error, an empty seed, and a required-but-undiscoverable CardDAV endpoint all
have to fail the run rather than report success.
"""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.live import mail_smoke_test as smoke  # noqa: E402
from tests.live import seed_test_accounts as seed  # noqa: E402


@pytest.mark.asyncio
async def test_seed_and_smoke_raises_on_seed_failure(monkeypatch):
    async def boom(_environ):
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(seed, "seed_test_accounts", boom)
    with pytest.raises(smoke.SmokeError):
        await smoke.seed_and_smoke({"NARUON_TEST_EMAIL1": "a@example.com"})


@pytest.mark.asyncio
async def test_seed_and_smoke_raises_when_nothing_seeded(monkeypatch):
    async def empty(_environ):
        return []

    monkeypatch.setattr(seed, "seed_test_accounts", empty)
    with pytest.raises(smoke.SmokeError):
        await smoke.seed_and_smoke({})


@pytest.mark.asyncio
async def test_seed_and_smoke_raises_when_no_protocols(monkeypatch):
    async def no_protocols(_environ):
        return [{"user_id": "naruon-test-1", "protocols": []}]

    monkeypatch.setattr(seed, "seed_test_accounts", no_protocols)
    with pytest.raises(smoke.SmokeError):
        await smoke.seed_and_smoke({"NARUON_TEST_EMAIL1": "a@example.com"})


@pytest.mark.asyncio
async def test_seed_and_smoke_raises_on_required_discovery_failure(monkeypatch):
    async def discovery_failed(_environ):
        return [
            {
                "user_id": "naruon-test-1",
                "protocols": ["imap"],
                "carddav_discovery_failed": True,
            }
        ]

    monkeypatch.setattr(seed, "seed_test_accounts", discovery_failed)
    with pytest.raises(smoke.SmokeError):
        await smoke.seed_and_smoke({"NARUON_TEST_EMAIL1": "a@example.com"})


@pytest.mark.asyncio
async def test_seed_and_smoke_runs_checks_when_seed_succeeds(monkeypatch):
    async def ok(_environ):
        return [{"user_id": "naruon-test-1", "protocols": ["imap"]}]

    sentinel = smoke.SmokeReport()

    async def fake_run(_environ):
        return sentinel

    monkeypatch.setattr(seed, "seed_test_accounts", ok)
    monkeypatch.setattr(smoke, "run_smoke", fake_run)
    report = await smoke.seed_and_smoke({"NARUON_TEST_EMAIL1": "a@example.com"})
    assert report is sentinel


@pytest.mark.asyncio
async def test_required_carddav_discovery_failure_is_a_failure_not_skip():
    from tests.live.seed_test_accounts import LiveAccountSpec

    spec = LiveAccountSpec(
        index=1,
        email="user@example.com",
        password="pw",
        carddav_needs_discovery=True,
    )

    async def no_discovery(_email):
        return None

    import tests.live.mail_smoke_test as module

    module_globals = module.__dict__
    original = module_globals.get("discover_carddav_base_url")
    # _check_carddav imports discover_carddav_base_url lazily; patch the source.
    import services.carddav_discovery as discovery

    orig_disc = discovery.discover_carddav_base_url
    discovery.discover_carddav_base_url = no_discovery
    try:
        result = await module._check_carddav(spec)
    finally:
        discovery.discover_carddav_base_url = orig_disc
        if original is not None:
            module_globals["discover_carddav_base_url"] = original

    assert result.skipped is False
    assert result.reachable is False
