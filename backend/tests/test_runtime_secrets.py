import math

import pytest
from core.runtime_secrets import (
    _KNOWN_PUBLIC_AUTH_SESSION_HMAC_SECRETS,
    _LOW_ENTROPY_PLACEHOLDER_TERMS,
    _character_class_count,
    _shannon_entropy_bits,
    validate_auth_session_hmac_secret_value,
)


def test_validate_auth_session_hmac_secret_value_valid():
    validate_auth_session_hmac_secret_value("thisisaverylongandsecurestring123!")


def test_validate_auth_session_hmac_secret_value_empty():
    with pytest.raises(
        ValueError,
        match="AUTH_SESSION_HMAC_SECRET must be at least 32 bytes",
    ):
        validate_auth_session_hmac_secret_value("")
    with pytest.raises(
        ValueError,
        match="AUTH_SESSION_HMAC_SECRET must be at least 32 bytes",
    ):
        validate_auth_session_hmac_secret_value(None)


def test_validate_auth_session_hmac_secret_value_short():
    with pytest.raises(
        ValueError,
        match="AUTH_SESSION_HMAC_SECRET must be at least 32 bytes",
    ):
        validate_auth_session_hmac_secret_value("short")
    with pytest.raises(
        ValueError,
        match="AUTH_SESSION_HMAC_SECRET must be at least 32 bytes",
    ):
        validate_auth_session_hmac_secret_value("a" * 31)


def test_validate_auth_session_hmac_secret_value_repeated():
    with pytest.raises(ValueError, match="must not be a repeated character"):
        validate_auth_session_hmac_secret_value("a" * 32)
    with pytest.raises(ValueError, match="must not be a repeated character"):
        validate_auth_session_hmac_secret_value("1" * 64)


def test_validate_auth_session_hmac_secret_value_rejects_low_diversity():
    with pytest.raises(ValueError, match="at least 12 distinct characters"):
        validate_auth_session_hmac_secret_value("abcabcabcabcabcabcabcabcabcabcab")
    with pytest.raises(ValueError, match="at least three character classes"):
        validate_auth_session_hmac_secret_value("abcdefghijklmnopqrstuvwxyzabcdef")
    with pytest.raises(ValueError, match="at least 128 bits of estimated entropy"):
        validate_auth_session_hmac_secret_value("aaaaaaaaaaaaaaaaaaaaABC123!@#xyz")


def test_validate_auth_session_hmac_secret_value_public_fixture():
    for public_fixture in _KNOWN_PUBLIC_AUTH_SESSION_HMAC_SECRETS:
        with pytest.raises(ValueError, match="must not use a public fixture value"):
            validate_auth_session_hmac_secret_value(public_fixture)


def test_validate_auth_session_hmac_secret_value_placeholder():
    for term in _LOW_ENTROPY_PLACEHOLDER_TERMS:
        with pytest.raises(ValueError, match="must not contain placeholder terms"):
            validate_auth_session_hmac_secret_value(
                f"this_is_a_sufficiently_long_prefix_for_testing_purposes_{term}"
            )


def test_validate_auth_session_hmac_secret_value_rejects_strix_fixture():
    with pytest.raises(ValueError, match="placeholder terms"):
        validate_auth_session_hmac_secret_value("NaRuOnSeCrEtToKeN1234567890abcdef")


def test_validate_auth_session_hmac_secret_value_accepts_multibyte_byte_length():
    secret = "가ABCDEFGHIJKLMNOabcdefghij1234!"

    assert len(secret) < 32
    assert len(secret.encode("utf-8")) >= 32

    validate_auth_session_hmac_secret_value(secret)


def test_validate_auth_session_hmac_secret_value_multibyte_length():
    with pytest.raises(ValueError, match="must be at least 32 bytes"):
        validate_auth_session_hmac_secret_value("가나다라마바사아자차")

    with pytest.raises(ValueError, match="at least three character classes"):
        validate_auth_session_hmac_secret_value("가나다라마바사아자차카타파하")


def test_character_class_count():
    assert _character_class_count("alllower") == 1
    assert _character_class_count("ALLUPPER") == 1
    assert _character_class_count("12345678") == 1
    assert _character_class_count("!@#$%^&*") == 1

    assert _character_class_count("LowerAndUpper") == 2
    assert _character_class_count("lower123") == 2
    assert _character_class_count("UPPER123") == 2
    assert _character_class_count("lower!@#") == 2

    assert _character_class_count("LowerAndUpper123") == 3
    assert _character_class_count("LowerAndUpper!@#") == 3

    assert _character_class_count("All4Classes123!@#") == 4
    assert _character_class_count("aaAA11!!") == 4

    assert _character_class_count("") == 0


