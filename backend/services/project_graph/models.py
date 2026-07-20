from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ProjectObjectType(str, Enum):
    PROJECT_CANDIDATE = "project_candidate"
    REQUIREMENT = "requirement"
    FEATURE = "feature"
    ISSUE = "issue"
    MILESTONE = "milestone"
    WBS_ITEM = "wbs_item"
    DELIVERABLE = "deliverable"
    PARTICIPANT = "participant"
    DATA_REQUIREMENT = "data_requirement"
    ERD_CANDIDATE = "erd_candidate"
    INFRA_REQUIREMENT = "infra_requirement"
    REPORT_DELTA = "report_delta"
    WIKI_PROJECTION = "wiki_projection"


@dataclass(frozen=True, slots=True)
class ProjectSourceSegment:
    content_segment_uid: str
    source_kind: str
    source_record_uid: str
    safe_text_content: str
    heading_path: str | None = None
    segment_path: str | None = None
    ordinal_index: int = 0


@dataclass(frozen=True, slots=True)
class ProjectSemanticObject:
    uid: str
    object_type: ProjectObjectType
    title: str
    summary: str
    source_segment_uids: tuple[str, ...]
    confidence: float
    extractor_name: str
    extractor_version: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.uid:
            raise ValueError("Project semantic object requires uid")
        if not self.source_segment_uids:
            raise ValueError("Project semantic object requires source segment citation")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Project semantic object confidence must be between 0 and 1")
        object.__setattr__(
            self,
            "source_segment_uids",
            tuple(self.source_segment_uids),
        )
        object.__setattr__(self, "attributes", dict(self.attributes))


@dataclass(frozen=True, slots=True)
class ProjectSemanticEdge:
    source_uid: str
    target_uid: str
    edge_type: str
    confidence: float
    source_segment_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_uid or not self.target_uid:
            raise ValueError("Project semantic edge requires endpoints")
        if not self.edge_type:
            raise ValueError("Project semantic edge requires edge type")
        if not self.source_segment_uids:
            raise ValueError("Project semantic edge requires source segment citation")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Project semantic edge confidence must be between 0 and 1")
        object.__setattr__(
            self,
            "source_segment_uids",
            tuple(self.source_segment_uids),
        )


@dataclass(frozen=True, slots=True)
class ProjectSemanticExtractionResult:
    objects: tuple[ProjectSemanticObject, ...]
    edges: tuple[ProjectSemanticEdge, ...]
    extractor_name: str
    extractor_version: str
