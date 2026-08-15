from cryptography.fernet import Fernet
import pytest
from pydantic import SecretStr

from core.runtime_secrets import EncryptionKeyRing
from db.models import get_encryption_keyring


def test_get_encryption_keyring_basic(monkeypatch):
    """Build the active database encryption keyring from runtime settings."""
    from core.config import settings

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", SecretStr(key))
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_ID", "primary")
    monkeypatch.setattr(settings, "ENCRYPTION_PREVIOUS_KEYS", None)

    keyring = get_encryption_keyring()

    assert isinstance(keyring, EncryptionKeyRing)
    assert keyring.active_key.key_id == "primary"
    plaintext = b"active-key-material-proof"
    encrypted = Fernet(key.encode("utf-8")).encrypt(plaintext)
    assert keyring.active_key.fernet.decrypt(encrypted) == plaintext


def test_get_encryption_keyring_with_previous_keys(monkeypatch):
    """Preserve prior decryption keys alongside a newly active key."""
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

    active_plaintext = b"active-key-material-proof"
    active_encrypted = Fernet(key1.encode("utf-8")).encrypt(active_plaintext)
    assert keyring.active_key.fernet.decrypt(active_encrypted) == active_plaintext

    previous_plaintext = b"previous-key-material-proof"
    previous_encrypted = Fernet(key2.encode("utf-8")).encrypt(previous_plaintext)
    assert keyring.previous_keys[0].fernet.decrypt(previous_encrypted) == previous_plaintext


@pytest.mark.parametrize(
    "invalid_key",
    [None, SecretStr(""), SecretStr("   ")],
)
def test_get_encryption_keyring_missing_key(monkeypatch, invalid_key):
    """Fail closed when the database encryption key is absent or blank."""
    from core.config import settings

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", invalid_key)
    monkeypatch.setattr(settings, "ENCRYPTION_PREVIOUS_KEYS", None)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        get_encryption_keyring()
