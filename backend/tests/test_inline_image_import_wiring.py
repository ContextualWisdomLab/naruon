"""Verify inline image evidence reaches persistence and search surfaces."""

import base64
import datetime

from services.email_import_service import _build_email_object
from services.inline_image_service import extract_inline_image_sources


def test_build_email_object_persists_and_indexes_inline_image_source():
    image_payload = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + b"\x00\x00\x00\x11\x00\x00\x00\x13\x08\x06\x00\x00\x00"
    )
    source = extract_inline_image_sources(
        "<html><body><img src='data:image/png;base64,"
        + base64.b64encode(image_payload).decode("ascii")
        + "'></body></html>"
    )[0]

    email, attachment_count = _build_email_object(
        parsed={
            "body": "Image context",
            "body_content_type": "text/html",
            "body_parse_content": "<html><body>Image context</body></html>",
            "attachments": [],
            "inline_images": [source.as_payload()],
            "sender": "sender@example.test",
            "recipients": "recipient@example.test",
            "subject": "Inline image evidence",
        },
        user_id="user-inline-image",
        organization_id="organization-inline-image",
        message_id="<inline-image-import@test>",
        thread_id="<inline-image-import@test>",
        fingerprint="inline-image-fingerprint",
        persisted_date=datetime.datetime(
            2026, 8, 21, tzinfo=datetime.timezone.utc
        ),
        attachment_payloads=[],
        fitted_embeddings=[],
    )

    assert attachment_count == 0
    assert len(email.image_sources) == 1
    assert email.image_sources[0].source_kind == "inline_html_image"
    assert email.image_sources[0].source_locator_value.endswith("img[1]")
    assert email.image_sources[0].pixel_width == 17
    assert email.image_sources[0].pixel_height == 19
    assert any(
        segment.source_kind == "inline_image"
        and "Inline image evidence" in segment.safe_text_content
        for segment in email.content_segments
    )
