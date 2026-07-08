"""Property-based fuzzing of the attachment parser (services.attachment_parser).

``parse_email_attachment`` receives an attacker-controlled filename, MIME
content-type and raw payload (bytes, str, or anything the email stack hands
back). It must always return a well-formed ``AttachmentParseResult`` -- never
raise -- and must sanitise filename/text fields (NUL-free, non-empty filename).
"""

import pytest

pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from ._invariants import (  # noqa: E402
    ATTACHMENT_CONTENT_TYPES,
    check_parse_email_attachment,
)

# Filenames exercise path-traversal, NUL, empty, dot, and markup edge cases.
_FILENAMES = st.one_of(
    st.none(),
    st.sampled_from([
        "", ".", "..", "a.txt", "../../etc/passwd", "a\x00.md",
        "<b>.html", "x.PDF", ".hidden", "n a m e.txt",
    ]),
    st.text(max_size=64),
)

# Raw content covers the real union: bytes (incl. invalid utf-8), str, None,
# and non-string objects that must be coerced via str().
_RAW = st.one_of(
    st.none(),
    st.binary(max_size=256),
    st.text(max_size=256),
    st.integers(),
    st.lists(st.integers(), max_size=8),
)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    filename=_FILENAMES,
    content_type=st.sampled_from(ATTACHMENT_CONTENT_TYPES),
    raw_content=_RAW,
)
def test_parse_email_attachment_never_crashes(
    filename, content_type, raw_content
) -> None:
    check_parse_email_attachment(filename, content_type, raw_content)
