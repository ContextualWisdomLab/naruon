"""Deterministic policy for preventing silent calendar double-booking.

The policy treats event time ranges as half-open intervals (inclusive start,
exclusive end) and ranks Naruon commitment statuses as confirmed > tentative >
desired. The rank is a product policy, not an iCalendar standard requirement.
No lower-priority event is mutated or displaced automatically.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal

CommitmentStatus = Literal["confirmed", "tentative", "desired"]
DecisionCode = Literal["available", "blocked", "review_required"]

_STATUS_PRIORITY: dict[str, int] = {
    "desired": 1,
    "tentative": 2,
    "confirmed": 3,
}
UTC = datetime.timezone.utc


@dataclass(frozen=True, slots=True)
class CalendarCommitment:
    """One auditable scheduling commitment considered by the conflict policy.

    Attributes:
        commitment_id: Opaque non-blank identifier used to correlate evidence.
        start_at: Inclusive timezone-aware start instant.
        end_at: Exclusive timezone-aware end instant, strictly after ``start_at``.
        status: Naruon commitment priority: confirmed, tentative, or desired.
    """

    commitment_id: str
    start_at: datetime.datetime
    end_at: datetime.datetime
    status: CommitmentStatus

    def __post_init__(self) -> None:
        """Fail closed when scheduling evidence is ambiguous or unsupported."""
        if not self.commitment_id.strip():
            raise ValueError("commitment_id must be non-blank")
        _require_timezone_aware(self.start_at)
        _require_timezone_aware(self.end_at)
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        if self.status not in _STATUS_PRIORITY:
            raise ValueError(f"Unsupported commitment status: {self.status}")


@dataclass(frozen=True, slots=True)
class CalendarConflictDecision:
    """Deterministic conflict evidence and the customer's required next action."""

    decision_code: DecisionCode
    reason_code: str
    conflicts: tuple[CalendarCommitment, ...]
    recommended_action: str
    policy_version: str = "status-weighted-v1"


def _require_timezone_aware(value: datetime.datetime) -> None:
    """Reject local/naive timestamps whose absolute instant is ambiguous."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("calendar commitment timestamps must be timezone-aware")


def _overlaps(
    left: CalendarCommitment,
    right: CalendarCommitment,
) -> bool:
    """Return whether two half-open event intervals overlap in absolute time."""
    return left.start_at < right.end_at and right.start_at < left.end_at


def _conflict_sort_key(
    commitment: CalendarCommitment,
) -> tuple[datetime.datetime, str]:
    """Sort provider evidence deterministically by UTC instant then opaque ID."""
    return commitment.start_at.astimezone(UTC), commitment.commitment_id


def evaluate_calendar_conflicts(
    proposed: CalendarCommitment,
    existing: list[CalendarCommitment] | tuple[CalendarCommitment, ...],
) -> CalendarConflictDecision:
    """Classify a proposed commitment without silently mutating existing events.

    Existing commitments with the same opaque identifier are treated as the
    current representation of the proposal rather than as a self-conflict.
    Equal or higher-priority overlaps block scheduling. Lower-priority overlaps
    require explicit human review instead of automatic displacement.

    Args:
        proposed: Candidate commitment being considered for scheduling.
        existing: Provider- or database-derived commitments in any order.

    Returns:
        A deterministic decision with sorted conflict evidence and a concrete
        next action for the customer.
    """
    conflicts = tuple(
        sorted(
            (
                commitment
                for commitment in existing
                if commitment.commitment_id != proposed.commitment_id
                and _overlaps(proposed, commitment)
            ),
            key=_conflict_sort_key,
        )
    )
    if not conflicts:
        return CalendarConflictDecision(
            decision_code="available",
            reason_code="no_overlapping_commitment",
            conflicts=(),
            recommended_action="Proceed with scheduling.",
        )

    proposed_priority = _STATUS_PRIORITY[proposed.status]
    if any(
        _STATUS_PRIORITY[commitment.status] >= proposed_priority
        for commitment in conflicts
    ):
        return CalendarConflictDecision(
            decision_code="blocked",
            reason_code="equal_or_higher_priority_conflict",
            conflicts=conflicts,
            recommended_action=(
                "Choose another time or explicitly resolve the equal/higher-priority "
                "conflict first."
            ),
        )

    return CalendarConflictDecision(
        decision_code="review_required",
        reason_code="lower_priority_conflict_requires_explicit_resolution",
        conflicts=conflicts,
        recommended_action=(
            "Review and explicitly reschedule or accept the lower-priority conflict "
            "before proceeding."
        ),
    )
