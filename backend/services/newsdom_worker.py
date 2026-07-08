"""Background worker glue for NewsDOM PDF DOM recognition.

Attachments and workspace documents whose PDF recognition was deferred at
import time are processed here: the sidecar is called (via
:mod:`services.newsdom_pdf_recognition`) and the returned tree is landed into
``parse_content`` (for embeddings) and, for attachments, the
``content_nodes`` / ``content_segments`` graph.

The apply functions are deliberately session-free so they can be unit tested
with in-memory model instances and a mocked NewsDOM client.
"""

from __future__ import annotations

from db.models import (
    Attachment,
    ContentNodeRecord,
    ContentSegmentRecord,
    Document,
    Email,
)
from services.content_graph import ParseResult
from services.newsdom_client import request_pdf_dom
from services.newsdom_pdf_recognition import (
    PDF_DOM_RECOGNITION_PARSED_STATUS,
    PDF_PARSE_CONTENT_TYPE,
    PDF_PARSER_KEY,
    NewsdomRuntimeConfig,
    ParseRequestFn,
    PdfDomRecognitionRecords,
    recognize_pdf_dom,
)


def _append_parse_result_to_attachment(
    *,
    email: Email,
    attachment: Attachment,
    parse_result: ParseResult,
) -> None:
    node_records_by_uid: dict[str, ContentNodeRecord] = {}
    for parsed_node in parse_result.nodes:
        node_record = ContentNodeRecord(
            content_node_uid=parsed_node.content_node_uid,
            source_kind=parsed_node.source_kind,
            source_record_uid=parsed_node.source_record_uid,
            parent_node_uid=parsed_node.parent_node_uid,
            node_kind=parsed_node.node_kind,
            node_path=parsed_node.node_path,
            ordinal_index=parsed_node.ordinal_index,
            display_label=parsed_node.display_label,
            safe_text_content=parsed_node.safe_text_content,
            content_hash=parsed_node.content_hash,
        )
        email.content_nodes.append(node_record)
        attachment.content_nodes.append(node_record)
        node_records_by_uid[parsed_node.content_node_uid] = node_record

    for parsed_segment in parse_result.segments:
        node_record = node_records_by_uid.get(parsed_segment.content_node_uid)
        segment_record = ContentSegmentRecord(
            content_segment_uid=parsed_segment.content_segment_uid,
            source_kind=parsed_segment.source_kind,
            source_record_uid=parsed_segment.source_record_uid,
            segment_kind=parsed_segment.segment_kind,
            segment_path=parsed_segment.segment_path,
            ordinal_index=parsed_segment.ordinal_index,
            heading_path=parsed_segment.heading_path,
            safe_text_content=parsed_segment.safe_text_content,
            content_hash=parsed_segment.content_hash,
            word_count=parsed_segment.word_count,
        )
        if node_record is not None:
            node_record.segments.append(segment_record)
        email.content_segments.append(segment_record)
        attachment.content_segments.append(segment_record)


def apply_recognition_to_attachment(
    *,
    email: Email,
    attachment: Attachment,
    records: PdfDomRecognitionRecords,
) -> None:
    """Land recognized PDF DOM records onto an attachment (text + graph)."""
    attachment.parse_content = records.parse_text
    attachment.content = records.parse_text
    attachment.parse_content_type = PDF_PARSE_CONTENT_TYPE
    attachment.parser_key = PDF_PARSER_KEY
    attachment.parse_status = PDF_DOM_RECOGNITION_PARSED_STATUS
    attachment.parse_error_code = None
    _append_parse_result_to_attachment(
        email=email,
        attachment=attachment,
        parse_result=records.parse_result,
    )


def apply_recognition_to_document(
    *,
    document: Document,
    records: PdfDomRecognitionRecords,
) -> None:
    """Land recognized PDF text onto a workspace document (mirrors the HWP
    conversion worker: content + status, no content graph rows)."""
    document.document_content = records.parse_text
    document.document_status = PDF_DOM_RECOGNITION_PARSED_STATUS


async def recognize_attachment_pdf(
    *,
    email: Email,
    attachment: Attachment,
    pdf_bytes: bytes,
    config: NewsdomRuntimeConfig | None,
    source_record_uid: str,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> PdfDomRecognitionRecords:
    records = await recognize_pdf_dom(
        config=config,
        pdf_bytes=pdf_bytes,
        filename=attachment.filename or "attachment.pdf",
        source_kind="attachment",
        source_record_uid=source_record_uid,
        display_name=attachment.filename or "",
        request_fn=request_fn,
    )
    apply_recognition_to_attachment(email=email, attachment=attachment, records=records)
    return records


async def recognize_document_pdf(
    *,
    document: Document,
    pdf_bytes: bytes,
    config: NewsdomRuntimeConfig | None,
    request_fn: ParseRequestFn = request_pdf_dom,
) -> PdfDomRecognitionRecords:
    records = await recognize_pdf_dom(
        config=config,
        pdf_bytes=pdf_bytes,
        filename=document.document_name or "document.pdf",
        source_kind="workspace_document",
        source_record_uid=document.document_id,
        display_name=document.document_name or "",
        request_fn=request_fn,
    )
    apply_recognition_to_document(document=document, records=records)
    return records
