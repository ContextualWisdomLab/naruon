"""Property-based fuzzing of the raw-MIME email parser (services.email_parser).

``parse_eml_bytes`` is the entry point for provider-fetched email bytes. Its
contract: either raise the declared ``EmailParseError`` or return a well-formed
``EmailData``. It must never let another exception escape -- note that
``_message_to_email_data`` (address/date/body/attachment parsing) runs *outside*
the function's original try/except, so a downstream raise would leak straight to
callers. This target found two such escapes (a UnicodeEncodeError on non-ASCII
From addresses, and a KeyError on multipart-declared bodies with no parts),
which were fixed in services/email_parser.py.

The strategy assembles both plausible MIME messages (headers the parser branches
on -- From/To/Subject/Date/References/In-Reply-To + multipart bodies) and fully
arbitrary byte blobs, so both the structured and the garbage paths are covered.
"""

import pytest

pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from ._invariants import check_parse_eml_bytes  # noqa: E402

_HEADER_NAMES = st.sampled_from([
    "From", "To", "Cc", "Reply-To", "Subject", "Date",
    "Message-ID", "References", "In-Reply-To", "Content-Type",
    "MIME-Version", "Content-Disposition", "Content-Transfer-Encoding",
])

# Header values seed the tricky branches: multiple/garbage addresses, unparsable
# dates, whitespace-only reference lists, encoded words, IDN/non-ASCII
# addr-specs, and NUL/control bytes.
_HEADER_VALUES = st.sampled_from([
    "Alice <alice@example.com>",
    '"Doe, John" <j@x.com>, second@y.com, malformed@',
    "undisclosed-recipients:;",
    "not-a-real-date",
    "Mon, 07 Jul 2026 10:00:00 +0000",
    "<a@x> <b@x> <c@x>",
    "   ",
    "=?utf-8?B?7ZWc6riA?=",
    "user@호스트.com",
    "multipart/mixed; boundary=\"B\"",
    "text/html; charset=utf-8",
    "text/plain",
    "<m\x00id@x>",
    "1.0",
    "attachment; filename=\"../../evil.txt\"",
])


@st.composite
def _mime_messages(draw) -> bytes:
    headers = draw(
        st.lists(st.tuples(_HEADER_NAMES, _HEADER_VALUES), min_size=0, max_size=8)
    )
    header_block = "".join(f"{name}: {value}\r\n" for name, value in headers)
    body = draw(st.text(max_size=200))
    # Optionally build a real multipart body so the walk()/attachment path runs.
    if draw(st.booleans()):
        boundary = "B"
        header_block = (
            "MIME-Version: 1.0\r\n"
            f'Content-Type: multipart/mixed; boundary="{boundary}"\r\n'
            + header_block
        )
        part_body = draw(st.text(max_size=120))
        body = (
            f"--{boundary}\r\nContent-Type: text/html\r\n\r\n{part_body}\r\n"
            f"--{boundary}\r\n"
            "Content-Type: text/plain\r\n"
            'Content-Disposition: attachment; filename="a.txt"\r\n\r\n'
            f"{body}\r\n--{boundary}--\r\n"
        )
    raw = f"{header_block}\r\n{body}"
    return raw.encode("utf-8", errors="surrogatepass")


_INPUT = st.one_of(
    _mime_messages(),
    st.binary(max_size=512),
)


@settings(
    max_examples=400,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(_INPUT)
def test_parse_eml_bytes_only_raises_email_parse_error(raw: bytes) -> None:
    check_parse_eml_bytes(raw)
