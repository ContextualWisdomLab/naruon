import json
from pathlib import Path

import pytest

from services.project_graph import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    ProjectObjectType,
    ProjectSemanticObject,
    ProjectSourceSegment,
    extract_project_semantics,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures/project_graph/semantic_segments.json"


def _fixture_segments() -> list[ProjectSourceSegment]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [ProjectSourceSegment(**item) for item in payload]


def test_extract_project_semantics_covers_project_management_domains():
    result = extract_project_semantics(_fixture_segments())

    object_types = {semantic_object.object_type for semantic_object in result.objects}

    assert {
        ProjectObjectType.PROJECT_CANDIDATE,
        ProjectObjectType.REQUIREMENT,
        ProjectObjectType.FEATURE,
        ProjectObjectType.ISSUE,
        ProjectObjectType.MILESTONE,
        ProjectObjectType.WBS_ITEM,
        ProjectObjectType.DELIVERABLE,
        ProjectObjectType.PARTICIPANT,
        ProjectObjectType.DATA_REQUIREMENT,
        ProjectObjectType.ERD_CANDIDATE,
        ProjectObjectType.INFRA_REQUIREMENT,
        ProjectObjectType.REPORT_DELTA,
        ProjectObjectType.WIKI_PROJECTION,
    } <= object_types
    assert result.extractor_name == EXTRACTOR_NAME
    assert result.extractor_version == EXTRACTOR_VERSION


def test_extracted_objects_and_edges_are_source_cited():
    result = extract_project_semantics(_fixture_segments())

    assert result.objects
    assert len(result.edges) == len(result.objects)
    assert all(semantic_object.source_segment_uids for semantic_object in result.objects)
    assert all(0.0 < semantic_object.confidence <= 1.0 for semantic_object in result.objects)
    assert all(edge.source_segment_uids for edge in result.edges)
    assert {edge.edge_type for edge in result.edges} == {
        "segment_evidences_project_object"
    }
    assert all(edge.source_uid.startswith("segment:") for edge in result.edges)


def test_extraction_is_deterministic_for_same_segments():
    first = extract_project_semantics(_fixture_segments())
    second = extract_project_semantics(_fixture_segments())

    assert first.objects == second.objects
    assert first.edges == second.edges


def test_milestone_extraction_records_date_evidence():
    result = extract_project_semantics(_fixture_segments())
    milestones = [
        semantic_object
        for semantic_object in result.objects
        if semantic_object.object_type is ProjectObjectType.MILESTONE
    ]

    assert milestones
    assert any("2026-07-15" in item.attributes["dates"] for item in milestones)
    assert any("date" in item.attributes["matched_terms"] for item in milestones)


def test_project_semantic_object_rejects_uncited_output():
    with pytest.raises(ValueError, match="source segment citation"):
        ProjectSemanticObject(
            uid="requirement:missing-citation",
            object_type=ProjectObjectType.REQUIREMENT,
            title="Requirement",
            summary="Missing citation",
            source_segment_uids=(),
            confidence=0.8,
            extractor_name=EXTRACTOR_NAME,
            extractor_version=EXTRACTOR_VERSION,
            attributes={},
        )
