"""JWKS refresh on unknown kid: key rotation must not require a restart."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event

import jwt as pyjwt
import pytest

from api import auth as auth_module


class FakeKey:
    def __init__(self, key_id: str):
        self.key_id = key_id
        self.key = f"key-material-{key_id}"


@pytest.fixture(autouse=True)
def _isolated_jwks_state(monkeypatch):
    monkeypatch.setattr(auth_module, "_cached_oidc_signing_keys", ())
    monkeypatch.setattr(
        auth_module, "_last_unknown_kid_refresh_monotonic", float("-inf")
    )
    yield


def _wire(monkeypatch, *, cached, fetched, token_kid, accept_kid):
    monkeypatch.setattr(auth_module, "_cached_oidc_signing_keys", tuple(cached))
    fetch_calls = []

    def fake_preload():
        fetch_calls.append(True)
        auth_module._cached_oidc_signing_keys = tuple(fetched)

    monkeypatch.setattr(auth_module, "preload_oidc_jwks", fake_preload)
    monkeypatch.setattr(
        auth_module.jwt,
        "get_unverified_header",
        lambda token: {"alg": "RS256", "kid": token_kid},
    )

    def fake_decode(token, key, algorithms, audience, issuer, options):
        if key == f"key-material-{accept_kid}":
            return {"sub": "user-1"}
        raise pyjwt.PyJWTError("signature mismatch")

    monkeypatch.setattr(auth_module.jwt, "decode", fake_decode)
    return fetch_calls


def test_unknown_kid_triggers_one_refresh_and_recovers(monkeypatch):
    fetch_calls = _wire(
        monkeypatch,
        cached=[FakeKey("old-kid")],
        fetched=[FakeKey("rotated-kid")],
        token_kid="rotated-kid",
        accept_kid="rotated-kid",
    )

    payload = auth_module._decode_cached_oidc_session_payload("token")

    assert payload == {"sub": "user-1"}
    assert len(fetch_calls) == 1


def test_empty_cache_refreshes_instead_of_failing_closed_forever(monkeypatch):
    fetch_calls = _wire(
        monkeypatch,
        cached=[],
        fetched=[FakeKey("fresh-kid")],
        token_kid="fresh-kid",
        accept_kid="fresh-kid",
    )

    payload = auth_module._decode_cached_oidc_session_payload("token")

    assert payload == {"sub": "user-1"}
    assert len(fetch_calls) == 1


def test_refresh_is_rate_limited_against_kid_spray(monkeypatch):
    fetch_calls = _wire(
        monkeypatch,
        cached=[FakeKey("old-kid")],
        fetched=[FakeKey("old-kid")],
        token_kid="bogus-kid",
        accept_kid="never",
    )

    for _ in range(5):
        with pytest.raises(Exception) as first:
            auth_module._decode_cached_oidc_session_payload("token")
        assert getattr(first.value, "status_code", None) == 401

    assert len(fetch_calls) == 1


def test_concurrent_unknown_kids_share_one_blocking_refresh(monkeypatch):
    monkeypatch.setattr(
        auth_module, "_cached_oidc_signing_keys", (FakeKey("old-kid"),)
    )
    monkeypatch.setattr(auth_module.time, "monotonic", lambda: 100.0)
    preload_started = Event()
    release_preload = Event()
    fetch_calls: list[bool] = []

    def blocking_preload():
        fetch_calls.append(True)
        preload_started.set()
        assert release_preload.wait(timeout=2)
        auth_module._cached_oidc_signing_keys = (FakeKey("rotated-kid"),)

    monkeypatch.setattr(auth_module, "preload_oidc_jwks", blocking_preload)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            auth_module._refresh_jwks_for_unknown_kid, "rotated-kid"
        )
        assert preload_started.wait(timeout=1)
        second = executor.submit(
            auth_module._refresh_jwks_for_unknown_kid, "rotated-kid"
        )
        try:
            with pytest.raises(FutureTimeoutError):
                second.result(timeout=0.05)
        finally:
            release_preload.set()

        assert first.result(timeout=1) is True
        assert second.result(timeout=1) is False

    assert fetch_calls == [True]


def test_known_kid_with_bad_signature_never_refreshes(monkeypatch):
    fetch_calls = _wire(
        monkeypatch,
        cached=[FakeKey("known-kid")],
        fetched=[FakeKey("known-kid")],
        token_kid="known-kid",
        accept_kid="never",
    )

    with pytest.raises(Exception) as excinfo:
        auth_module._decode_cached_oidc_session_payload("token")

    assert getattr(excinfo.value, "status_code", None) == 401
    assert fetch_calls == []
