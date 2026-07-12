import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from db.models import EncryptedString, TenantConfig, get_encryption_keyring, get_fernet
from core.config import settings

TEST_OPENAI_KEY = "test_key2"  # noqa: S105
TEST_IMAP_PASSWORD = "imap-secret"  # noqa: S105
TEST_POP3_PASSWORD = "pop3-secret"  # noqa: S105
TEST_SMTP_PASSWORD = "smtp-secret"  # noqa: S105


@pytest.fixture(autouse=True)
def mock_debug():
    old_debug = settings.DEBUG
    old_encryption_key = settings.ENCRYPTION_KEY
    old_encryption_key_id = settings.ENCRYPTION_KEY_ID
    old_previous_keys = settings.ENCRYPTION_PREVIOUS_KEYS
    settings.DEBUG = True
    settings.ENCRYPTION_KEY_ID = "test-active"
    settings.ENCRYPTION_KEY = SecretStr(Fernet.generate_key().decode("ascii"))
    settings.ENCRYPTION_PREVIOUS_KEYS = None
    yield
    settings.DEBUG = old_debug
    settings.ENCRYPTION_KEY = old_encryption_key
    settings.ENCRYPTION_KEY_ID = old_encryption_key_id
    settings.ENCRYPTION_PREVIOUS_KEYS = old_previous_keys


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TenantConfig.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_tenant_config_model_exists():
    config = TenantConfig(
        user_id="test_user",
        organization_id="org_acme",
        openai_api_key="test_key",
    )
    assert config.user_id == "test_user"
    assert config.organization_id == "org_acme"
    assert config.openai_api_key == "test_key"


def test_tenant_config_allows_same_user_in_different_organizations(db_session):
    db_session.add(
        TenantConfig(
            user_id="shared_user",
            organization_id="org_acme",
            smtp_server="smtp.example.com",
        )
    )
    db_session.add(
        TenantConfig(
            user_id="shared_user",
            organization_id="org_rival",
            smtp_server="smtp.other.com",
        )
    )
    db_session.commit()

    rows = (
        db_session.query(TenantConfig)
        .filter_by(user_id="shared_user")
        .order_by(TenantConfig.organization_id)
        .all()
    )

    assert [row.organization_id for row in rows] == ["org_acme", "org_rival"]


def test_get_fernet_requires_encryption_key_even_when_debug_enabled():
    settings.ENCRYPTION_KEY = None

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
        get_fernet()


def test_get_fernet_rejects_non_fernet_key_without_derivation():
    settings.ENCRYPTION_KEY = SecretStr("test-encryption-key")

    with pytest.raises(RuntimeError, match="valid Fernet key"):
        get_fernet()


def test_encryption_keyring_rejects_duplicate_previous_key_id():
    settings.ENCRYPTION_PREVIOUS_KEYS = SecretStr(
        f"test-active={Fernet.generate_key().decode('ascii')}"
    )

    with pytest.raises(RuntimeError, match="must not repeat key identifiers"):
        get_encryption_keyring()


def test_encrypted_string_prefixes_active_key_id():
    settings.ENCRYPTION_KEY_ID = "tenant-secrets-2026-06"
    encrypted_string = EncryptedString()

    encrypted_value = encrypted_string.process_bind_param(TEST_SMTP_PASSWORD, None)

    assert encrypted_value.startswith("fernet:v1:tenant-secrets-2026-06:")
    assert encrypted_string.process_result_value(encrypted_value, None) == (
        TEST_SMTP_PASSWORD
    )


def test_encrypted_string_decrypts_rotated_versioned_key():
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    encrypted_string = EncryptedString()
    settings.ENCRYPTION_KEY_ID = "tenant-secrets-2026-05"
    settings.ENCRYPTION_KEY = SecretStr(old_key)

    encrypted_value = encrypted_string.process_bind_param(TEST_POP3_PASSWORD, None)

    settings.ENCRYPTION_KEY_ID = "tenant-secrets-2026-06"
    settings.ENCRYPTION_KEY = SecretStr(new_key)
    settings.ENCRYPTION_PREVIOUS_KEYS = SecretStr(f"tenant-secrets-2026-05={old_key}")

    assert encrypted_string.process_result_value(encrypted_value, None) == (
        TEST_POP3_PASSWORD
    )
    assert encrypted_string.process_bind_param(TEST_IMAP_PASSWORD, None).startswith(
        "fernet:v1:tenant-secrets-2026-06:"
    )


