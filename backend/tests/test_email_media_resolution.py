"""Tests for deterministic email inline-media resolution."""

from __future__ import annotations

import base64

import pytest

from services import email_media_resolution as media


def _png(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"payload"
    )


def _gif(width: int = 2, height: int = 3) -> bytes:
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little") + b"payload"


def _related_message(
    html_body: str,
    image_parts: list[tuple[str, str, bytes]],
) -> bytes:
    lines = [
        "MIME-Version: 1.0",
        'Content-Type: multipart/related; boundary="rel"; type="text/html"',
        "",
        "--rel",
        'Content-Type: text/html; charset="utf-8"',
        "Content-Transfer-Encoding: 8bit",
        "",
        html_body,
    ]
    raw = "\r\n".join(lines).encode("utf-8") + b"\r\n"
    for content_id, content_type, payload in image_parts:
        raw += (
            b"--rel\r\n"
            + f"Content-Type: {content_type}\r\n".encode()
            + f"Content-ID: <{content_id}>\r\n".encode()
            + b"Content-Disposition: inline\r\n"
            + b"Content-Transfer-Encoding: base64\r\n\r\n"
            + base64.b64encode(payload)
            + b"\r\n"
        )
    return raw + b"--rel--\r\n"


def _html_only_message(html_body: str) -> bytes:
    return (
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Transfer-Encoding: 8bit\r\n\r\n"
        + html_body.encode("utf-8")
    )


def test_resolves_cid_inside_related_scope_with_exact_source_span() -> None:
    html_body = '<p>before<img alt="logo" src="cid:logo%40example.test">after</p>'
    result = media.resolve_email_media(
        _related_message(html_body, [("logo@example.test", "image/png", _png(1, 1))])
    )

    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.llm_safe is True
    assert artifact.visual_classification == "tracking_candidate"
    assert artifact.pixel_width == 1
    assert artifact.pixel_height == 1
    assert artifact.content_type == "image/png"
    assert artifact.payload_bytes == _png(1, 1)

    cid_occurrence = next(
        item for item in result.occurrences if item.occurrence_kind == "html_cid"
    )
    assert cid_occurrence.content_id == "logo@example.test"
    assert cid_occurrence.artifact_id == artifact.artifact_id
    assert cid_occurrence.resolution_status == "resolved"
    assert cid_occurrence.reason_code == "cid_target_resolved"
    assert html_body[cid_occurrence.source_start : cid_occurrence.source_end] == (
        "cid:logo%40example.test"
    )
    assert result.remote_fetch_policy == "disabled"


def test_remote_images_are_recorded_without_fetching() -> None:
    html_body = '<img src="https://tracker.example/pixel.png?u=1">'
    result = media.resolve_email_media(_html_only_message(html_body))

    assert result.artifacts == ()
    assert len(result.occurrences) == 1
    occurrence = result.occurrences[0]
    assert occurrence.occurrence_kind == "html_remote"
    assert occurrence.resolution_status == "remote_blocked"
    assert occurrence.reason_code == "remote_fetch_disabled"
    assert occurrence.normalized_reference == "https://tracker.example/pixel.png?u=1"


def test_data_image_is_bounded_and_resolved_locally() -> None:
    encoded = base64.b64encode(_gif(4, 5)).decode()
    html_body = f"<img src='data:image/gif;base64,{encoded}'>"
    result = media.resolve_email_media(_html_only_message(html_body))

    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.content_type == "image/gif"
    assert artifact.byte_length == len(_gif(4, 5))
    assert artifact.visual_classification == "unclassified"
    assert artifact.pixel_width == 4
    assert artifact.pixel_height == 5
    occurrence = result.occurrences[0]
    assert occurrence.occurrence_kind == "html_data"
    assert occurrence.resolution_status == "resolved"
    assert occurrence.artifact_id == artifact.artifact_id


def test_identical_mime_images_deduplicate_artifact_but_preserve_occurrences() -> None:
    payload = _png()
    result = media.resolve_email_media(
        _related_message(
            "<p>no references</p>",
            [
                ("signature-one@example.test", "image/png", payload),
                ("signature-two@example.test", "image/png", payload),
            ],
        )
    )

    assert len(result.artifacts) == 1
    mime_occurrences = [
        item for item in result.occurrences if item.occurrence_kind == "mime_part"
    ]
    assert len(mime_occurrences) == 2
    assert {item.artifact_id for item in mime_occurrences} == {
        result.artifacts[0].artifact_id
    }
    assert {item.content_id for item in mime_occurrences} == {
        "signature-one@example.test",
        "signature-two@example.test",
    }


