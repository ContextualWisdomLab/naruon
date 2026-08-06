"""Finalize the reviewed PR 1245 repair helper before executing it.

This one-shot bridge corrects exact, previously reviewed source anchors in the
branch-local repair module, runs that module, and is removed by the verification
workflow before the durable product commit is published.
"""

from __future__ import annotations

import runpy
from pathlib import Path


REPAIR_SCRIPT = Path("scripts/ci/apply_pr1245_calendar_source_repair.py")


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    """Replace one exact source fragment or fail closed on branch drift."""
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label} fragment, observed {count}")
    return source.replace(old, new, 1)


def main() -> None:
    """Correct reviewed anchors and execute the self-removing repair module."""
    source = REPAIR_SCRIPT.read_text(encoding="utf-8")
    source = _replace_once(
        source,
        '    render_action_items = "  const actionItems = llmData?.action_items ?? [];\\n"\n',
        (
            '    render_action_items = (\n'
            '        "  const confidencePercent = toConfidencePercent(llmData?.confidence);\\n"\n'
            '        "  const actionItems = llmData?.action_items ?? [];\\n"\n'
            '    )\n'
        ),
        label="unique render source contract",
    )

    start_marker = "    conflict_action_end = _block(\n"
    end_marker = '        label="meeting source confirmation panel",\n    )\n'
    start_count = source.count(start_marker)
    end_count = source.count(end_marker)
    if start_count != 1 or end_count != 1:
        raise RuntimeError(
            "expected one meeting source panel repair region, "
            f"observed start={start_count}, end={end_count}"
        )
    start = source.index(start_marker)
    end = source.index(end_marker, start) + len(end_marker)
    replacement = (
        "    conflict_action_end = (\n"
        "        '                  {isSyncing ? \"조율 중\" : \"일정 조율\"}\\n'\n"
        "        '                </Button>\\n'\n"
        "        '              </div>\\n'\n"
        "        '            </div>\\n'\n"
        "        '          )}\\n'\n"
        "    )\n"
        "    source = _replace_once(\n"
        "        source,\n"
        "        conflict_action_end,\n"
        "        (\n"
        "            '                  {isSyncing ? \"조율 중\" : \"일정 조율\"}\\n'\n"
        "            '                </Button>\\n'\n"
        "            '              </div>\\n'\n"
        "            '              <div className=\"mt-3\">{calendarSourceSelector}</div>\\n'\n"
        "            '            </div>\\n'\n"
        "            '          )}\\n'\n"
        "        ),\n"
        "        label=\"meeting source confirmation panel\",\n"
        "    )\n"
    )
    source = source[:start] + replacement + source[end:]

    ambiguous_confirmation = (
        "    source = _replace_once(\n"
        "        source,\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.\\\");\\n\",\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.\\\");\\n\",\n"
        "        label=\"responsive-test source confirmation status\",\n"
        "    )\n"
    )
    deterministic_confirmation = (
        "    confirmation_before = (\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 선택한 원본 계정에 요청했습니다.\\\");\\n\"\n"
        "    )\n"
        "    confirmation_after = (\n"
        "        \"    expect(container.textContent).toContain(\"\n"
        "        \"\\\"1개 일정 반영 의도를 Fastmail 원본에 요청했습니다.\\\");\\n\"\n"
        "    )\n"
        "    confirmation_count = source.count(confirmation_before)\n"
        "    if confirmation_count != 2:\n"
        "        raise RuntimeError(\n"
        "            \"expected exactly two responsive-test source confirmation \"\n"
        "            f\"status fragments, observed {confirmation_count}\"\n"
        "        )\n"
        "    source = source.replace(confirmation_before, confirmation_after)\n"
    )
    source = _replace_once(
        source,
        ambiguous_confirmation,
        deterministic_confirmation,
        label="responsive confirmation multiplicity repair",
    )

    REPAIR_SCRIPT.write_text(source, encoding="utf-8")
    runpy.run_path(str(REPAIR_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()
