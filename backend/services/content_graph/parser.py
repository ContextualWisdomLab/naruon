from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser

from services.text_safety import strip_html_markup

from .models import ContentNode, ContentSegment, ParseResult


_BLANK_LINE_RE = re.compile(r"\n\s*\n+")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_RAW_TEXT_TAGS = {"script", "style", "template"}
_SEGMENT_TAGS = _HEADING_TAGS | {"p", "li", "blockquote", "pre", "td", "th"}
_VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_SUPPORTED_MARKDOWN_TYPES = {
    "text/markdown",
    "text/x-markdown",
    "application/markdown",
}


@dataclass(slots=True)
class _BuildContext:
    source_kind: str
    source_record_uid: str
    display_name: str
    content_type: str
    source_content_hash: str
    nodes: list[ContentNode] = field(default_factory=list)
    segments: list[ContentSegment] = field(default_factory=list)

    def add_node(
        self,
        *,
        parent_node_uid: str | None,
        node_kind: str,
        node_path: str,
        ordinal_index: int,
        safe_text_content: str = "",
        display_label: str | None = None,
    ) -> ContentNode:
        content_hash = _hash_text(safe_text_content)
        node = ContentNode(
            content_node_uid=_stable_uid(
                "cnode",
                self.source_kind,
                self.source_record_uid,
                self.source_content_hash,
                node_path,
            ),
            source_kind=self.source_kind,
            source_record_uid=self.source_record_uid,
            parent_node_uid=parent_node_uid,
            node_kind=node_kind,
            node_path=node_path,
            ordinal_index=ordinal_index,
            display_label=display_label,
            safe_text_content=safe_text_content,
            content_hash=content_hash,
        )
        self.nodes.append(node)
        return node

    def add_segment(
        self,
        *,
        content_node_uid: str,
        segment_kind: str,
        segment_path: str,
        heading_path: str | None,
        safe_text_content: str,
    ) -> ContentSegment:
        segment = ContentSegment(
            content_segment_uid=_stable_uid(
                "cseg",
                self.source_kind,
                self.source_record_uid,
                self.source_content_hash,
                segment_path,
                safe_text_content,
            ),
            source_kind=self.source_kind,
            source_record_uid=self.source_record_uid,
            content_node_uid=content_node_uid,
            segment_kind=segment_kind,
            segment_path=segment_path,
            ordinal_index=len(self.segments) + 1,
            heading_path=heading_path,
            safe_text_content=safe_text_content,
            content_hash=_hash_text(safe_text_content),
            word_count=_word_count(safe_text_content),
        )
        self.segments.append(segment)
        return segment

    def result(self) -> ParseResult:
        return ParseResult(
            source_kind=self.source_kind,
            source_record_uid=self.source_record_uid,
            display_name=self.display_name,
            content_type=self.content_type,
            source_content_hash=self.source_content_hash,
            nodes=tuple(self.nodes),
            segments=tuple(self.segments),
        )


@dataclass(slots=True)
class _PendingHtmlNode:
    tag: str
    node_path: str
    parent_node_uid: str | None
    ordinal_index: int
    text_parts: list[str] = field(default_factory=list)


