"""Immutable provider fixture shared with the LineageWeave consumer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.calendar_projection import CalendarProjectionPage

_EXPECTED_FIXTURE_SHA256 = (
    "7efe5799a942779c21bf123685daa0cf201063665dd84a377214e4325bf6039d"
)


def test_calendar_projection_fixture_is_immutable_and_runtime_valid() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "contracts"
        / "naruon-calendar-projection-v1.example.json"
    )
    fixture_bytes = fixture_path.read_bytes()

    assert hashlib.sha256(fixture_bytes).hexdigest() == _EXPECTED_FIXTURE_SHA256
    page = CalendarProjectionPage.model_validate(json.loads(fixture_bytes))
    assert page.projection_revision == "projection_fixture_001"
    assert page.events[0].occurrence_reference == "occurrence_fixture_001"
