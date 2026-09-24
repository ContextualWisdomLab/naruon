"""CodSpeed performance benchmarks for CPU-bound backend hot paths.

These benchmarks require ``pytest-codspeed`` (backend dev dependency group) and
are skipped when the plugin is not installed. Run them with:

    uv run pytest tests/benchmarks --codspeed
"""

import datetime
from email.message import EmailMessage
from pathlib import Path

import pytest

pytest.importorskip("pytest_codspeed")

from rankweave import FusionSettings  # noqa: E402

from services.access_policy import (  # noqa: E402
    AccessRequest,
    ResourcePolicy,
    evaluate_access,
)
from services.calendar_conflict_ics import (  # noqa: E402
    evaluate_calendar_conflicts_from_ics,
)
from services.email_dedupe_service import (  # noqa: E402
    EmailDedupeCandidate,
    candidate_strong_fingerprint,
)
from services.email_parser import parse_eml_bytes  # noqa: E402
from services.hybrid_retrieval import (  # noqa: E402
    fuse_channel_scores,
    normalize_search_text,
)
from services.text_safety import contains_html_markup, strip_html_markup  # noqa: E402
from services.threading_service import extract_reference_ids  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CALENDAR_FIXTURES_DIR = FIXTURES_DIR / "calendar"


def _build_multipart_email(paragraphs: int) -> bytes:
    msg = EmailMessage()
    msg["Message-ID"] = "<bench-root@example.com>"
    msg["From"] = "Alice Example <alice@example.com>"
    msg["To"] = "Bob Example <bob@example.com>, Carol <carol@example.com>"
    msg["Subject"] = "Re: Quarterly plan and budget review"
    msg["Date"] = "Mon, 27 Apr 2026 10:05:00 +0000"
    msg["In-Reply-To"] = "<thread-root@example.com>"
    msg["References"] = " ".join(f"<ref-{i}@example.com>" for i in range(20))
    plain = "\n\n".join(
        f"Paragraph {i}: discussing the quarterly roadmap, budget and hiring plan."
        for i in range(paragraphs)
    )
    html = "".join(
        f"<p>Paragraph <b>{i}</b>: discussing the <a href='https://example.com/{i}'>"
        "quarterly roadmap</a>, budget &amp; hiring plan.</p>"
        for i in range(paragraphs)
    )
    msg.set_content(plain)
    msg.add_alternative(f"<html><body>{html}</body></html>", subtype="html")
    msg.add_attachment(
        "name,value\n" + "\n".join(f"row{i},{i}" for i in range(50)),
        subtype="csv",
        filename="report.csv",
    )
    return msg.as_bytes()


MULTIPART_EMAIL = _build_multipart_email(paragraphs=40)
THREAD_REPLY_EMAIL = (FIXTURES_DIR / "threading-basic-02-reply.eml").read_bytes()

HTML_DOCUMENT = (
    "<html><head><style>p { color: red; }</style>"
    "<script>alert('x')</script></head><body>"
    + "".join(
        f"<div class='row'><p>Hello <b>user {i}</b> &lt;user{i}@example.com&gt; "
        f"&amp; welcome to <a href='https://naruon.net/{i}'>Naruon</a>.</p>"
        "<!-- tracking comment --><br/></div>"
        for i in range(100)
    )
    + "</body></html>"
)
PLAIN_TEXT_DOCUMENT = "\n".join(
    f"Line {i}: plain text body without any markup at all." for i in range(200)
)

REFERENCES_HEADER = "\r\n ".join(
    f"<message-{i % 150}@\r\n mail.example.com>" for i in range(300)
)


@pytest.mark.benchmark
def test_parse_multipart_email(benchmark):
    result = benchmark(parse_eml_bytes, MULTIPART_EMAIL)
    assert result["message_id"]


@pytest.mark.benchmark
def test_parse_thread_reply_email(benchmark):
    result = benchmark(parse_eml_bytes, THREAD_REPLY_EMAIL)
    assert result["subject"] == "Re: Quarterly plan"


@pytest.mark.benchmark
def test_strip_html_markup(benchmark):
    text = benchmark(strip_html_markup, HTML_DOCUMENT)
    assert "Naruon" in text


@pytest.mark.benchmark
def test_strip_html_markup_plain_text(benchmark):
    text = benchmark(strip_html_markup, PLAIN_TEXT_DOCUMENT)
    assert text


