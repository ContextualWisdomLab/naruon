"""Property-based fuzzing of the content-graph parser (services.content_graph).

``parse_content`` turns arbitrary email/attachment bodies (HTML, markdown or
plain text) into a node/segment graph. It runs the stdlib ``HTMLParser`` plus a
hand-written markdown splitter, so malformed markup must not crash it and must
not produce a structurally inconsistent graph (duplicate uids, dangling
segments, a missing/duplicated document root).
"""

import pytest

pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from ._invariants import CONTENT_TYPES, check_parse_content  # noqa: E402

_MARKUP_CHARS = st.sampled_from(list("<>/&#*-=[]() \t\n\rabcdhpHTML123"))
_CONTENT = st.text(
    alphabet=st.one_of(_MARKUP_CHARS, st.characters()),
    max_size=512,
)


@settings(
    max_examples=250,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(content=_CONTENT, content_type=st.sampled_from(CONTENT_TYPES))
def test_parse_content_holds_invariants(content: str, content_type: str) -> None:
    check_parse_content(content, content_type)
