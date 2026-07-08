"""Invariants asserted by every fuzz target.

Kept in one place so the Hypothesis property tests and the Atheris
coverage-guided harnesses check *exactly the same* contracts. Each function
either returns normally (invariants held) or raises ``AssertionError`` /
propagates an unexpected exception -- both of which a fuzzer treats as a
finding.

None of these helpers touch the network, a database, the filesystem, or the
environment: they only call pure in-process parsers on caller-supplied input.
"""

from __future__ import annotations

from services.attachment_parser import AttachmentParseResult, parse_email_attachment
from services.content_graph import parse_content
from services.content_graph.models import ParseResult
from services.email_parser import parse_eml_bytes
from services.exceptions import EmailParseError
from services.text_safety import contains_html_markup, strip_html_markup

# Content types worth exercising: every dispatch branch of parse_content plus a
# few that must fall through to the strip-then-plain-text path.
CONTENT_TYPES = (
    "text/plain",
    "text/html",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
    "",
    "TEXT/HTML; charset=utf-8",
)

ATTACHMENT_CONTENT_TYPES = (
    None,
    "",
    "text/plain",
    "text/html",
    "text/markdown",
    "application/pdf",
    "application/octet-stream",
    "image/png",
)


def check_strip_html_markup(value: str) -> None:
    """``strip_html_markup`` must return a string and be idempotent for *any*
    input, without raising.

    (NUL removal is the job of the ``_sanitize_nul`` wrapper applied *before*
    strip in the callers, so strip itself is intentionally not asserted to be
    NUL-free.)
    """
    out = strip_html_markup(value)
    assert isinstance(out, str), type(out)
    # Stripping already-stripped text must be a no-op (stable fixed point):
    # a non-idempotent HTML sanitiser is a real correctness/bypass hazard.
    assert strip_html_markup(out) == out, "strip_html_markup is not idempotent"
    # contains_html_markup is the companion classifier and must also be crash-free.
    assert isinstance(contains_html_markup(value), bool)


def check_parse_content(content: str, content_type: str) -> None:
    """``parse_content`` must return a structurally consistent ParseResult for
    any string / content-type pair, without raising."""
    result = parse_content(
        source_kind="email",
        source_record_uid="fuzz-record",
        content=content,
        content_type=content_type,
        display_name="fuzz",
    )
    assert isinstance(result, ParseResult)

    node_uids = {node.content_node_uid for node in result.nodes}
    # Node uids must be unique -- collisions would silently merge document
    # structure downstream.
    assert len(node_uids) == len(result.nodes), "duplicate content_node_uid"
    # There is always exactly one document root.
    documents = [n for n in result.nodes if n.node_kind == "document"]
    assert len(documents) == 1, f"expected 1 document node, got {len(documents)}"

    for segment in result.segments:
        # Every segment must point at a real node.
        assert segment.content_node_uid in node_uids, "segment references unknown node"
        assert isinstance(segment.safe_text_content, str)


def check_parse_email_attachment(
    filename: str | None, content_type: str | None, raw_content: object
) -> None:
    """``parse_email_attachment`` must always return a well-formed result; it
    must never raise regardless of filename / content-type / payload."""
    result = parse_email_attachment(
        filename=filename,
        content_type=content_type,
        raw_content=raw_content,
    )
    assert isinstance(result, AttachmentParseResult)
    assert isinstance(result.filename, str) and result.filename, "empty filename"
    for field in (
        result.content,
        result.parse_content,
        result.parser_key,
        result.parse_status,
    ):
        assert isinstance(field, str)
        assert "\x00" not in field, "attachment field leaked a NUL byte"


def check_parse_eml_bytes(raw: bytes) -> None:
    """``parse_eml_bytes`` may reject input, but only by raising the declared
    ``EmailParseError`` -- never a bare/unexpected exception -- and on success
    must return a NUL-free, well-typed ``EmailData`` mapping."""
    try:
        data = parse_eml_bytes(raw)
    except EmailParseError:
        return
    # If it claims success, the payload must satisfy the EmailData contract.
    for key in ("message_id", "sender", "recipients", "subject", "body"):
        assert isinstance(data[key], str), f"{key} is not a str"
        assert "\x00" not in data[key], f"{key} leaked a NUL byte"
    assert isinstance(data["attachments"], list)