@pytest.mark.benchmark
def test_contains_html_markup(benchmark):
    assert benchmark(contains_html_markup, HTML_DOCUMENT) is True


@pytest.mark.benchmark
def test_extract_reference_ids(benchmark):
    refs = benchmark(extract_reference_ids, REFERENCES_HEADER)
    assert len(refs) == 150


@pytest.mark.benchmark
def test_email_strong_fingerprints(benchmark):
    base_date = datetime.datetime(2026, 4, 27, 10, 0, tzinfo=datetime.timezone.utc)
    candidates = [
        EmailDedupeCandidate(
            candidate_key=f"candidate-{i}",
            message_id=f"<msg-{i}@example.com>",
            sender=f"sender{i}@example.com",
            recipients="team@example.com",
            subject=f"Status update {i}",
            date=base_date + datetime.timedelta(minutes=i),
            body="Body content for the status update. " * 30,
        )
        for i in range(200)
    ]

    def run():
        return [candidate_strong_fingerprint(c) for c in candidates]

    fingerprints = benchmark(run)
    assert len(set(fingerprints)) == len(candidates)


@pytest.mark.benchmark
def test_hybrid_retrieval_fusion(benchmark):
    settings = FusionSettings()
    queries = [
        "  Quarterly   PLAN review\tfor  Naruon  workspace  ",
        "예산 검토 회의 일정",
        "Budget & hiring — Q3 roadmap",
    ] * 20
    channel_rows = [
        (i / 500, 0.2 + (i % 50) / 100, {"dense": i + 1, "lexical": (i * 7) % 500 + 1})
        for i in range(500)
    ]

    def run():
        normalized = [normalize_search_text(q) for q in queries]
        scores = [
            fuse_channel_scores(
                word_similarity_score=ws,
                cosine_distance=cd,
                channel_ranks=ranks,
                settings=settings,
            )
            for ws, cd, ranks in channel_rows
        ]
        return normalized, scores

    normalized, scores = benchmark(run)
    assert len(scores) == len(channel_rows)
    assert normalized[0]


def _build_existing_calendar(events: int) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Naruon//Calendar Benchmark//EN",
    ]
    base = datetime.datetime(2026, 8, 1, 8, 0, tzinfo=datetime.timezone.utc)
    statuses = ("CONFIRMED", "TENTATIVE", "CANCELLED")
    for i in range(events):
        start = base + datetime.timedelta(hours=i * 3)
        end = start + datetime.timedelta(hours=1)
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:bench-event-{i}",
                "DTSTAMP:20260801T000000Z",
                f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
                f"DTEND:{end:%Y%m%dT%H%M%SZ}",
                f"SUMMARY:Benchmark event {i}",
                f"STATUS:{statuses[i % len(statuses)]}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@pytest.mark.benchmark
def test_calendar_conflicts_from_ics(benchmark):
    proposed = (CALENDAR_FIXTURES_DIR / "proposed-confirmed-1000z.ics").read_text()
    existing = _build_existing_calendar(events=100)
    decision = benchmark(evaluate_calendar_conflicts_from_ics, proposed, existing)
    assert decision is not None


@pytest.mark.benchmark
def test_evaluate_access_policy(benchmark):
    roles = (
        "member",
        "group_admin",
        "organization_admin",
        "tenant_admin",
        "platform_admin",
        "system_admin",
    )
    requests = [
        AccessRequest(
            user_id=f"user-{i}",
            role=roles[i % len(roles)],
            organization_id=f"org-{i % 3}",
            group_ids=(f"group-{i % 5}", f"group-{i % 7}"),
            data_region="kr" if i % 4 else "eu",
            consent_scopes=("email.read", "calendar.read"),
            workspace_id=f"ws-{i % 2}",
        )
        for i in range(300)
    ]
    resource = ResourcePolicy(
        owner_id="user-1",
        organization_id="org-1",
        permitted_roles=("member", "group_admin", "organization_admin"),
        permitted_group_ids=("group-1", "group-3"),
        data_region="kr",
        required_consent_scopes=("email.read",),
        workspace_id="ws-1",
    )

    def run():
        return [evaluate_access(request, resource) for request in requests]

    decisions = benchmark(run)
    assert any(d.allowed for d in decisions)