class _ContentHTMLParser(HTMLParser):
    def __init__(self, context: _BuildContext, document_node: ContentNode):
        super().__init__(convert_charrefs=True)
        self._context = context
        self._document_node = document_node
        self._stack: list[_PendingHtmlNode] = []
        self._child_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._raw_text_depth = 0
        self._heading_stack: list[str] = []
        self._emitted_segment_paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized in _RAW_TEXT_TAGS:
            self._raw_text_depth += 1
            return
        if normalized in _VOID_HTML_TAGS:
            if normalized == "br":
                self._append_text_to_stack("\n")
            self._add_leaf_node(normalized)
            return

        parent_path = self._stack[-1].node_path if self._stack else "/document[1]"
        self._child_counts[parent_path][normalized] += 1
        ordinal_index = self._child_counts[parent_path][normalized]
        node_path = f"{parent_path}/{normalized}[{ordinal_index}]"
        parent_node_uid = (
            _node_uid(
                self._context,
                self._stack[-1].node_path,
            )
            if self._stack
            else self._document_node.content_node_uid
        )
        self._stack.append(
            _PendingHtmlNode(
                tag=normalized,
                node_path=node_path,
                parent_node_uid=parent_node_uid,
                ordinal_index=ordinal_index,
            )
        )

    def handle_startendtag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized in _RAW_TEXT_TAGS:
            return
        if normalized == "br":
            self._append_text_to_stack("\n")

        self._add_leaf_node(normalized)

    def _append_text_to_stack(self, value: str) -> None:
        for pending in self._stack:
            pending.text_parts.append(value)

    def _add_leaf_node(self, normalized: str) -> None:
        parent_path = self._stack[-1].node_path if self._stack else "/document[1]"
        self._child_counts[parent_path][normalized] += 1
        ordinal_index = self._child_counts[parent_path][normalized]
        node_path = f"{parent_path}/{normalized}[{ordinal_index}]"
        parent_node_uid = (
            _node_uid(self._context, self._stack[-1].node_path)
            if self._stack
            else self._document_node.content_node_uid
        )
        self._context.add_node(
            parent_node_uid=parent_node_uid,
            node_kind=normalized,
            node_path=node_path,
            ordinal_index=ordinal_index,
        )

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _RAW_TEXT_TAGS and self._raw_text_depth:
            self._raw_text_depth -= 1
            return
        if self._raw_text_depth:
            return

        matching_index = None
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index].tag == normalized:
                matching_index = index
                break
        if matching_index is None:
            return

        closing = self._stack[matching_index:]
        del self._stack[matching_index:]
        for pending in reversed(closing):
            self._emit_node_and_segment(pending)

    def handle_data(self, data: str) -> None:
        if self._raw_text_depth:
            return
        self._append_text_to_stack(data)

    def close(self) -> None:
        super().close()
        while self._stack:
            self._emit_node_and_segment(self._stack.pop())

    def _emit_node_and_segment(self, pending: _PendingHtmlNode) -> None:
        safe_text = _safe_text("".join(pending.text_parts))
        node = self._context.add_node(
            parent_node_uid=pending.parent_node_uid,
            node_kind=pending.tag,
            node_path=pending.node_path,
            ordinal_index=pending.ordinal_index,
            safe_text_content=safe_text,
        )
        if pending.tag not in _SEGMENT_TAGS or not safe_text:
            return
        if pending.node_path in self._emitted_segment_paths:
            return
        self._emitted_segment_paths.add(pending.node_path)

        if pending.tag in _HEADING_TAGS:
            level = int(pending.tag[1])
            self._heading_stack = self._heading_stack[: level - 1]
            self._heading_stack.append(safe_text)
            heading_path = _join_heading_path(self._heading_stack)
            segment_kind = "heading"
        else:
            heading_path = _join_heading_path(self._heading_stack)
            segment_kind = "paragraph"

        self._context.add_segment(
            content_node_uid=node.content_node_uid,
            segment_kind=segment_kind,
            segment_path=pending.node_path,
            heading_path=heading_path,
            safe_text_content=safe_text,
        )


def parse_content(
    *,
    source_kind: str,
    source_record_uid: str,
    content: str,
    content_type: str = "text/plain",
    display_name: str = "",
) -> ParseResult:
    normalized_type = _normalize_content_type(content_type)
    source_content_hash = _hash_text(content)
    context = _BuildContext(
        source_kind=source_kind,
        source_record_uid=source_record_uid,
        display_name=display_name,
        content_type=normalized_type,
        source_content_hash=source_content_hash,
    )
    document_node = _add_document_node(context, display_name)

    if normalized_type == "text/html":
        return _parse_html(context, document_node, content)
    if normalized_type in _SUPPORTED_MARKDOWN_TYPES:
        return _parse_markdown(context, document_node, content)
    if normalized_type == "text/plain":
        return _parse_plain_text(context, document_node, content)
    return _parse_plain_text(context, document_node, strip_html_markup(content))


