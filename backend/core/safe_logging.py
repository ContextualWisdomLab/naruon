import traceback
import sys

def redacted_exception_info(e: Exception):
    """
    Returns exception information safe for logging without leaking sensitive
    stack traces or internal state that could be used maliciously.
    """
    return type(e).__name__
