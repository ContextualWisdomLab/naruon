"""Fuzz / property-based tests for naruon's untrusted-input parsers.

These targets exercise the surfaces that ingest attacker-controlled bytes and
strings (raw MIME email, HTML/markdown content, email attachments) and assert
that they degrade gracefully instead of crashing with an unhandled exception.

The same invariants are shared by the Hypothesis property tests
(``test_*_fuzz.py``, always runnable under pytest) and the optional
coverage-guided Atheris harnesses (``fuzz_*.py``).
"""
