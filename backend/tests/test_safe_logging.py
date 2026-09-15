"""Regression tests for secret-safe exception logging."""

import logging
import re

from core.safe_logging import redacted_exception_info

_TOKEN_PREFIX = "token="
_SECRET_ONE = "super-secret-value-one"
_SECRET_TWO = "super-secret-value-two"
_CONNECTION_STRING = "postgresql://user:password@internal.example/db"


def _raise_secret_bearing_exception(
    secret_value: str,
    *,
    alternate_site: bool = False,
) -> None:
    """Raise from one function with two distinct execution sites."""
    message = "provider " + _TOKEN_PREFIX + secret_value + " " + _CONNECTION_STRING
    if alternate_site:
        raise RuntimeError(message)
    raise RuntimeError(message)


def _capture_redacted_exception_info(
    secret_value: str,
    *,
    alternate_site: bool = False,
):
    """Capture the sanitized logging tuple for a secret-bearing exception."""
    try:
        _raise_secret_bearing_exception(secret_value, alternate_site=alternate_site)
    except RuntimeError as exc:
        return redacted_exception_info(exc)
    raise AssertionError("expected RuntimeError")


def _render_exception_info(exc_info) -> str:
    """Render an exception tuple using Python's production logging formatter."""
    record = logging.LogRecord(
        name="naruon.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Provider operation failed",
        args=(),
        exc_info=exc_info,
    )
    return logging.Formatter("%(message)s").format(record)


def _fingerprint(rendered: str) -> str:
    """Extract the structured correlation fingerprint from rendered telemetry."""
    match = re.search(r"exception_fingerprint=([0-9a-f]{16})", rendered)
    assert match is not None
    return match.group(1)


def test_redacted_exception_info_emits_bounded_structured_correlation() -> None:
    """Exclude secret values and traceback paths while retaining RCA correlation."""
    rendered = _render_exception_info(_capture_redacted_exception_info(_SECRET_ONE))

    assert _SECRET_ONE not in rendered
    assert _TOKEN_PREFIX not in rendered
    assert _CONNECTION_STRING not in rendered
    assert __file__ not in rendered
    assert "_raise_secret_bearing_exception" not in rendered
    assert "Exception details redacted" in rendered
    assert "exception_type=RuntimeError" in rendered
    assert _fingerprint(rendered)


def test_redacted_exception_info_fingerprint_is_message_independent() -> None:
    """Correlate the same failure site without making secret text part of the key."""
    first = _render_exception_info(_capture_redacted_exception_info(_SECRET_ONE))
    second = _render_exception_info(_capture_redacted_exception_info(_SECRET_TWO))

    assert _SECRET_TWO not in second
    assert _fingerprint(first) == _fingerprint(second)


def test_redacted_exception_info_distinguishes_sites_in_same_function() -> None:
    """Do not collapse distinct failure lines inside one function into one incident."""
    first = _render_exception_info(_capture_redacted_exception_info(_SECRET_ONE))
    second = _render_exception_info(
        _capture_redacted_exception_info(_SECRET_ONE, alternate_site=True)
    )

    assert _SECRET_ONE not in first
    assert _SECRET_ONE not in second
    assert "_raise_secret_bearing_exception" not in first
    assert "_raise_secret_bearing_exception" not in second
    assert _fingerprint(first) != _fingerprint(second)


def test_redacted_exception_info_handles_unraised_exception() -> None:
    """Produce bounded telemetry even when an exception has no traceback object."""
    exc_info = redacted_exception_info(ValueError(_CONNECTION_STRING))
    rendered = _render_exception_info(exc_info)

    assert exc_info[2] is None
    assert _CONNECTION_STRING not in rendered
    assert "exception_type=ValueError" in rendered
    assert _fingerprint(rendered)
