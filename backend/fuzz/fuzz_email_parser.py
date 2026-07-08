#!/usr/bin/env python3
"""Atheris (Apache-2.0) coverage-guided harness for parse_eml_bytes.

Runs the same invariant as test_email_parser_fuzz.py, but driven by libFuzzer's
coverage feedback instead of Hypothesis' random search. Optional: Atheris is not
required to run the pytest property suite.

Usage:
    python fuzz/fuzz_email_parser.py -max_total_time=60 fuzz/corpus/email
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
    from _invariants import check_parse_eml_bytes  # noqa: E402


def test_one_input(data: bytes) -> None:
    check_parse_eml_bytes(data)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
