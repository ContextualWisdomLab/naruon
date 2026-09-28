import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import bindparam, func, select
from db.models import Email, EmailThreadEdge
from services.email_parser import EmailData


import hashlib
import datetime
from collections import defaultdict, deque

_THREAD_LOCK_NAMESPACE = "naruon-email-thread-evidence"


def email_owner_lock_key(user_id: str, organization_id: str | None) -> str:
    return f"{len(user_id)}:{user_id}{'N' if organization_id is None else 'S' + organization_id}"


async def lock_email_thread_owner(
    session: AsyncSession, user_id: str, organization_id: str | None
) -> None:
    """Serialize imports and corrections for one owner until transaction commit."""
    if not hasattr(type(session), "get_bind"):
        return
    try:
        dialect = session.get_bind().dialect.name
    except AttributeError:
        return
    if dialect != "postgresql":
        return
    await session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtext(bindparam("lock_namespace")),
                func.hashtext(bindparam("lock_owner")),
            )
        ),
        {
            "lock_namespace": _THREAD_LOCK_NAMESPACE,
            "lock_owner": email_owner_lock_key(user_id, organization_id),
        },
    )


# ⚡ Bolt Optimization: Pre-compile reference extraction regex
# Impact: Eliminates redundant inline compilation/caching overhead during repetitive
# email header processing, yielding a measurable speedup when handling long reference lists.
REFERENCE_PATTERN = re.compile(r"<([^>]+)>")


def generate_email_fingerprint(
    subject: str | None,
    date_str: str | None,
    sender: str | None,
    recipient: str | None,
) -> str:
    """Generate a deterministic fingerprint for an email based on key fields."""
    components = [
        str(subject or "").strip(),
        str(date_str or "").strip(),
        str(sender or "").strip(),
        str(recipient or "").strip(),
    ]
    raw = "|".join(components).lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_message_id(value: str | None) -> str | None:
    """Return the canonical persisted form for a Message-ID-like header.

    A Message-ID (RFC 5322 section 3.6.4) carries no interior whitespace, but
    header unfolding (RFC 5322 section 2.2.3) can leave interior spaces or tabs
    when a folded header is rejoined -- e.g. ``<abc@\\r\\n example.com>`` unfolds
    to ``<abc@ example.com>``. Collapsing all interior whitespace keeps the
    folded and unfolded forms of the same Message-ID equal, so de-duplication
    and threading never split one message into two over a fold boundary.
    """
    if value is None:
        return None

    stripped = str(value).strip().strip("<>")
    normalized = "".join(stripped.split())
    return normalized or None


def extract_reference_ids(value: str | None) -> list[str]:
    """Extract canonical message IDs from a ``1*msg-id`` header in header order.

    RFC 5322 defines both References (section 3.6.4) and In-Reply-To
    (section 3.6.4) as ``1*msg-id`` -- one or more angle-bracketed Message-IDs,
    each optionally surrounded by CFWS -- so this extractor applies to either
    header. Ids are canonicalized with :func:`normalize_message_id` and
    de-duplicated while preserving header order.
    """
    if not value:
        return []

    refs = REFERENCE_PATTERN.findall(str(value))
    if not refs:
        refs = str(value).split()

    normalized_refs: list[str] = []
    # Optimization: Use a set for O(1) membership checks to avoid O(n^2) scaling on long reference lists
    seen: set[str] = set()
    for ref in refs:
        normalized = normalize_message_id(ref)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_refs.append(normalized)
    return normalized_refs


async def _find_existing_thread_ids(
    session: AsyncSession,
    message_ids: list[str],
    *,
    user_id: str,
    organization_id: str | None,
) -> dict[str, str]:
    if not message_ids:
        return {}

    target_ids: list[str] = []
    seen_target_ids: set[str] = set()
    for message_id in message_ids:
        for target_id in (message_id, f"<{message_id}>"):
            if target_id not in seen_target_ids:
                seen_target_ids.add(target_id)
                target_ids.append(target_id)

    result = await session.execute(
        select(Email.message_id, Email.thread_id).where(
            *Email.owner_filters(user_id, organization_id),
            Email.message_id.in_(target_ids),
        )
    )

    thread_ids_by_message_id: dict[str, str] = {}
    for message_id, thread_id in result.all():
        if not thread_id:
            continue
        normalized_message_id = normalize_message_id(message_id)
        if normalized_message_id:
            thread_ids_by_message_id[normalized_message_id] = (
                normalize_message_id(thread_id) or thread_id
            )
    return thread_ids_by_message_id


