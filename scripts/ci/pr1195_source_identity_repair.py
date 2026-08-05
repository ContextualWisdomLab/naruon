from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(".")

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

path = "backend/services/email_dedupe_service.py"
text = read(path)
text = replace_once(
    text,
    "import datetime\nfrom collections.abc import Iterable\n",
    "import datetime\nimport hashlib\nimport json\nfrom collections.abc import Iterable, Mapping\n",
    "email_dedupe_service imports",
)
helper = '_CANONICAL_SOURCE_FIELDS = (\n    "message_id",\n    "sender",\n    "recipients",\n    "subject",\n    "body",\n    "reply_to",\n    "in_reply_to",\n    "references",\n    "attachments",\n)\n\n\ndef canonical_email_source_content(email_data: Mapping[str, object]) -> bytes:\n    """Serialize stable parsed fields when raw transport bytes are unavailable.\n\n    Collection-time ``date`` values and their provenance are deliberately\n    excluded. Transport-backed paths should provide exact RFC822 bytes.\n    """\n    payload = {field: email_data.get(field) for field in _CANONICAL_SOURCE_FIELDS}\n    return json.dumps(\n        payload,\n        ensure_ascii=False,\n        sort_keys=True,\n        separators=(",", ":"),\n        default=str,\n    ).encode("utf-8", errors="surrogatepass")\n\n\ndef source_email_fingerprint(\n    source_content: bytes,\n    *,\n    source_kind: Literal["raw", "canonical"] = "raw",\n) -> str:\n    """Return a domain-separated SHA-256 identity for stable source bytes."""\n    digest = hashlib.sha256()\n    digest.update(b"naruon-email-source-v1\\0")\n    digest.update(source_kind.encode("ascii"))\n    digest.update(b"\\0")\n    digest.update(source_content)\n    return digest.hexdigest()\n\n\n'
if "def source_email_fingerprint(" not in text:
    text = replace_once(
        text,
        "def strong_email_fingerprint(\n",
        helper + "def strong_email_fingerprint(\n",
        "email_dedupe_service helper insertion",
    )
write(path, text)

path = "backend/services/email_import_service.py"
text = read(path)
text = replace_once(
    text,
    "from services.email_dedupe_service import strong_email_fingerprint\n",
    "from services.email_dedupe_service import (\n    canonical_email_source_content,\n    source_email_fingerprint,\n    strong_email_fingerprint,\n)\n",
    "email_import_service dedupe import",
)
pattern = re.compile(
    r"def _email_fingerprint\(parsed: EmailData, persisted_date: datetime\.datetime\) -> str:\n"
    r".*?\n\n\nasync def _find_existing_email",
    re.DOTALL,
)
replacement = 'def _email_fingerprint(\n    parsed: EmailData,\n    persisted_date: datetime.datetime,\n    source_content: bytes | None = None,\n) -> str:\n    """Return trusted-Date evidence or a source-bound fallback identity.\n\n    ``persisted_date`` remains the storage timestamp and participates in\n    duplicate evidence only when it came from a valid sender ``Date``.\n    """\n    strong_fingerprint = None\n    if parsed.get("date_provenance") == "parsed":\n        strong_fingerprint = strong_email_fingerprint(\n            sender=parsed.get("sender"),\n            subject=parsed.get("subject"),\n            date=persisted_date,\n            body=parsed.get("body"),\n        )\n    if strong_fingerprint:\n        return strong_fingerprint\n    source_identity = (\n        source_content\n        if source_content is not None\n        else canonical_email_source_content(parsed)\n    )\n    return source_email_fingerprint(\n        source_identity,\n        source_kind="raw" if source_content is not None else "canonical",\n    )\n\n\nasync def _find_existing_email'
text, count = pattern.subn(replacement, text, count=1)
if count != 1 and "source-bound fallback identity" not in text:
    raise SystemExit(f"email_import_service fingerprint block: replaced {count}")
text = replace_once(
    text,
    "    fingerprint = _email_fingerprint(parsed, persisted_date)\n",
    "    fingerprint = _email_fingerprint(parsed, persisted_date, content)\n",
    "email_import_service fingerprint call",
)
if text.count("generate_email_fingerprint") == 1:
    text = text.replace("    generate_email_fingerprint,\n", "", 1)
write(path, text)

