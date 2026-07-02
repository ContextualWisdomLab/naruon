from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentNode:
    content_node_uid: str
    source_kind: str
    source_record_uid: str
    parent_node_uid: str | None
    node_kind: str
    node_path: str
    ordinal_index: int
    display_label: str | None
    safe_text_content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class ContentSegment:
    content_segment_uid: str
    source_kind: str
    source_record_uid: str
    content_node_uid: str
    segment_kind: str
    segment_path: str
    ordinal_index: int
    heading_path: str | None
    safe_text_content: str
    content_hash: str
    token_count: int


@dataclass(frozen=True, slots=True)
class ParseResult:
    source_kind: str
    source_record_uid: str
    display_name: str
    content_type: str
    source_content_hash: str
    nodes: tuple[ContentNode, ...]
    segments: tuple[ContentSegment, ...]
