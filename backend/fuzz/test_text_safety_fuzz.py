"""Property-based fuzzing of the HTML-stripping sanitiser (services.text_safety).

``strip_html_markup`` is a hand-rolled tag/entity state machine that runs on
every inbound email subject, body, display name and attachment filename, so a
crash or a non-idempotent result there is an ingest-path denial-of-service or a
sanitiser-bypass hazard.
"""

import pytest

pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from ._invariants import check_strip_html_markup  # noqa: E402

# Bias generation toward the characters the parser branches on (angle brackets,
# entities, slashes, quotes, attribute punctuation) while still allowing any
# codepoint through so surrogate/whitespace/control edge cases are reached.
_MARKUP_CHARS = st.sampled_from(list("<>/&;=\"'!?-:# \t\n\rabcdivpsScriptaye"))
_HOSTILE_TEXT = st.text(
    alphabet=st.one_of(_MARKUP_CHARS, st.characters()),
    max_size=256,
)


@settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(_HOSTILE_TEXT)
def test_strip_html_markup_never_crashes_and_is_idempotent(value: str) -> None:
    check_strip_html_markup(value)


@settings(max_examples=100, deadline=None)
@given(st.text(max_size=512))
def test_strip_html_markup_plain_text(value: str) -> None:
    check_strip_html_markup(value)
