"""Contract tests for the Postgres import-quota advisory-lock owner key.

PostgreSQL ``text`` / ``hashtext()`` cannot store a NUL (0x00) octet
(PostgreSQL Global Development Group, n.d.). The production helper must
therefore emit a NUL-free digest. The expected digest is computed here with
the standard-library hasher so a helper rewrite cannot silently change the
on-disk lock identity.
"""

from __future__ import annotations

import hashlib

from services.email_import_service import _owner_import_quota_lock_key

# Independent reference: SHA-256 of UTF-8 ``user_id + NUL + organization_id``.
_GOLDEN_TESTUSER_ORG_ACME = "3fbc5671f32a1608f88c1775c1008c26c53faaea0308b97c556eeceb2b4bb8d3"


def test_owner_import_quota_lock_key_matches_independent_sha256_digest() -> None:
    independent = hashlib.sha256(b"testuser\x00org-acme").hexdigest()
    assert independent == _GOLDEN_TESTUSER_ORG_ACME
    assert _owner_import_quota_lock_key("testuser", "org-acme") == independent
    assert "\x00" not in independent


def test_owner_import_quota_lock_key_is_nul_free_for_unicode_owners() -> None:
    user_id = "유저"
    organization_id = "org-서울"
    independent = hashlib.sha256(
        f"{user_id}\x00{organization_id}".encode("utf-8")
    ).hexdigest()
    actual = _owner_import_quota_lock_key(user_id, organization_id)
    assert actual == independent
    assert "\x00" not in actual
    assert len(actual) == 64