def test_shannon_entropy_bits():
    assert _shannon_entropy_bits("") == 0.0

    assert _shannon_entropy_bits("a") == 0.0
    assert _shannon_entropy_bits("aaaaa") == 0.0

    assert _shannon_entropy_bits("ab") == 2.0
    assert _shannon_entropy_bits("abab") == 4.0

    assert math.isclose(_shannon_entropy_bits("aab"), 3 * math.log2(3) - 2)
    assert math.isclose(_shannon_entropy_bits("abcd"), 8.0)
    assert math.isclose(_shannon_entropy_bits("abc"), 4.754887502163468)
    assert math.isclose(_shannon_entropy_bits("abcabc"), 9.509775004326936)


def test_key_for_id_not_found():
    from core.runtime_secrets import EncryptionKeyRing, RuntimeEncryptionKey
    from cryptography.fernet import Fernet

    fernet = Fernet(Fernet.generate_key())
    key1 = RuntimeEncryptionKey(key_id="test1", fernet=fernet)

    secrets = EncryptionKeyRing(active_key=key1, previous_keys=())

    assert secrets.key_for_id("nonexistent") is None


def test_validate_encryption_key_id_invalid():
    from core.runtime_secrets import validate_encryption_key_id
    import pytest

    with pytest.raises(RuntimeError, match="must be 1-64 characters"):
        validate_encryption_key_id("test", "!invalid")

    with pytest.raises(RuntimeError, match="must start with a letter or number"):
        validate_encryption_key_id("test", "-invalid")


def test_build_runtime_encryption_key_invalid():
    from core.runtime_secrets import build_runtime_encryption_key
    import pytest

    with pytest.raises(RuntimeError, match="must be a valid Fernet key"):
        build_runtime_encryption_key("test", "test", "invalid_key")


def test_parse_previous_encryption_keys_empty_or_none():
    from core.runtime_secrets import _parse_previous_encryption_keys

    assert _parse_previous_encryption_keys(None) == ()
    assert _parse_previous_encryption_keys("") == ()
    assert _parse_previous_encryption_keys("   ") == ()


def test_parse_previous_encryption_keys_invalid_format():
    from core.runtime_secrets import _parse_previous_encryption_keys
    import pytest

    with pytest.raises(RuntimeError, match="entries must use key_id=fernet_key"):
        _parse_previous_encryption_keys("invalid_entry")

    with pytest.raises(RuntimeError, match="entries must use key_id=fernet_key"):
        _parse_previous_encryption_keys("=fernet_key")

    with pytest.raises(RuntimeError, match="entries must use key_id=fernet_key"):
        _parse_previous_encryption_keys("key_id=")


def test_parse_previous_encryption_keys_valid():
    from core.runtime_secrets import _parse_previous_encryption_keys

    result = _parse_previous_encryption_keys("key1=value1, key2=value2, ,,")
    assert result == (("key1", "value1"), ("key2", "value2"))


def test_character_class_count_incremental_classes():
    assert _character_class_count("a") == 1
    assert _character_class_count("aA") == 2
    assert _character_class_count("aA1") == 3
    assert _character_class_count("aA1!") == 4


def test_all_keys():
    from core.runtime_secrets import EncryptionKeyRing, RuntimeEncryptionKey
    from cryptography.fernet import Fernet

    fernet1 = Fernet(Fernet.generate_key())
    fernet2 = Fernet(Fernet.generate_key())

    key1 = RuntimeEncryptionKey(key_id="test1", fernet=fernet1)
    key2 = RuntimeEncryptionKey(key_id="test2", fernet=fernet2)

    secrets = EncryptionKeyRing(active_key=key1, previous_keys=(key2,))

    assert secrets.all_keys() == (key1, key2)


def test_build_encryption_keyring_invalid():
    from core.runtime_secrets import build_encryption_keyring
    from cryptography.fernet import Fernet
    import pytest

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        build_encryption_keyring(None)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        build_encryption_keyring("   ")

    valid_key = Fernet.generate_key().decode("utf-8")
    with pytest.raises(RuntimeError, match="must not repeat key identifiers"):
        build_encryption_keyring(valid_key, "same_id", f"same_id={valid_key}")


def test_build_encryption_keyring_valid():
    from core.runtime_secrets import build_encryption_keyring
    from cryptography.fernet import Fernet

    valid_key1 = Fernet.generate_key().decode("utf-8")
    valid_key2 = Fernet.generate_key().decode("utf-8")

    keyring = build_encryption_keyring(valid_key1, "key1", f"key2={valid_key2}")
    assert keyring.active_key.key_id == "key1"
    assert len(keyring.previous_keys) == 1
    assert keyring.previous_keys[0].key_id == "key2"


def test_key_for_id_found():
    from core.runtime_secrets import EncryptionKeyRing, RuntimeEncryptionKey
    from cryptography.fernet import Fernet

    fernet = Fernet(Fernet.generate_key())
    key1 = RuntimeEncryptionKey(key_id="test1", fernet=fernet)

    secrets = EncryptionKeyRing(active_key=key1, previous_keys=())

    assert secrets.key_for_id("test1") == key1
