from __future__ import annotations

import hashlib
import datetime
import re
from dataclasses import dataclass
from typing import Iterable

from .models import (
    ProjectObjectType,
    ProjectSemanticEdge,
    ProjectSemanticExtractionResult,
    ProjectSemanticObject,
    ProjectSourceSegment,
)

EXTRACTOR_NAME = "deterministic_project_graph"
EXTRACTOR_VERSION = "2026.07.02.1"

_DATE_RE = re.compile(
    r"(?<!\d)20\d{2}[-./]\d{1,2}[-./]\d{1,2}(?=\D|$)"
    r"|20\d{2}년\s*\d{1,2}월\s*\d{1,2}일"
)
_SPACE_RE = re.compile(r"\s+")
_ASCII_TOKEN_RE_CACHE: dict[str, re.Pattern[str]] = {}


@dataclass(frozen=True, slots=True)
class _ObjectRule:
    object_type: ProjectObjectType
    title_prefix: str
    keywords: tuple[str, ...]


_RULES: tuple[_ObjectRule, ...] = (
    _ObjectRule(
        ProjectObjectType.PROJECT_CANDIDATE,
        "Project",
        ("project", "프로젝트", "kickoff", "킥오프", "착수", "launch"),
    ),
    _ObjectRule(
        ProjectObjectType.REQUIREMENT,
        "Requirement",
        (
            "requirement",
            "요구사항",
            "필수",
            "must",
            "should",
            "shall",
            "정책",
            "제약",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.FEATURE,
        "Feature",
        (
            "feature",
            "기능",
            "user story",
            "acceptance criteria",
            "사용자는",
            "화면",
            "wireframe",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.ISSUE,
        "Issue",
        (
            "blocker",
            "risk",
            "defect",
            "issue",
            "approval-needed",
            "질문",
            "리스크",
            "장애",
            "지연",
            "승인 필요",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.DECISION,
        "Decision",
        (
            "decision",
            "decided",
            "approved",
            "resolved",
            "agreed",
            "sign-off",
            "signed-off",
            "greenlight",
            "의사결정",
            "결정",
            "의결",
            "결재",
            "재가",
            "가결",
            "부결",
            "확정",
            "합의",
            "승인됨",
            "승인 완료",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.MILESTONE,
        "Milestone",
        (
            "milestone",
            "deadline",
            "due",
            "release",
            "일정",
            "마일스톤",
            "까지",
            "납기",
            "릴리즈",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.WBS_ITEM,
        "WBS",
        (
            "wbs",
            "work package",
            "phase",
            "sprint",
            "epic",
            "story",
            "task",
            "작업",
            "단계",
            "백로그",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.DELIVERABLE,
        "Deliverable",
        (
            "deliverable",
            "artifact",
            "srs",
            "prd",
            "test report",
            "산출물",
            "보고서",
            "명세서",
            "wireframe",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.PARTICIPANT,
        "Participant",
        (
            "owner",
            "assignee",
            "pm",
            "approver",
            "stakeholder",
            "담당",
            "담당자",
            "승인권자",
            "이해관계자",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.DATA_REQUIREMENT,
        "Data Requirement",
        (
            "data requirement",
            "entity",
            "attribute",
            "retention",
            "privacy",
            "quality rule",
            "데이터 요건",
            "엔티티",
            "속성",
            "보존",
            "개인정보",
            "품질 규칙",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.ERD_CANDIDATE,
        "ERD",
        (
            "erd",
            "entity relationship",
            "table",
            "column",
            "foreign key",
            "테이블",
            "컬럼",
            "관계",
            "외래키",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.INFRA_REQUIREMENT,
        "Infra Requirement",
        (
            "infrastructure",
            "environment",
            "network",
            "runner",
            "secret",
            "backup",
            "slo",
            "deployment",
            "인프라",
            "환경",
            "네트워크",
            "시크릿",
            "백업",
            "배포",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.REPORT_DELTA,
        "Report Delta",
        (
            "daily report",
            "weekly report",
            "status report",
            "delta",
            "일일 보고",
            "주간 보고",
            "진척",
            "변경",
            "상태 보고",
        ),
    ),
    _ObjectRule(
        ProjectObjectType.WIKI_PROJECTION,
        "Wiki Projection",
        (
            "wiki",
            "knowledge base",
            "llm wiki",
            "위키",
            "지식 베이스",
            "문서화",
        ),
    ),
)


def extract_project_semantics(
    segments: Iterable[ProjectSourceSegment],
) -> ProjectSemanticExtractionResult:
    objects: list[ProjectSemanticObject] = []
    edges: list[ProjectSemanticEdge] = []

    for segment in segments:
        text = _normalize_text(segment.safe_text_content)
        if not text:
            continue

        for rule in _RULES:
            matched_terms = _matched_terms(text, rule)
            dates = _DATE_RE.findall(text)
            if rule.object_type is ProjectObjectType.MILESTONE and dates:
                matched_terms = (*matched_terms, "date")
            if not matched_terms:
                continue

            semantic_object = _build_object(
                segment=segment,
                text=text,
                rule=rule,
                matched_terms=matched_terms,
                dates=tuple(dates),
            )
            objects.append(semantic_object)
            edges.append(_source_edge(segment, semantic_object))

    return ProjectSemanticExtractionResult(
        objects=tuple(objects),
        edges=tuple(edges),
        extractor_name=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
    )


_FACT_LABEL_RE = re.compile(
    r"(?<!\S)(?P<label>invoice date|due date|date|계약일|납기일|청구일|"
    r"amount|total|금액|합계|party|vendor|customer|당사자|공급자|고객|"
    r"commitment|약속|확약)\s*[:：]\s*",
    re.IGNORECASE,
)
_FACT_DATE_RE = re.compile(r"^(20\d{2})[-./](\d{1,2})[-./](\d{1,2})$")
_AMOUNT_NUMBER = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?"
_FACT_AMOUNT_RE = re.compile(
    rf"^(?:[₩$€£]\s*{_AMOUNT_NUMBER}|"
    rf"(?:USD|KRW|EUR|GBP)\s+{_AMOUNT_NUMBER}|"
    rf"{_AMOUNT_NUMBER}\s*원)$",
    re.IGNORECASE,
)
_OTHER_LABEL_RE = re.compile(r"(?<!\S)[A-Za-z가-힣][\w -]{0,32}[:：]\s*")
_FACT_LABELS = {
    "date": "date",
    "due date": "date",
    "invoice date": "date",
    "계약일": "date",
    "납기일": "date",
    "청구일": "date",
    "amount": "amount",
    "total": "amount",
    "금액": "amount",
    "합계": "amount",
    "party": "party",
    "vendor": "party",
    "customer": "party",
    "당사자": "party",
    "공급자": "party",
    "고객": "party",
    "commitment": "commitment",
    "약속": "commitment",
    "확약": "commitment",
}


def extract_attachment_facts(
    segments: Iterable[ProjectSourceSegment],
) -> ProjectSemanticExtractionResult:
    """Promote only literal, labelled attachment facts with exact segment citations."""
    objects: list[ProjectSemanticObject] = []
    edges: list[ProjectSemanticEdge] = []
    for segment in segments:
        if segment.source_kind != "attachment":
            continue
        matches = list(_FACT_LABEL_RE.finditer(segment.safe_text_content))
        for index, match in enumerate(matches):
            label = match["label"].casefold()
            kind = _FACT_LABELS[label]
            end = matches[index + 1].start() if index + 1 < len(matches) else None
            value = segment.safe_text_content[match.end() : end].strip()
            if not value or len(value) > 160:
                continue
            if kind in {"party", "commitment"} and _OTHER_LABEL_RE.search(value):
                continue
            if kind == "date":
                date_match = _FACT_DATE_RE.fullmatch(value)
                if date_match is None:
                    continue
                try:
                    datetime.date(*map(int, date_match.groups()))
                except ValueError:
                    continue
            elif kind == "amount" and _FACT_AMOUNT_RE.fullmatch(value) is None:
                continue
            fact_text = f"{match['label']}: {value}"
            digest = hashlib.sha256(
                f"{segment.content_segment_uid}|{match.start()}|{fact_text}".encode(
                    "utf-8"
                )
            ).hexdigest()[:20]
            fact = ProjectSemanticObject(
                uid=f"attachment_fact:{digest}",
                object_type=ProjectObjectType.ATTACHMENT_FACT,
                title=fact_text[:240],
                summary=fact_text,
                source_segment_uids=(segment.content_segment_uid,),
                confidence=0.9,
                extractor_name="literal_attachment_fact",
                extractor_version="1",
                attributes={"fact_kind": kind, "label": match["label"], "value": value},
            )
            objects.append(fact)
            edges.append(
                ProjectSemanticEdge(
                    source_uid=f"segment:{segment.content_segment_uid}",
                    target_uid=fact.uid,
                    edge_type="segment_evidences_attachment_fact",
                    confidence=fact.confidence,
                    source_segment_uids=fact.source_segment_uids,
                )
            )
    return ProjectSemanticExtractionResult(
        objects=tuple(objects),
        edges=tuple(edges),
        extractor_name="literal_attachment_fact",
        extractor_version="1",
    )


def _build_object(
    *,
    segment: ProjectSourceSegment,
    text: str,
    rule: _ObjectRule,
    matched_terms: tuple[str, ...],
    dates: tuple[str, ...],
) -> ProjectSemanticObject:
    summary = _summary(text)
    attributes = {
        "matched_terms": matched_terms,
        "source_kind": segment.source_kind,
        "source_record_uid": segment.source_record_uid,
        "heading_path": segment.heading_path,
        "segment_path": segment.segment_path,
        "ordinal_index": segment.ordinal_index,
        "dates": dates,
    }
    return ProjectSemanticObject(
        uid=_object_uid(rule.object_type, segment.content_segment_uid, matched_terms),
        object_type=rule.object_type,
        title=f"{rule.title_prefix}: {summary}",
        summary=summary,
        source_segment_uids=(segment.content_segment_uid,),
        confidence=_confidence(matched_terms, segment),
        extractor_name=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
        attributes=attributes,
    )


def _source_edge(
    segment: ProjectSourceSegment,
    semantic_object: ProjectSemanticObject,
) -> ProjectSemanticEdge:
    return ProjectSemanticEdge(
        source_uid=f"segment:{segment.content_segment_uid}",
        target_uid=semantic_object.uid,
        edge_type="segment_evidences_project_object",
        confidence=semantic_object.confidence,
        source_segment_uids=(segment.content_segment_uid,),
    )


def _matched_terms(text: str, rule: _ObjectRule) -> tuple[str, ...]:
    lowered = text.casefold()
    return tuple(
        keyword for keyword in rule.keywords if _keyword_matches(lowered, keyword)
    )


def _keyword_matches(lowered_text: str, keyword: str) -> bool:
    normalized = keyword.casefold()
    if _requires_ascii_token_boundary(normalized):
        pattern = _ASCII_TOKEN_RE_CACHE.get(normalized)
        if pattern is None:
            pattern = re.compile(
                rf"(?<![A-Za-z0-9_]){re.escape(normalized)}(?![A-Za-z0-9_])"
            )
            _ASCII_TOKEN_RE_CACHE[normalized] = pattern
        return pattern.search(lowered_text) is not None
    return normalized in lowered_text


def _requires_ascii_token_boundary(keyword: str) -> bool:
    if not keyword.isascii() or any(character.isspace() for character in keyword):
        return False
    return any(character.isalnum() for character in keyword)


def _confidence(
    matched_terms: tuple[str, ...],
    segment: ProjectSourceSegment,
) -> float:
    confidence = 0.58 + min(len(matched_terms), 4) * 0.08
    if segment.heading_path:
        confidence += 0.03
    if "date" in matched_terms:
        confidence += 0.04
    return round(min(confidence, 0.94), 2)


def _object_uid(
    object_type: ProjectObjectType,
    segment_uid: str,
    matched_terms: tuple[str, ...],
) -> str:
    payload = "|".join((object_type.value, segment_uid, ",".join(matched_terms)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{object_type.value}:{digest}"


def _summary(text: str) -> str:
    if len(text) <= 96:
        return text
    return text[:93].rstrip() + "..."


def _normalize_text(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()