def test_encrypted_string_decrypts_legacy_ciphertext_with_previous_key():
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    encrypted_string = EncryptedString()
    settings.ENCRYPTION_KEY_ID = "tenant-secrets-2026-05"
    settings.ENCRYPTION_KEY = SecretStr(old_key)
    legacy_ciphertext = get_fernet().encrypt(TEST_IMAP_PASSWORD.encode("utf-8")).decode(
        "utf-8"
    )

    settings.ENCRYPTION_KEY_ID = "tenant-secrets-2026-06"
    settings.ENCRYPTION_KEY = SecretStr(new_key)
    settings.ENCRYPTION_PREVIOUS_KEYS = SecretStr(f"tenant-secrets-2026-05={old_key}")

    assert encrypted_string.process_result_value(legacy_ciphertext, None) == (
        TEST_IMAP_PASSWORD
    )


def test_encrypted_string_returns_none_on_tampered_ciphertext():
    encrypted_string = EncryptedString()
    encrypted_value = encrypted_string.process_bind_param(TEST_SMTP_PASSWORD, None)
    assert encrypted_value is not None
    tampered_value = encrypted_value[:-1] + ("A" if encrypted_value[-1] != "A" else "B")

    decrypted_value = encrypted_string.process_result_value(tampered_value, None)

    assert decrypted_value is None
    assert decrypted_value != tampered_value


def test_encrypted_string_returns_none_on_wrong_key_without_leaking_ciphertext():
    encrypted_string = EncryptedString()
    encrypted_value = encrypted_string.process_bind_param(TEST_IMAP_PASSWORD, None)
    assert encrypted_value is not None
    settings.ENCRYPTION_KEY = SecretStr(Fernet.generate_key().decode("ascii"))

    decrypted_value = encrypted_string.process_result_value(encrypted_value, None)

    assert decrypted_value is None
    assert decrypted_value != encrypted_value


def test_tenant_config_model_encryption(db_session):
    config = TenantConfig(
        user_id="test_user2",
        openai_api_key=TEST_OPENAI_KEY,
        imap_username="mail-user",
        imap_password=TEST_IMAP_PASSWORD,
        pop3_username="pop3-user",
        pop3_password=TEST_POP3_PASSWORD,
        smtp_password=TEST_SMTP_PASSWORD,
    )
    db_session.add(config)
    db_session.commit()

    # Query back to ensure it can be decrypted properly
    saved_config = (
        db_session.query(TenantConfig).filter_by(user_id="test_user2").first()
    )
    assert saved_config.openai_api_key == TEST_OPENAI_KEY

    # Verify that the value in the database is actually encrypted
    result = db_session.execute(
        text("SELECT openai_api_key FROM tenant_configs WHERE user_id = :user_id"),
        {"user_id": "test_user2"},
    ).scalar()
    assert result != "test_key2"
    assert result is not None
    assert isinstance(result, str)

    imap_pw = db_session.execute(
        text("SELECT imap_password FROM tenant_configs WHERE user_id = :user_id"),
        {"user_id": "test_user2"},
    ).scalar()
    smtp_pw = db_session.execute(
        text("SELECT smtp_password FROM tenant_configs WHERE user_id = :user_id"),
        {"user_id": "test_user2"},
    ).scalar()
    pop3_pw = db_session.execute(
        text("SELECT pop3_password FROM tenant_configs WHERE user_id = :user_id"),
        {"user_id": "test_user2"},
    ).scalar()
    assert imap_pw != TEST_IMAP_PASSWORD
    assert smtp_pw != TEST_SMTP_PASSWORD
    assert pop3_pw != TEST_POP3_PASSWORD
    assert saved_config.imap_username == "mail-user"
    assert saved_config.imap_password == TEST_IMAP_PASSWORD
    assert saved_config.pop3_username == "pop3-user"
    assert saved_config.pop3_password == TEST_POP3_PASSWORD
    assert saved_config.smtp_password == TEST_SMTP_PASSWORD

    # Verify __repr__ does not expose sensitive keys
    repr_str = repr(saved_config)
    assert TEST_OPENAI_KEY not in repr_str
    assert TEST_IMAP_PASSWORD not in repr_str
    assert TEST_POP3_PASSWORD not in repr_str
    assert TEST_SMTP_PASSWORD not in repr_str
    assert "has_openai_key=True" in repr_str
    assert "has_imap_password=True" in repr_str
    assert "has_pop3_password=True" in repr_str
    assert "has_smtp_password=True" in repr_str