path = "backend/services/imap_worker.py"
text = read(path)
text = replace_once(
    text,
    "from services.email_dedupe_service import strong_email_fingerprint\n",
    "from services.email_dedupe_service import (\n    canonical_email_source_content,\n    source_email_fingerprint,\n    strong_email_fingerprint,\n)\n",
    "imap_worker dedupe import",
)
text = replace_once(
    text,
    "from services.threading_service import assign_thread_id, generate_email_fingerprint\n",
    "from services.threading_service import assign_thread_id\n",
    "imap_worker threading import",
)
text = replace_once(
    text,
    '    owner_addresses: Iterable[str] | None = None,\n    is_read: bool = True,\n):\n    subject = email_data.get("subject", "")\n    date_obj = email_data.get("date")\n    if hasattr(date_obj, "isoformat"):\n        date_str = date_obj.isoformat()\n    else:\n        date_str = str(date_obj) if date_obj else ""\n',
    '    owner_addresses: Iterable[str] | None = None,\n    is_read: bool = True,\n    source_content: bytes | None = None,\n) -> Email:\n    """Persist one fetched email with provenance-safe identity."""\n    subject = email_data.get("subject", "")\n    date_obj = email_data.get("date")\n',
    "imap_worker signature",
)
fingerprint_pattern = re.compile(
    r"    # Seed the strong \(auto-dedupe\) fingerprint only from a genuinely-parsed\n"
    r".*?"
    r"    fingerprint = strong_fingerprint or generate_email_fingerprint\(\n"
    r"        subject, date_str, sender, recipients\n"
    r"    \)\n",
    re.DOTALL,
)
fingerprint_replacement = '    # Seed strong duplicate evidence only from a genuinely parsed Date.\n    strong_fingerprint = None\n    if email_data.get("date_provenance") == "parsed":\n        strong_fingerprint = strong_email_fingerprint(\n            sender=sender,\n            subject=subject,\n            date=persisted_date,\n            body=email_data.get("body", ""),\n        )\n    source_identity = (\n        source_content\n        if source_content is not None\n        else canonical_email_source_content(email_data)\n    )\n    fingerprint = strong_fingerprint or source_email_fingerprint(\n        source_identity,\n        source_kind="raw" if source_content is not None else "canonical",\n    )\n'
text, count = fingerprint_pattern.subn(fingerprint_replacement, text, count=1)
if count != 1 and "source_identity = (" not in text:
    raise SystemExit(f"imap_worker fingerprint block: replaced {count}")
text = replace_once(
    text,
    "                        is_read=is_read,\n                    )\n",
    "                        is_read=is_read,\n                        source_content=raw_message,\n                    )\n",
    "imap_worker raw source propagation",
)
write(path, text)

path = "backend/services/pop3_worker.py"
text = read(path)
text = replace_once(
    text,
    "                        owner_addresses=owner_addresses,\n                    )\n",
    "                        owner_addresses=owner_addresses,\n                        source_content=raw_message,\n                    )\n",
    "pop3_worker raw source propagation",
)
write(path, text)

path = "backend/tests/test_imap_worker.py"
text = read(path)
text = replace_once(
    text,
    '    assert kwargs["owner_addresses"] == ["imap-user@example.com"]\n',
    '    assert kwargs["owner_addresses"] == ["imap-user@example.com"]\n    assert kwargs["source_content"] == raw_message\n',
    "imap worker source assertion",
)
write(path, text)

path = "backend/tests/test_pop3_worker.py"
text = read(path)
text = replace_once(
    text,
    '    async def fake_process_fetched_email(\n        db_session, email_data, user_id, organization_id, owner_addresses=None\n    ):\n',
    '    async def fake_process_fetched_email(\n        db_session,\n        email_data,\n        user_id,\n        organization_id,\n        owner_addresses=None,\n        source_content=None,\n    ):\n',
    "pop3 fake processor signature",
)
text = replace_once(
    text,
    '                "owner_addresses": owner_addresses,\n',
    '                "owner_addresses": owner_addresses,\n                "source_content": source_content,\n',
    "pop3 imported source record",
)
text = replace_once(
    text,
    '    assert imported[0]["owner_addresses"] == ["pop3-user@example.com"]\n',
    '    assert imported[0]["owner_addresses"] == ["pop3-user@example.com"]\n    assert imported[0]["source_content"] == raw_message\n',
    "pop3 worker source assertion",
)
write(path, text)

path = "backend/tests/test_email_parser_provenance.py"
text = read(path)
text = replace_once(
    text,
    '    return (headers.strip() + "\\n\\nBody text.").encode("utf-8")\n',
    '    return (headers.strip("\\r\\n") + "\\n\\nBody text.").encode("utf-8")\n',
    "parser provenance fixture",
)
write(path, text)

path = "CHANGELOG.md"
text = read(path)
note = (
    "- Bound missing/invalid-Date email deduplication fallbacks to immutable "
    "RFC822 source bytes (or a deterministic Date-free canonical projection), "
    "including import, IMAP, and POP3 paths, so collection timestamps cannot "
    "create false duplicate identities.\n"
)
if note not in text:
    if "### Fixed\n" in text:
        text = text.replace("### Fixed\n", "### Fixed\n" + note, 1)
    else:
        text = text.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n" + note, 1)
write(path, text)
