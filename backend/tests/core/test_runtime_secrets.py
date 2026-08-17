import pytest
from cryptography.fernet import Fernet
from core.runtime_secrets import build_encryption_keyring, DEFAULT_ENCRYPTION_KEY_ID


def test_build_encryption_keyring_success():
    active_key = Fernet.generate_key().decode("utf-8")
    keyring = build_encryption_keyring(active_key)
    assert keyring.active_key.key_id == DEFAULT_ENCRYPTION_KEY_ID
    assert keyring.active_key.fernet is not None
    assert len(keyring.previous_keys) == 0


def test_build_encryption_keyring_missing_key():
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        build_encryption_keyring(None)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        build_encryption_keyring("   ")


def test_build_encryption_keyring_invalid_key():
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY must be a valid Fernet key"):
        build_encryption_keyring("invalid_key_value")


def test_build_encryption_keyring_with_previous_keys():
    active_key = Fernet.generate_key().decode("utf-8")
    prev_key1 = Fernet.generate_key().decode("utf-8")
    prev_key2 = Fernet.generate_key().decode("utf-8")

    previous_keys_str = f"old1={prev_key1},old2={prev_key2}"

    keyring = build_encryption_keyring(
        active_key_value=active_key, previous_keys_value=previous_keys_str
    )

    assert keyring.active_key.key_id == DEFAULT_ENCRYPTION_KEY_ID
    assert len(keyring.previous_keys) == 2
    assert keyring.previous_keys[0].key_id == "old1"
    assert keyring.previous_keys[1].key_id == "old2"


def test_build_encryption_keyring_duplicate_key_id():
    active_key = Fernet.generate_key().decode("utf-8")
    prev_key = Fernet.generate_key().decode("utf-8")

    # Trying to use DEFAULT_ENCRYPTION_KEY_ID ('primary') in previous_keys
    previous_keys_str = f"{DEFAULT_ENCRYPTION_KEY_ID}={prev_key}"

    with pytest.raises(
        RuntimeError, match="ENCRYPTION_PREVIOUS_KEYS must not repeat key identifiers"
    ):
        build_encryption_keyring(
            active_key_value=active_key, previous_keys_value=previous_keys_str
        )


def test_build_encryption_keyring_invalid_previous_key_format():
    active_key = Fernet.generate_key().decode("utf-8")

    # Missing key_id
    with pytest.raises(
        RuntimeError,
        match="ENCRYPTION_PREVIOUS_KEYS entries must use key_id=fernet_key",
    ):
        build_encryption_keyring(
            active_key_value=active_key, previous_keys_value="=some_value"
        )

    # Missing separator
    with pytest.raises(
        RuntimeError,
        match="ENCRYPTION_PREVIOUS_KEYS entries must use key_id=fernet_key",
    ):
        build_encryption_keyring(
            active_key_value=active_key, previous_keys_value="some_value"
        )
