import hashlib
import logging
from collections.abc import Iterable
from typing import Dict, Any
from email.utils import parseaddr, getaddresses

logger = logging.getLogger(__name__)

def generate_email_fingerprint(email_data: Dict[str, Any]) -> str:
    """
    Generates a unique fingerprint for an email based on its sender, subject, date, and body content.
    Used to de-duplicate emails from ZIP imports or forwarding loops.
    """
    sender = str(email_data.get("sender") or "")
    subject = str(email_data.get("subject") or "")
    date = str(email_data.get("date") or "")
    body = str(email_data.get("body") or "")
    body_snippet = body[:500] # First 500 chars
    
    raw_str = f"{sender}|{subject}|{date}|{body_snippet}"
    fingerprint_source = raw_str.encode("utf-8", errors="backslashreplace")
    return hashlib.sha256(fingerprint_source).hexdigest()


def process_self_to_self(
    email_data: Dict[str, Any], user_email: str | Iterable[str]
) -> bool:
    """
    Detect mail sent only between addresses owned by the same user.
    """
    sender_raw = str(email_data.get("sender") or "")
    recipients_raw = email_data.get("recipients") or []
    recipient_inputs = recipients_raw if isinstance(recipients_raw, list) else [recipients_raw]
    recipient_inputs = [str(v) for v in recipient_inputs]
    owner_inputs = [user_email] if isinstance(user_email, str) else list(user_email)
    
    _, sender_addr = parseaddr(sender_raw)
    owner_addresses = {
        addr.strip().lower()
        for _, addr in getaddresses([str(value) for value in owner_inputs])
        if "@" in addr
    }
    normalized_sender = sender_addr.strip().lower()
    parsed_recipients = {
        addr.strip().lower()
        for _, addr in getaddresses(recipient_inputs)
        if addr
    }
    
    if (
        normalized_sender in owner_addresses
        and parsed_recipients
        and parsed_recipients <= owner_addresses
    ):
        logger.info("Self-to-self email detected. Organizing as knowledge node.")
        return True
    return False
