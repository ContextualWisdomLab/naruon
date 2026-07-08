#!/usr/bin/env python3
"""Atheris (Apache-2.0) coverage-guided harness for parse_email_attachment.

Usage:
    python fuzz/fuzz_attachment_parser.py -max_total_time=60 fuzz/corpus/attachment
"""
import os
import sys

import atheris

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
for _p in (_BACKEND, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

with atheris.instrument_imports():
    from _invariants import (  # noqa: E402
        ATTACHMENT_CONTENT_TYPES,
        check_parse_email_attachment,
    )


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    idx = fdp.ConsumeIntInRange(0, len(ATTACHMENT_CONTENT_TYPES) - 1)
    content_type = ATTACHMENT_CONTENT_TYPES[idx]
    filename = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 64))
    raw = fdp.ConsumeBytes(fdp.remaining_bytes())
    check_parse_email_attachment(filename or None, content_type, raw)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
