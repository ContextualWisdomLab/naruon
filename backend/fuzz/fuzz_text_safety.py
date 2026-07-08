#!/usr/bin/env python3
"""Atheris (Apache-2.0) coverage-guided harness for strip_html_markup.

Usage:
    python fuzz/fuzz_text_safety.py -max_total_time=60 fuzz/corpus/html
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
    from _invariants import check_strip_html_markup  # noqa: E402


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    check_strip_html_markup(fdp.ConsumeUnicodeNoSurrogates(len(data)))


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
