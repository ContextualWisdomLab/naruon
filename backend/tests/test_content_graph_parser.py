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
        <p>Hello<br><strong>team</strong></p>
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
    assert "/document[1]/html[1]/body[1]/p[1]/br[1]" in {
        node.node_path for node in result.nodes
    }
    assert not any("/br[1]/strong[1]" in node.node_path for node in result.nodes)
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


def test_json_content_builds_scalar_segments_with_member_paths():
    content = """{
        "project": "Launch",
        "risk": {"level": "high"},
        "tasks": ["Parse JSON", "Store segments"]
    }"""

    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-json",
        content=content,
        content_type="application/json",
        display_name="status.json",
    )

    assert [segment.segment_kind for segment in result.segments] == [
        "json_value",
        "json_value",
        "json_value",
        "json_value",
    ]
    assert [segment.safe_text_content for segment in result.segments] == [
        "project: Launch",
        "level: high",
        "tasks[1]: Parse JSON",
        "tasks[2]: Store segments",
    ]
    assert [segment.heading_path for segment in result.segments] == [
        "project",
        "risk > level",
        "tasks > tasks[1]",
        "tasks > tasks[2]",
    ]


def test_csv_content_builds_header_and_row_segments():
    content = "name,status\nLaunch,Ready\nGraph,Blocked\n"

    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-csv",
        content=content,
        content_type="text/csv",
        display_name="status.csv",
    )

    assert [segment.segment_kind for segment in result.segments] == [
        "table_header",
        "table_row",
        "table_row",
    ]
    assert [segment.safe_text_content for segment in result.segments] == [
        "name, status",
        "name=Launch; status=Ready",
        "name=Graph; status=Blocked",
    ]
    assert [segment.segment_path for segment in result.segments] == [
        "/document[1]/table[1]/row[1]",
        "/document[1]/table[1]/row[2]",
        "/document[1]/table[1]/row[3]",
    ]


def test_xml_content_uses_defused_parser_and_element_text_segments():
    content = "<root><title>Launch</title><item>Ship graph</item></root>"

    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-xml",
        content=content,
        content_type="application/xml",
        display_name="status.xml",
    )

    assert [segment.segment_kind for segment in result.segments] == [
        "xml_text",
        "xml_text",
    ]
    assert [segment.safe_text_content for segment in result.segments] == [
        "Launch",
        "Ship graph",
    ]
    assert [segment.heading_path for segment in result.segments] == [
        "root > title",
        "root > item",
    ]


def test_calendar_content_unfolds_lines_into_property_segments():
    content = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "BEGIN:VEVENT",
            "SUMMARY:Launch review",
            "DESCRIPTION:Line one",
            " continued",
            "DTSTART:20260711T090000Z",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )

    result = parse_content(
        source_kind="attachment",
        source_record_uid="attachment-ics",
        content=content,
        content_type="text/calendar",
        display_name="invite.ics",
    )

    assert [segment.segment_kind for segment in result.segments] == [
        "calendar_property",
        "calendar_property",
        "calendar_property",
    ]
    assert [segment.safe_text_content for segment in result.segments] == [
        "SUMMARY: Launch review",
        "DESCRIPTION: Line onecontinued",
        "DTSTART: 20260711T090000Z",
    ]
    assert all(segment.heading_path == "VEVENT" for segment in result.segments)


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