def test_unsupported_and_mismatched_mime_images_are_not_llm_safe() -> None:
    result = media.resolve_email_media(
        _related_message(
            "<p>images</p>",
            [
                ("vector@example.test", "image/svg+xml", b"<svg></svg>"),
                ("mismatch@example.test", "image/png", _gif()),
            ],
        )
    )

    assert len(result.artifacts) == 2
    assert {artifact.reason_code for artifact in result.artifacts} == {
        "unsupported_image_content_type",
        "image_content_type_mismatch",
    }
    assert all(artifact.llm_safe is False for artifact in result.artifacts)
    assert all(artifact.payload_bytes == b"" for artifact in result.artifacts)


def test_cid_must_resolve_in_nearest_multipart_related_scope() -> None:
    outside = media.resolve_email_media(_html_only_message('<img src="cid:x@example.test">'))
    occurrence = outside.occurrences[0]
    assert occurrence.reason_code == "cid_outside_multipart_related"
    assert occurrence.artifact_id is None

    missing = media.resolve_email_media(
        _related_message('<img src="cid:missing@example.test">', [])
    )
    assert missing.occurrences[0].reason_code == "cid_target_missing"


def test_duplicate_content_id_fails_closed_for_human_review() -> None:
    result = media.resolve_email_media(
        _related_message(
            '<img src="cid:duplicate@example.test">',
            [
                ("duplicate@example.test", "image/png", _png()),
                ("duplicate@example.test", "image/gif", _gif()),
            ],
        )
    )
    cid_occurrence = next(
        item for item in result.occurrences if item.occurrence_kind == "html_cid"
    )
    assert cid_occurrence.resolution_status == "review_required"
    assert cid_occurrence.reason_code == "cid_target_ambiguous"
    assert cid_occurrence.artifact_id is None


def test_cid_target_that_is_not_llm_safe_remains_visible() -> None:
    result = media.resolve_email_media(
        _related_message(
            '<img src="cid:vector@example.test">',
            [("vector@example.test", "image/svg+xml", b"<svg></svg>")],
        )
    )
    cid_occurrence = next(
        item for item in result.occurrences if item.occurrence_kind == "html_cid"
    )
    assert cid_occurrence.resolution_status == "unsafe_media"
    assert cid_occurrence.reason_code == "cid_target_not_llm_safe"
    assert cid_occurrence.artifact_id == result.artifacts[0].artifact_id


@pytest.mark.parametrize(
    ("reference", "expected_reason"),
    [
        ("cid:", "invalid_cid_reference"),
        ("cid:bad%0Aid", "invalid_cid_reference"),
        ("data:image/png,AAAA", "unsupported_data_image_encoding"),
        ("data:image/svg+xml;base64,PHN2Zz4=", "unsupported_data_image_content_type"),
        ("data:image/png;base64,%%%", "invalid_data_image_base64"),
        ("relative/image.png", "unsupported_image_reference"),
        ("http://[broken", "unsupported_image_reference"),
    ],
)
def test_invalid_or_unsupported_references_are_explicit(
    reference: str, expected_reason: str
) -> None:
    result = media.resolve_email_media(_html_only_message(f'<img src="{reference}">'))
    assert result.occurrences[0].resolution_status == "unresolved"
    assert result.occurrences[0].reason_code == expected_reason


def test_html_entities_and_self_closing_img_preserve_raw_span() -> None:
    html_body = '<img src="cid:logo&#64;example.test" />'
    result = media.resolve_email_media(
        _related_message(html_body, [("logo@example.test", "image/png", _png())])
    )
    cid_occurrence = next(
        item for item in result.occurrences if item.occurrence_kind == "html_cid"
    )
    assert cid_occurrence.normalized_reference == "cid:logo@example.test"
    assert html_body[cid_occurrence.source_start : cid_occurrence.source_end] == (
        "cid:logo&#64;example.test"
    )


def test_img_without_src_and_non_img_tags_do_not_create_occurrences() -> None:
    result = media.resolve_email_media(
        _html_only_message('<a src="https://example.test/a">x</a><img alt="none">')
    )
    assert result.occurrences == ()


