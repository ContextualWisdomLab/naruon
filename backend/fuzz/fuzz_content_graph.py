#!/usr/bin/env python3
"""Atheris (Apache-2.0) coverage-guided harness for parse_content.

Usage:
    python fuzz/fuzz_content_graph.py -max_total_time=60 fuzz/corpus/content
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
    from _invariants import CONTENT_TYPES, check_parse_content  # noqa: E402


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    content_type = CONTENT_TYPES[fdp.ConsumeIntInRange(0, len(CONTENT_TYPES) - 1)]
    content = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    check_parse_content(content, content_type)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
