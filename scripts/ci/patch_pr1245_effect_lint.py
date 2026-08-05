#!/usr/bin/env python3
"""Remove the synchronous effect reset rejected by the React lint contract."""

from pathlib import Path

path = Path(__file__).with_name("repair_pr1245_review.py")
text = path.read_text(encoding="utf-8")
old = '''  useEffect(() => {
    if (!shouldLoadCalendarSources) {
      setCalendarSources([]);
      setCalendarSourceStatus('idle');
      setSelectedCalendarSourceId('');
      return;
    }

    let isMounted = true;
'''
new = '''  useEffect(() => {
    if (!shouldLoadCalendarSources) return;

    let isMounted = true;
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one synchronous effect reset, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