def test_non_image_mime_parts_are_ignored() -> None:
    raw = (
        b"MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=m\r\n\r\n"
        b"--m\r\nContent-Type: application/pdf\r\nContent-ID: <doc@example.test>\r\n\r\n"
        b"%PDF-1.7\r\n--m--\r\n"
    )
    result = media.resolve_email_media(raw)
    assert result.artifacts == ()
    assert result.occurrences == ()


def test_public_input_and_message_size_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(TypeError, match="raw_message must be bytes"):
        media.resolve_email_media("not bytes")  # type: ignore[arg-type]

    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_MESSAGE_BYTES", 3)
    with pytest.raises(ValueError, match="email_media_message_size_limit_exceeded"):
        media.resolve_email_media(b"four")


def test_html_reference_and_artifact_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_REFERENCES", 1)
    with pytest.raises(ValueError, match="email_media_reference_limit_exceeded"):
        media.resolve_email_media(_html_only_message('<img src="a"><img src="b">'))

    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_REFERENCES", 500)
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_ARTIFACTS", 1)
    with pytest.raises(ValueError, match="email_media_artifact_limit_exceeded"):
        media.resolve_email_media(
            _related_message(
                "<p>two</p>",
                [
                    ("one@example.test", "image/png", _png()),
                    ("two@example.test", "image/gif", _gif()),
                ],
            )
        )


def test_html_and_data_image_size_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_HTML_CHARS", 3)
    with pytest.raises(ValueError, match="email_media_html_size_limit_exceeded"):
        media.resolve_email_media(_html_only_message("<p>x</p>"))

    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_HTML_CHARS", 2_000_000)
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_IMAGE_BYTES", 2)
    oversized_data = base64.b64encode(_png()).decode()
    result = media.resolve_email_media(
        _html_only_message(f'<img src="data:image/png;base64,{oversized_data}">')
    )
    assert result.occurrences[0].reason_code == "data_image_size_limit_exceeded"


def test_mime_image_size_limit_keeps_auditable_non_safe_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_IMAGE_BYTES", 4)
    result = media.resolve_email_media(
        _related_message("<p>x</p>", [("large@example.test", "image/png", _png())])
    )
    assert result.artifacts[0].llm_safe is False
    assert result.artifacts[0].reason_code == "image_size_limit_exceeded"
    assert result.artifacts[0].payload_bytes == b""


def test_jpeg_webp_and_image_jpg_alias_are_supported() -> None:
    jpeg = b"\xff\xd8\xff" + b"jpeg-data"
    webp = b"RIFF\x08\x00\x00\x00WEBPdata"
    result = media.resolve_email_media(
        _related_message(
            "<p>x</p>",
            [
                ("jpeg@example.test", "image/jpg", jpeg),
                ("webp@example.test", "image/webp", webp),
            ],
        )
    )
    assert {artifact.content_type for artifact in result.artifacts} == {
        "image/jpeg",
        "image/webp",
    }
    assert all(artifact.llm_safe for artifact in result.artifacts)


def test_missing_and_malformed_content_ids_are_not_resolution_authority() -> None:
    raw = _related_message('<img src="cid:target@example.test">', [])
    raw = raw.replace(
        b"--rel--\r\n",
        b"--rel\r\nContent-Type: image/png\r\nContent-ID: <bad\x01id>\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        + base64.b64encode(_png())
        + b"\r\n--rel--\r\n",
    )
    result = media.resolve_email_media(raw)
    cid_occurrence = next(
        item for item in result.occurrences if item.occurrence_kind == "html_cid"
    )
    assert cid_occurrence.reason_code == "cid_target_missing"


def test_data_helper_rejects_malformed_data_url_and_postdecode_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="invalid_data_image"):
        media._decode_data_image("not-data")

    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_IMAGE_BYTES", 3)
    encoded = base64.b64encode(b"four").decode()
    with pytest.raises(ValueError, match="data_image_size_limit_exceeded"):
        media._decode_data_image(f"data:image/png;base64,{encoded}")


def test_content_helpers_cover_empty_and_unknown_inputs() -> None:
    assert media._normalize_content_id(None) is None
    assert media._normalize_content_id(" <x@example.test> ") == "x@example.test"
    assert media._normalize_content_id("") is None
    assert media._normalize_content_type("") == ""
    assert media._infer_image_content_type(b"not-image") is None
    assert media._image_dimensions("image/jpeg", b"jpeg") is None
    assert media._line_offsets("one\ntwo\n") == [0, 4, 8]