async def assign_thread_id(
    session: AsyncSession,
    email_data: EmailData,
    *,
    user_id: str,
    organization_id: str | None,
) -> str:
    """
    Determine the thread_id for a new email based on in_reply_to and references.
    If no existing match is found, generate a new thread_id.
    """
    # In-Reply-To (RFC 5322 section 3.6.4) is 1*msg-id, exactly like References,
    # and each id may be wrapped in CFWS. Parse it with the same multi-id
    # extractor rather than treating the whole header as one opaque Message-ID,
    # so a reply that names several parents -- or a single id trailed by a
    # comment -- still threads onto an existing ancestor instead of splitting off.
    in_reply_to_ids = extract_reference_ids(email_data.get("in_reply_to"))
    references = extract_reference_ids(email_data.get("references"))

    existing_candidates = []
    # Optimization: Use a set for O(1) membership checks to prevent O(n^2) deduplication of candidates
    seen = set()
    for candidate in (*in_reply_to_ids, *references):
        if candidate not in seen:
            seen.add(candidate)
            existing_candidates.append(candidate)

    if existing_candidates:
        thread_ids_by_message_id = await _find_existing_thread_ids(
            session,
            existing_candidates,
            user_id=user_id,
            organization_id=organization_id,
        )
        for candidate in existing_candidates:
            thread_id = thread_ids_by_message_id.get(candidate)
            if thread_id:
                return thread_id

    # If the parent/root has not been imported yet, use the oldest known ancestor
    # as the deterministic thread root so later imports converge on one thread.
    if references:
        return references[0]

    if in_reply_to_ids:
        return in_reply_to_ids[0]

    msg_id = normalize_message_id(email_data.get("message_id"))
    if msg_id:
        return msg_id

    return uuid.uuid4().hex


def email_thread_evidence(email: Email) -> list[EmailThreadEdge]:
    """Keep bounded RFC reply evidence alongside a newly imported email."""
    edges = []
    for source in ("in_reply_to", "references"):
        raw = getattr(email, source)
        if not raw:
            continue
        ids = extract_reference_ids(raw[:8192]) if len(raw) <= 8192 else []
        incomplete = not ids or len(ids) > 64 or any(len(value) > 512 for value in ids)
        for ordinal, target in enumerate([None] if incomplete else ids):
            edges.append(
                EmailThreadEdge(
                    source_email=email,
                    user_id=email.user_id,
                    organization_id=email.organization_id,
                    source_message_id=email.message_id,
                    target_message_id=target,
                    evidence_source=source,
                    ordinal=ordinal,
                    incomplete=incomplete,
                )
            )
    return edges


def _direct_parent_id(edges: list[EmailThreadEdge]) -> str | None:
    if any(edge.incomplete for edge in edges):
        return None
    replies = {
        edge.target_message_id
        for edge in edges
        if edge.evidence_source == "in_reply_to"
    }
    references = [edge for edge in edges if edge.evidence_source == "references"]
    last_reference = (
        max(references, key=lambda edge: edge.ordinal).target_message_id
        if references
        else None
    )
    if len(replies) > 1 or (
        replies and last_reference and last_reference not in replies
    ):
        return None
    return next(iter(replies)) if replies else last_reference


def _thread_children(
    emails: list[Email], edges: list[EmailThreadEdge]
) -> dict[int, list[Email]]:
    by_message_id: dict[str, list[Email]] = defaultdict(list)
    for email in emails:
        message_id = normalize_message_id(email.message_id)
        if message_id:
            by_message_id[message_id].append(email)
    edges_by_source: dict[int, list[EmailThreadEdge]] = defaultdict(list)
    for edge in edges:
        edges_by_source[edge.source_email_id].append(edge)
    children: dict[int, list[Email]] = defaultdict(list)
    for email in emails:
        parent_id = _direct_parent_id(edges_by_source[email.id])
        parents = by_message_id.get(parent_id or "", [])
        if len(parents) == 1 and parents[0].id != email.id:
            children[parents[0].id].append(email)
    return children