def _parse_plain_text(
    context: _BuildContext,
    document_node: ContentNode,
    content: str,
) -> ParseResult:
    for index, paragraph in enumerate(_split_paragraphs(content), start=1):
        segment_path = f"/document[1]/paragraph[{index}]"
        node = context.add_node(
            parent_node_uid=document_node.content_node_uid,
            node_kind="paragraph",
            node_path=segment_path,
            ordinal_index=index,
            safe_text_content=paragraph,
        )
        context.add_segment(
            content_node_uid=node.content_node_uid,
            segment_kind="paragraph",
            segment_path=segment_path,
            heading_path=None,
            safe_text_content=paragraph,
        )
    return context.result()


def _parse_markdown(
    context: _BuildContext,
    document_node: ContentNode,
    content: str,
) -> ParseResult:
    heading_stack: list[str] = []
    heading_counts: defaultdict[int, int] = defaultdict(int)
    paragraph_index = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_index
        safe_text = _safe_text("\n".join(paragraph_lines))
        paragraph_lines.clear()
        if not safe_text:
            return

        paragraph_index += 1
        segment_path = f"/document[1]/paragraph[{paragraph_index}]"
        node = context.add_node(
            parent_node_uid=document_node.content_node_uid,
            node_kind="paragraph",
            node_path=segment_path,
            ordinal_index=paragraph_index,
            safe_text_content=safe_text,
        )
        context.add_segment(
            content_node_uid=node.content_node_uid,
            segment_kind="paragraph",
            segment_path=segment_path,
            heading_path=_join_heading_path(heading_stack),
            safe_text_content=safe_text,
        )

    for line in _normalize_newlines(content).split("\n"):
        heading_match = _MARKDOWN_HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            heading_text = _safe_text(heading_match.group(2))
            if not heading_text:
                continue
            heading_counts[level] += 1
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading_text)
            segment_path = f"/document[1]/h{level}[{heading_counts[level]}]"
            node = context.add_node(
                parent_node_uid=document_node.content_node_uid,
                node_kind=f"h{level}",
                node_path=segment_path,
                ordinal_index=heading_counts[level],
                safe_text_content=heading_text,
            )
            context.add_segment(
                content_node_uid=node.content_node_uid,
                segment_kind="heading",
                segment_path=segment_path,
                heading_path=_join_heading_path(heading_stack),
                safe_text_content=heading_text,
            )
            continue

        if not line.strip():
            flush_paragraph()
            continue
        paragraph_lines.append(line)

    flush_paragraph()
    return context.result()


def _parse_html(
    context: _BuildContext,
    document_node: ContentNode,
    content: str,
) -> ParseResult:
    parser = _ContentHTMLParser(context, document_node)
    parser.feed(content)
    parser.close()
    return context.result()


def _add_document_node(context: _BuildContext, display_name: str) -> ContentNode:
    return context.add_node(
        parent_node_uid=None,
        node_kind="document",
        node_path="/document[1]",
        ordinal_index=1,
        display_label=display_name or None,
    )


def _node_uid(context: _BuildContext, node_path: str) -> str:
    return _stable_uid(
        "cnode",
        context.source_kind,
        context.source_record_uid,
        context.source_content_hash,
        node_path,
    )


def _split_paragraphs(content: str) -> list[str]:
    normalized = _normalize_newlines(content)
    paragraphs = []
    for candidate in _BLANK_LINE_RE.split(normalized):
        safe_text = _safe_text(candidate)
        if safe_text:
            paragraphs.append(safe_text)
    return paragraphs


def _safe_text(value: str) -> str:
    return " ".join(strip_html_markup(value).split())


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_content_type(content_type: str | None) -> str:
    normalized = (content_type or "text/plain").split(";", maxsplit=1)[0]
    return normalized.strip().lower() or "text/plain"


def _join_heading_path(headings: list[str]) -> str | None:
    return " > ".join(headings) if headings else None


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def _stable_uid(prefix: str, *parts: str) -> str:
    payload = "\x00".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _word_count(value: str) -> int:
    return len(value.split())
