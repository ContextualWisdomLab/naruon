#!/usr/bin/env python3
"""Repair the temporary PR 1245 transformer string delimiters fail-closed."""

from pathlib import Path

path = Path(__file__).with_name("patch_pr1245_repair_script.py")
text = path.read_text(encoding="utf-8")
open_old = "write_replacement = '''    TESTS.write_text"
open_new = 'write_replacement = r"""    TESTS.write_text'
close_old = "\n'''\nreplace_exact(write_anchor, write_replacement, \"existing command regression update\")"
close_new = '\n"""\nreplace_exact(write_anchor, write_replacement, "existing command regression update")'
if text.count(open_old) != 1:
    raise SystemExit(f"expected one broken opening delimiter, found {text.count(open_old)}")
if text.count(close_old) != 1:
    raise SystemExit(f"expected one broken closing delimiter, found {text.count(close_old)}")
path.write_text(
    text.replace(open_old, open_new, 1).replace(close_old, close_new, 1),
    encoding="utf-8",
)
