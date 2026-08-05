#!/usr/bin/env python3
"""Correct the bounded PR 1245 transformer to target the main conflict panel."""

from pathlib import Path

path = Path(__file__).with_name("repair_pr1245_review.py")
text = path.read_text(encoding="utf-8")
old = '    start = text.index("          {email.schedule_conflict && (")\n'
new = '''    start = text.index(
        '          {email.schedule_conflict && (\\n'
        '            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-sm">'
    )
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one broad conflict-panel anchor, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
