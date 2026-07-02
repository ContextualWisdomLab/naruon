from services.content_graph import parse_content


def test_plain_text_content_builds_document_node_and_paragraph_segments():
    content = "First paragraph.\n\nSecond paragraph has two lines\nthat wrap."

    result = parse_content(
        source_kind="email_body",
        source_record_uid="email-1",
        content=content,
        content_type="text/plain",
        display_name="body",
    )
    repeated = parse_content(
        source_kind="email_body",
        source_record_uid="email-1",
        content=content,
        content_type="text/plain",
        display_name="body",
    )

    assert [segment.safe_text_content for segment in result.segments] == [
        "First paragraph.",
        "Second paragraph has two lines that wrap.",
    ]
    assert [segment.segment_path for segment in result.segments] == [
        "/document[1]/paragraph[1]",
        "/document[1]/paragraph[2]",
    ]
    assert all(segment.segment_kind == "paragraph" for segment in result.segments)
    assert result.nodes[0].node_kind == "document"
    assert result.nodes[0].node_path == "/document[1]"
    assert result.nodes[1].parent_node_uid == result.nodes[0].content_node_uid
    assert (
        result.segments[0].content_segment_uid
        == repeated.segments[0].content_segment_uid
    )
    assert result.source_content_hash == repeated.source_content_hash


def test_html_content_preserves_block_dom_paths_and_safe_heading_context():
    html = """
    <html>
      <body>
        <h1>Launch</h1>
        <p>Hello <strong>team</strong></p>
        <script>alert('bad')</script>
        <style>body { color: red; }</style>
        <div><p>Second <img src=x onerror=alert(1)> paragraph</p></div>
      </body>
    </html>
    """

    result = parse_content(
        source_kind="email_body",
        source_record_uid="email-2",
        content=html,
        content_type="text/html",
        display_name="body.html",
    )

    assert [segment.safe_text_content for segment in result.segments] == [
        "Launch",
        "Hello team",
        "Second paragraph",
    ]
    assert [segment.segment_kind for segment in result.segments] == [
        "heading",
        "paragraph",
        "paragraph",
    ]
    assert result.segments[1].heading_path == "Launch"
    assert result.segments[2].heading_path == "Launch"
    assert "/document[1]/html[1]/body[1]/h1[1]" in {
        node.node_path for node in result.nodes
    }
    assert "/document[1]/html[1]/body[1]/div[1]/p[1]" in {
        node.node_path for node in result.nodes
    }
    joined = " ".join(segment.safe_text_content for segment in result.segments).lower()
    assert "<" not in joined
    assert "script" not in joined
    assert "alert" not in joined
    assert "onerror" not in joined


def test_markdown_content_attaches_heading_path_to_paragraph_segments():
    content = "# Project Alpha\n\nFirst paragraph.\n\n## Risk\n\nSecond paragraph."

    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-1",
        content=content,
        content_type="text/markdown",
        display_name="plan.md",
    )

    assert [segment.segment_kind for segment in result.segments] == [
        "heading",
        "paragraph",
        "heading",
        "paragraph",
    ]
    assert [segment.safe_text_content for segment in result.segments] == [
        "Project Alpha",
        "First paragraph.",
        "Risk",
        "Second paragraph.",
    ]
    assert [segment.heading_path for segment in result.segments] == [
        "Project Alpha",
        "Project Alpha",
        "Project Alpha > Risk",
        "Project Alpha > Risk",
    ]
    assert [segment.segment_path for segment in result.segments] == [
        "/document[1]/h1[1]",
        "/document[1]/paragraph[1]",
        "/document[1]/h2[1]",
        "/document[1]/paragraph[2]",
    ]


def test_unknown_content_type_uses_safe_text_fallback():
    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-2",
        content="<b>Visible</b><script>alert('bad')</script>",
        content_type="application/octet-stream",
        display_name="payload.bin",
    )

    assert [segment.safe_text_content for segment in result.segments] == ["Visible"]
    assert result.segments[0].segment_path == "/document[1]/paragraph[1]"
