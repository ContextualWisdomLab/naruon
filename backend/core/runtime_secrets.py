import math
from collections import Counter


MIN_AUTH_SESSION_HMAC_SECRET_BYTES = 32
MIN_AUTH_SESSION_HMAC_SECRET_UNIQUE_CHARS = 12
MIN_AUTH_SESSION_HMAC_SECRET_CHARACTER_CLASSES = 3
MIN_AUTH_SESSION_HMAC_SECRET_ENTROPY_BITS = 128.0
_LOW_ENTROPY_PLACEHOLDER_TERMS = ("change", "example", "password", "secret")
_KNOWN_PUBLIC_AUTH_SESSION_HMAC_SECRETS = frozenset(
    {"naruon-session-hmac-token-32-byte-minimum"}
)


def _character_class_count(secret: str) -> int:
    return sum(
        (
            any(char.islower() for char in secret),
            any(char.isupper() for char in secret),
            any(char.isdigit() for char in secret),
            any(not char.isalnum() for char in secret),
        )
    )


def _shannon_entropy_bits(secret: str) -> float:
    length = len(secret)
    counts = Counter(secret)
    return (
        -sum(
            (count / length) * math.log2(count / length)
            for count in counts.values()
        )
        * length
    )


def validate_auth_session_hmac_secret_value(secret: str) -> None:
    if not secret:
        raise ValueError(
            "AUTH_SESSION_HMAC_SECRET must be at least 32 bytes in all environments"
        )
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) < MIN_AUTH_SESSION_HMAC_SECRET_BYTES:
        raise ValueError(
            "AUTH_SESSION_HMAC_SECRET must be at least 32 bytes in all environments"
        )
    if len(set(secret)) == 1:
        raise ValueError("AUTH_SESSION_HMAC_SECRET must not be a repeated character")
    normalized_secret = secret.lower()
    if normalized_secret in _KNOWN_PUBLIC_AUTH_SESSION_HMAC_SECRETS:
        raise ValueError("AUTH_SESSION_HMAC_SECRET must not use a public fixture value")
    if any(term in normalized_secret for term in _LOW_ENTROPY_PLACEHOLDER_TERMS):
        raise ValueError("AUTH_SESSION_HMAC_SECRET must not contain placeholder terms")
    if len(set(secret)) < MIN_AUTH_SESSION_HMAC_SECRET_UNIQUE_CHARS:
        raise ValueError(
            "AUTH_SESSION_HMAC_SECRET must contain at least 12 distinct characters"
        )
    if _character_class_count(secret) < MIN_AUTH_SESSION_HMAC_SECRET_CHARACTER_CLASSES:
        raise ValueError(
            "AUTH_SESSION_HMAC_SECRET must use at least three character classes"
        )
    if _shannon_entropy_bits(secret) < MIN_AUTH_SESSION_HMAC_SECRET_ENTROPY_BITS:
        raise ValueError(
            "AUTH_SESSION_HMAC_SECRET must provide at least 128 bits of estimated entropy"
        )
