"""Grounding-quality metrics over stored project-graph extractions.

Turns the AI Hub evaluation surface from configuration counts (how many prompts
/ providers are set up) into a real, owner-scoped measurement of extraction
*grounding*: how much extracted structure is bound to source evidence, how
confident it is, and how often humans had to correct it. This is the
measurement side of the evidence-based moat — you cannot claim or improve an AI
advantage you do not measure.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ProjectGraphCorrectionRecord, ProjectGraphObjectRecord

LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class GroundingMetrics:
    total_objects: int
    grounded_objects: int
    grounding_rate: float
    mean_confidence: float
    low_confidence_objects: int
    correction_count: int
    correction_rate: float

    def as_score(self) -> int:
        """0-100 grounding score for the evaluation surface."""
        return round(self.grounding_rate * 100)


def compute_grounding_metrics(
    *,
    confidences: list[float],
    citation_counts: list[int],
    correction_count: int,
) -> GroundingMetrics:
    """Derive grounding metrics from per-object confidence and citation counts.

    Pure: no DB, so the arithmetic is unit-testable in isolation. ``confidences``
    and ``citation_counts`` are per-object and expected to be the same length;
    an object is *grounded* when it cites at least one source segment.
    """
    total = len(confidences)
    grounded = sum(1 for count in citation_counts if count > 0)
    low_confidence = sum(1 for value in confidences if value < LOW_CONFIDENCE_THRESHOLD)
    mean_confidence = (sum(confidences) / total) if total else 0.0
    return GroundingMetrics(
        total_objects=total,
        grounded_objects=grounded,
        grounding_rate=(grounded / total) if total else 0.0,
        mean_confidence=mean_confidence,
        low_confidence_objects=low_confidence,
        correction_count=correction_count,
        correction_rate=(correction_count / total) if total else 0.0,
    )


def _owner_predicates(model, user_id: str, organization_id: str | None):
    org_predicate = (
        model.organization_id.is_(None)
        if organization_id is None
        else model.organization_id == organization_id
    )
    return (model.user_id == user_id, org_predicate)


async def load_grounding_metrics(
    session: AsyncSession, *, user_id: str, organization_id: str | None
) -> GroundingMetrics:
    """Owner-scoped fetch + compute over stored project-graph extraction objects."""
    rows = (
        await session.execute(
            select(
                ProjectGraphObjectRecord.confidence,
                ProjectGraphObjectRecord.source_segment_uids,
            ).where(*_owner_predicates(ProjectGraphObjectRecord, user_id, organization_id))
        )
    ).all()
    # ponytail: loads per-object rows (bounded per owner at eval cadence); switch
    # to a SQL JSON-length aggregate if object volume outgrows a single fetch.
    confidences = [float(row.confidence) for row in rows]
    citation_counts = [len(row.source_segment_uids or []) for row in rows]

    correction_count = (
        await session.execute(
            select(
                func.count(ProjectGraphCorrectionRecord.project_graph_correction_id)
            ).where(
                *_owner_predicates(
                    ProjectGraphCorrectionRecord, user_id, organization_id
                )
            )
        )
    ).scalar_one()

    return compute_grounding_metrics(
        confidences=confidences,
        citation_counts=citation_counts,
        correction_count=int(correction_count or 0),
    )
