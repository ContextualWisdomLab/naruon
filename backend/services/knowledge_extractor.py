import logging
from email import utils as email_utils
from collections.abc import Iterable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Email, TicketTask
from services.email_service import process_self_to_self
from services.text_safety import strip_html_markup

logger = logging.getLogger(__name__)

SELF_SENT_KNOWLEDGE_SOURCE = "self_sent_knowledge"
_TITLE_LIMIT = 140


def _single_line_plain_text(value: str | None) -> str:
    text = strip_html_markup(str(value or "").replace("\x00", ""))
    return " ".join(text.split())


def _normalized_owner_addresses(owner_addresses: Iterable[str] | None):
    if owner_addresses is None:
        candidates: list[str] = []
    elif isinstance(owner_addresses, str):
        candidates = [owner_addresses]
    else:
        candidates = list(owner_addresses)
    return {
        address.strip().lower()
        for _, address in email_utils.getaddresses(candidates)
        if address
    }


def is_self_sent_email(
    email: Email, owner_addresses: Iterable[str] | None = None
) -> bool:
    tenant_addresses = _normalized_owner_addresses(owner_addresses)
    return process_self_to_self(
        {
            "sender": email.sender,
            "recipients": email.recipients or "",
            "subject": email.subject or "",
            "body": email.body or "",
        },
        tenant_addresses,
    )


def _knowledge_task_title(email: Email) -> str:
    subject = _single_line_plain_text(email.subject)
    if subject:
        title_basis = subject
    else:
        title_basis = _single_line_plain_text(email.body).splitlines()[0:1]
        title_basis = title_basis[0] if title_basis else "Self note"

    title_basis = title_basis[:_TITLE_LIMIT].strip() or "Self note"
    return f"Memo: {title_basis}"


async def _existing_knowledge_task(db: AsyncSession, email: Email) -> TicketTask | None:
    if email.id is None:
        return None
    result = await db.execute(
        select(TicketTask).where(
            TicketTask.user_id == email.user_id,
            TicketTask.organization_id == email.organization_id,
            TicketTask.related_email_id == email.id,
            TicketTask.source_type == SELF_SENT_KNOWLEDGE_SOURCE,
        )
        .order_by(TicketTask.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def extract_knowledge_from_self_sent(
    db: AsyncSession, email: Email, owner_addresses: Iterable[str] | None = None
):
    """
    Extract knowledge from a self-sent email into a source-linked TicketTask.
    """
    has_note_content = bool(
        _single_line_plain_text(email.subject) or _single_line_plain_text(email.body)
    )
    if (
        not has_note_content
        or email.is_personal_reference is not True
        or not is_self_sent_email(email, owner_addresses)
    ):
        return None

    existing_task = await _existing_knowledge_task(db, email)
    if existing_task is not None:
        return existing_task

    if email.id is None:
        return None

    logger.info("Extracting self-sent knowledge from email %s", email.message_id)

    task = TicketTask(
        user_id=email.user_id,
        organization_id=email.organization_id,
        title=_knowledge_task_title(email),
        status="open",
        priority="normal",
        source_type=SELF_SENT_KNOWLEDGE_SOURCE,
        related_email_id=email.id,
        related_thread_id=email.thread_id,
    )
    db.add(task)
    await db.flush()
    return task
