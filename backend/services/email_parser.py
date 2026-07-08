from email import message_from_binary_file, message_from_bytes, policy
from email.message import Message
from pathlib import Path
import datetime
from email.utils import formataddr, getaddresses
from email.utils import parsedate_to_datetime
from typing import NotRequired, TypedDict
from .attachment_parser import parse_email_attachment
from .exceptions import EmailParseError
from .text_safety import strip_html_markup


class EmailData(TypedDict):
    """Parsed email data structure."""

    message_id: str
    thread_id: str | None
    sender: str
    reply_to: str | None
    recipients: str
    subject: str
    in_reply_to: str | None
    references: str | None
    date: datetime.datetime
    body: str
    body_content_type: NotRequired[str]
    body_parse_content: NotRequired[str]
    attachments: list[dict]


def _sanitize_nul(text: str) -> str:
    """Removes NUL characters from strings, which are invalid in PostgreSQL text fields."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    return text.replace("\x00", "")


def _sanitize_display_text(text: str) -> str:
    return strip_html_markup(_sanitize_nul(text))


def _safe_formataddr(display_name: str, address: str) -> str:
    """RFC-format an address, falling back to a plain rendering when the
    addr-spec cannot be encoded.

    ``email.utils.formataddr`` raises ``UnicodeEncodeError`` on a non-ASCII
    addr-spec (e.g. an IDN domain, or an RFC 2047 encoded-word display name that
    ``getaddresses`` parses as the address itself). Left unguarded this escapes
    ``parse_eml_bytes`` -- whose declared contract is ``EmailParseError`` -- and
    crashes email ingest on very common inbound mail. Fall back instead of
    raising. Found by ``backend/fuzz`` (test_email_parser_fuzz).
    """
    try:
        return formataddr((display_name, address))
    except (UnicodeEncodeError, ValueError):
        if display_name and address:
            return f"{display_name} <{address}>"
        return address or display_name


def _sanitize_address_display_text(text: str) -> str:
    sanitized_parts: list[str] = []
    for display_name, address in getaddresses([text]):
        safe_display_name = _sanitize_display_text(display_name).strip()
        safe_address = _sanitize_nul(address).strip()
        if safe_address:
            sanitized_parts.append(
                _safe_formataddr(safe_display_name, safe_address)
            )
        elif safe_display_name:
            sanitized_parts.append(safe_display_name)
    if sanitized_parts:
        return ", ".join(sanitized_parts)
    return _sanitize_display_text(text)


def _process_multipart_body(msg: Message) -> tuple[str, str, list[dict]]:
    plain_body = ""
    html_body = ""
    attachments = []

    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()
        # Skip attachments
        if filename:
            parsed_attachment = parse_email_attachment(
                filename=filename,
                content_type=content_type,
                raw_content=_attachment_part_content(part),
            )
            attachments.append(
                {
                    "filename": parsed_attachment.filename,
                    "content": parsed_attachment.content,
                    "content_type": parsed_attachment.content_type,
                    "parse_content": parsed_attachment.parse_content,
                    "parse_content_type": parsed_attachment.parse_content_type,
                    "parser_key": parsed_attachment.parser_key,
                    "parse_status": parsed_attachment.parse_status,
                    "parse_error_code": parsed_attachment.parse_error_code,
                }
            )
            continue

        if content_type == "text/plain":
            part_content = part.get_content()
            if isinstance(part_content, str):
                plain_body += part_content
        elif content_type == "text/html":
            part_content = part.get_content()
            if isinstance(part_content, str):
                html_body += part_content
    return plain_body, html_body, attachments


def _attachment_part_content(part: Message) -> object:
    try:
        return part.get_content()
    except (LookupError, TypeError, ValueError):
        payload = part.get_payload(decode=True)
        return payload if payload is not None else ""


def _process_singlepart_body(msg: Message) -> tuple[str, str, list[dict]]:
    plain_body = ""
    html_body = ""
    content_type = msg.get_content_type()
    # get_content() raises for content types with no registered handler -- e.g. a
    # message that declares multipart/* but carries no parsable parts, which
    # is_multipart() reports as single-part. Guard it exactly like the
    # attachment path (_attachment_part_content). Note KeyError <: LookupError.
    try:
        part_content = msg.get_content()
    except (LookupError, TypeError, ValueError):
        payload = msg.get_payload(decode=True)
        part_content = payload.decode("utf-8", errors="replace") if payload else ""
    if isinstance(part_content, str):
        if content_type == "text/html":
            html_body = part_content
        else:
            plain_body = part_content
    return plain_body, html_body, []


def _extract_body_and_attachments(msg: Message) -> tuple[str, str, list[dict]]:
    if msg.is_multipart():
        plain_body, html_body, attachments = _process_multipart_body(msg)
    else:
        plain_body, html_body, attachments = _process_singlepart_body(msg)

    if plain_body:
        return plain_body, "text/plain", attachments
    return html_body, "text/html" if html_body else "text/plain", attachments


def _extract_date(msg: Message) -> datetime.datetime:
    date_header = msg.get("Date")
    parsed_date = None
    if date_header:
        try:
            parsed_date = parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            parsed_date = None

    if not parsed_date:
        parsed_date = datetime.datetime.now(datetime.timezone.utc)
    return parsed_date


def _extract_thread_id(msg: Message, message_id: str) -> str | None:
    references = msg.get("References")  # O3: email threading support

    if references:
        refs = references.split(None, 1)
        if refs:
            return _sanitize_nul(refs[0])

    in_reply_to = msg.get("In-Reply-To")
    if in_reply_to:
        in_reply_to_list = in_reply_to.split(None, 1)
        if in_reply_to_list:
            return _sanitize_nul(in_reply_to_list[0])

    return message_id


def _message_to_email_data(msg: Message) -> EmailData:
    body, body_content_type, attachments = _extract_body_and_attachments(msg)
    parsed_date = _extract_date(msg)
    message_id = _sanitize_nul(msg.get("Message-ID", ""))
    thread_id = _extract_thread_id(msg, message_id)

    return {
        "message_id": message_id,
        "thread_id": thread_id,
        "sender": _sanitize_address_display_text(msg.get("From", "")),
        "reply_to": (
            _sanitize_address_display_text(msg.get("Reply-To", ""))
            if msg.get("Reply-To")
            else None
        ),
        "recipients": _sanitize_address_display_text(msg.get("To", "")),
        "subject": _sanitize_display_text(msg.get("Subject", "")),
        "in_reply_to": (
            _sanitize_nul(msg.get("In-Reply-To", ""))
            if msg.get("In-Reply-To")
            else None
        ),
        "references": (
            _sanitize_nul(msg.get("References", "")) if msg.get("References") else None
        ),
        "date": parsed_date,
        "body": _sanitize_display_text(body),
        "body_content_type": body_content_type,
        "body_parse_content": _sanitize_nul(body),
        "attachments": attachments,
    }


def parse_eml(file_path: str | Path) -> EmailData:
    """Parses an EML file and extracts email metadata and body.

    Raises:
        EmailParseError: If there is an issue reading the file.
    """
    try:
        with open(file_path, "rb") as f:
            msg = message_from_binary_file(f, policy=policy.default)
    except OSError as e:
        raise EmailParseError(f"Failed to read file {file_path}: {e}") from e

    try:
        return _message_to_email_data(msg)
    except Exception as e:  # noqa: BLE001 -- enforce the declared contract
        raise EmailParseError(f"Failed to parse email file {file_path}") from e


def parse_eml_bytes(content: bytes) -> EmailData:
    """Parses EML bytes fetched from a provider."""
    try:
        msg = message_from_bytes(content, policy=policy.default)
    except Exception as e:
        raise EmailParseError("Failed to parse provider email bytes") from e

    # Malformed messages can make the stdlib email stack raise deep inside
    # header/body extraction (address, date, content-type handlers). The
    # declared contract of this function is EmailParseError-or-EmailData, so any
    # such raise is normalised rather than leaked to callers. Found by
    # backend/fuzz (test_email_parser_fuzz).
    try:
        return _message_to_email_data(msg)
    except Exception as e:  # noqa: BLE001 -- enforce the declared contract
        raise EmailParseError("Failed to parse provider email bytes") from e
