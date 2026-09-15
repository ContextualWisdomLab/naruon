"""Logging helpers for bounded exception correlation without raw exception data."""

from __future__ import annotations

import hashlib
from types import TracebackType

_REDACTED_EXCEPTION_MESSAGE = "Exception details redacted"
_FINGERPRINT_LENGTH = 16


def _exception_location_key(exc: BaseException) -> str:
    """Return an exact internal failure-site key used only as fingerprint input."""
    traceback = exc.__traceback__
    if traceback is None:
        return "unraised"
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    code = traceback.tb_frame.f_code
    module_name = str(traceback.tb_frame.f_globals.get("__name__", "unknown"))
    return (
        f"{module_name}:{code.co_qualname}:"
        f"{traceback.tb_lineno}:{traceback.tb_lasti}"
    )


def _exception_fingerprint(exc: BaseException) -> str:
    """Return a stable-per-build, non-secret fingerprint for an exact failure site."""
    exception_type = f"{type(exc).__module__}.{type(exc).__qualname__}"
    fingerprint_input = f"{exception_type}|{_exception_location_key(exc)}"
    return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[
        :_FINGERPRINT_LENGTH
    ]


def redacted_exception_info(
    exc: BaseException,
) -> tuple[type[RuntimeError], RuntimeError, TracebackType | None]:
    """Return sanitized logging evidence without raw values or traceback frames.

    ``exc_info=True`` and ordinary exception tuples render the original exception
    value and traceback. Provider, parser, database, and protocol exceptions can
    contain credentials, connection strings, response bodies, or internal paths.
    This helper uses the original traceback only to derive a one-way correlation
    fingerprint from the exception type and exact deepest execution site; it never
    attaches that traceback to the log record and never renders ``str(exc)`` or
    ``repr(exc)``.
    """
    safe_message = (
        f"{_REDACTED_EXCEPTION_MESSAGE} "
        f"exception_type={type(exc).__name__} "
        f"exception_fingerprint={_exception_fingerprint(exc)}"
    )
    return RuntimeError, RuntimeError(safe_message), None