def _move_thread_descendants(
    source: Email, children: dict[int, list[Email]], thread_id: str
) -> int:
    moved: set[int] = set()
    queue = deque([source])
    while queue:
        email = queue.popleft()
        if email.id in moved:
            continue
        moved.add(email.id)
        email.thread_id = thread_id
        queue.extend(children[email.id])
    return len(moved)


async def reconcile_email_thread(session: AsyncSession, email: Email) -> None:
    """Join replies imported before their direct parent, inside the import transaction."""
    message_id = normalize_message_id(email.message_id)
    if not message_id:
        return
    owner = Email.owner_filters(email.user_id, email.organization_id)
    result = await session.execute(
        select(Email.id).where(
            *owner, Email.message_id.in_([message_id, f"<{message_id}>"])
        )
    )
    if result.scalars().all() != [email.id]:
        return
    result = await session.execute(
        select(EmailThreadEdge.source_email_id).where(
            *EmailThreadEdge.owner_filters(email.user_id, email.organization_id),
            EmailThreadEdge.target_message_id == message_id,
            EmailThreadEdge.detached_at.is_(None),
            EmailThreadEdge.incomplete.is_(False),
        )
    )
    candidate_ids = result.scalars().all()
    if not candidate_ids:
        return
    result = await session.execute(
        select(Email).where(*owner, Email.id.in_(candidate_ids)).with_for_update()
    )
    candidates = result.scalars().all()
    new_thread = normalize_message_id(email.thread_id) or email.thread_id
    old_threads = {
        normalize_message_id(candidate.thread_id) or candidate.thread_id
        for candidate in candidates
        if candidate.id != email.id and candidate.thread_id != new_thread
    }
    if not old_threads:
        return
    thread_keys = old_threads | {f"<{value}>" for value in old_threads}
    result = await session.execute(
        select(Email).where(*owner, Email.thread_id.in_(thread_keys)).with_for_update()
    )
    emails = result.scalars().all()
    if email not in emails:
        emails.append(email)
    result = await session.execute(
        select(EmailThreadEdge).where(
            *EmailThreadEdge.owner_filters(email.user_id, email.organization_id),
            EmailThreadEdge.source_email_id.in_([item.id for item in emails]),
            EmailThreadEdge.detached_at.is_(None),
        )
    )
    children = _thread_children(emails, result.scalars().all())
    # ponytail: scans only provisional thread groups; index direct-parent edges if groups grow large.
    for child in children[email.id]:
        _move_thread_descendants(child, children, new_thread)


async def detach_email_from_thread(
    session: AsyncSession,
    *,
    email_id: int,
    user_id: str,
    organization_id: str | None,
    reason: str,
) -> int | None:
    """Detach one email and its unambiguous descendants, retaining the source evidence."""
    await lock_email_thread_owner(session, user_id, organization_id)
    result = await session.execute(
        select(Email)
        .where(Email.id == email_id, *Email.owner_filters(user_id, organization_id))
        .with_for_update()
    )
    source = result.scalar_one_or_none()
    if source is None:
        return None

    old_thread = normalize_message_id(source.thread_id) or source.thread_id
    new_thread = normalize_message_id(source.message_id) or f"email-{source.id}"
    result = await session.execute(
        select(Email)
        .where(
            *Email.owner_filters(user_id, organization_id),
            Email.thread_id.in_([old_thread, f"<{old_thread}>"]),
        )
        .with_for_update()
    )
    emails = result.scalars().all()
    if source not in emails:
        emails.append(source)
    result = await session.execute(
        select(EmailThreadEdge)
        .where(
            *EmailThreadEdge.owner_filters(user_id, organization_id),
            EmailThreadEdge.source_email_id.in_([email.id for email in emails]),
            EmailThreadEdge.detached_at.is_(None),
        )
        .with_for_update()
    )
    active_edges = result.scalars().all()
    source_edges = [edge for edge in active_edges if edge.source_email_id == source.id]
    if not source_edges:
        return 0

    children = _thread_children(emails, active_edges)
    moved = _move_thread_descendants(source, children, new_thread)

    now = datetime.datetime.now(datetime.timezone.utc)
    for edge in source_edges:
        edge.detached_at = now
        edge.detached_by = user_id
        edge.detach_reason = reason
    await session.commit()
    return moved
