import pytest
from pydantic import SecretStr
from cryptography.fernet import Fernet
from db.models import get_encryption_keyring
from core.runtime_secrets import EncryptionKeyRing


def test_get_encryption_keyring_basic(monkeypatch):
    from core.config import settings

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", SecretStr(key))
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_ID", "primary")
    monkeypatch.setattr(settings, "ENCRYPTION_PREVIOUS_KEYS", None)

    keyring = get_encryption_keyring()
    assert isinstance(keyring, EncryptionKeyRing)
    assert keyring.active_key.key_id == "primary"


def test_get_encryption_keyring_with_previous_keys(monkeypatch):
    from core.config import settings

    key1 = Fernet.generate_key().decode("utf-8")
    key2 = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", SecretStr(key1))
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_ID", "new_primary")
    monkeypatch.setattr(settings, "ENCRYPTION_PREVIOUS_KEYS", SecretStr(f"old={key2}"))

    keyring = get_encryption_keyring()
    assert isinstance(keyring, EncryptionKeyRing)
    assert keyring.active_key.key_id == "new_primary"
    assert len(keyring.previous_keys) == 1
    assert keyring.previous_keys[0].key_id == "old"


def test_get_encryption_keyring_missing_key(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", None)
    monkeypatch.setattr(settings, "ENCRYPTION_PREVIOUS_KEYS", None)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        get_encryption_keyring()
