"""Exercise Reply-SLA contention bounds with real SQLAlchemy unit-of-work semantics."""

import datetime
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base

from api import tasks as tasks_api
from api.auth import AuthContext
from services import reply_sla_escalation_service as service

NOW = datetime.datetime.now(datetime.timezone.utc)
WORKSPACE_ID = "workspace-a"
Base = declarative_base()


class MailRow(Base):
    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    organization_id = Column(String)
    workspace_id = Column(String, nullable=False)
    message_id = Column(String, nullable=False)
    subject = Column(String)
    thread_id = Column(String)
    date = Column(DateTime(timezone=True), nullable=False)


class TaskRow(Base):
    __tablename__ = "ticket_tasks"

    id = Column("task_id", Integer, primary_key=True)
    task_uid = Column(String, default=lambda: uuid.uuid4().hex)
    user_id = Column(String, nullable=False)
    organization_id = Column(String)
    title = Column("task_title", String, nullable=False)
    status = Column("status_code", String, nullable=False)
    priority = Column("priority_code", String, nullable=False)
    source_type = Column(String, nullable=False)
    related_email_id = Column("email_id", Integer, ForeignKey("email_records.id"))
    related_thread_id = Column("thread_id", String)
    updated_at = Column(DateTime(timezone=True), default=lambda: NOW)


Index(
    "uq_ticket_tasks_reply_sla_email",
    TaskRow.user_id,
    func.coalesce(TaskRow.organization_id, ""),
    TaskRow.source_type,
    TaskRow.related_email_id,
    unique=True,
    sqlite_where=(
        (TaskRow.source_type == "reply_sla")
        & TaskRow.related_email_id.is_not(None)
    ),
)


class SessionBridge:
    """Expose async service methods over a real synchronous SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.savepoints = 0
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self.statements = []

    @property
    def no_autoflush(self):
        return self.session.no_autoflush

    async def execute(self, statement):
        self.statements.append(statement)
        return self.session.execute(statement)

    def add(self, row) -> None:
        self.session.add(row)

    async def commit(self) -> None:
        self.commits += 1
        self.session.commit()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.session.rollback()

    async def flush(self) -> None:
        self.flushes += 1
        self.session.flush()

    @asynccontextmanager
    async def begin_nested(self):
        self.savepoints += 1
        with self.session.begin_nested():
            yield


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _connection_record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin_transaction(connection):
        # SQLite legacy mode must not let a released savepoint escape rollback.
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    monkeypatch.setattr(service, "Email", MailRow)
    monkeypatch.setattr(service, "TicketTask", TaskRow)
    monkeypatch.setattr(
        service,
        "_reply_sla_task_title",
        lambda mail: f"follow up: {mail.subject}",
    )
    monkeypatch.setattr(
        service,
        "canonical_reply_sla_thread_key",
        lambda mail: mail.thread_id,
    )
    with Session(engine, expire_on_commit=False) as session:
        yield SessionBridge(session)
    engine.dispose()


def seed_mail(database: SessionBridge, count: int) -> list[MailRow]:
    mails = [
        MailRow(
            user_id="alice",
            organization_id="org-a",
            workspace_id=WORKSPACE_ID,
            message_id=f"mail-{index}",
            subject=f"subject-{index}",
            thread_id=f"thread-{index}",
            date=NOW - datetime.timedelta(days=3),
        )
        for index in range(count)
    ]
    database.session.add_all(mails)
    database.session.commit()
    return mails


def seed_task(
    database: SessionBridge,
    mail: MailRow,
    *,
    status: str = "open",
    organization_id: str | None = "org-a",
) -> TaskRow:
    task = TaskRow(
        user_id="alice",
        organization_id=organization_id,
        title="old title",
        status=status,
        priority="normal",
        source_type="reply_sla",
        related_email_id=mail.id,
        related_thread_id="old thread",
        updated_at=NOW,
    )
    database.session.add(task)
    database.session.commit()
    return task


def expose_conflict_waves(monkeypatch, waves: list[set[int]]) -> None:
    original = service._fetch_existing_tasks_by_email
    reads = 0

    async def fetch(*args):
        nonlocal reads
        rows = await original(*args)
        visible = waves[min(reads, len(waves) - 1)]
        reads += 1
        return {key: value for key, value in rows.items() if key in visible}

    monkeypatch.setattr(service, "_fetch_existing_tasks_by_email", fetch)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 10, 50])
async def test_ordinary_path_does_not_create_per_mail_savepoints(database, count):
    mails = seed_mail(database, count)

    created, tasks = await service._process_bulk_escalation(
        database, "alice", "org-a", mails, NOW
    )

    assert created == count
    assert [message for _, message in tasks] == [mail.message_id for mail in mails]
    assert database.commits == 1
    assert database.savepoints == 0
    assert database.session.scalar(select(func.count()).select_from(TaskRow)) == count


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [10, 50])
async def test_repeated_conflicts_stay_batched_and_preserve_response_authority(
    database, monkeypatch, count
):
    mails = seed_mail(database, count)
    first = seed_task(database, mails[0])
    done = seed_task(database, mails[1], status="done")
    done_uid = done.task_uid
    expose_conflict_waves(
        monkeypatch,
        [
            set(),
            {mails[0].id},
            {mails[0].id, mails[1].id},
            {mail.id for mail in mails},
        ],
    )

    created, tasks = await service._process_fallback_escalation(
        database, "alice", "org-a", mails, NOW
    )

    assert created == count - 2
    assert database.flushes <= service.REPLY_SLA_MAX_BATCH_ATTEMPTS
    assert database.savepoints <= service.REPLY_SLA_MAX_BATCH_ATTEMPTS
    assert database.commits == 1
    assert tasks[0][0].task_uid == first.task_uid
    assert tasks[0][0].status == "blocked"
    assert tasks[1][0].task_uid == done_uid
    assert tasks[1][0].status == "done"
    assert tasks[1][0].title == "old title"
    assert [message for _, message in tasks] == [
        f"mail-{index}" for index in range(count)
    ]


@pytest.mark.asyncio
async def test_exhausted_batch_budget_rolls_back_all_local_updates(
    database, monkeypatch
):
    mails = seed_mail(database, 10)
    winners = [seed_task(database, mail) for mail in mails[:4]]
    expose_conflict_waves(
        monkeypatch,
        [set(), {mails[0].id}, {mails[1].id}, {mails[2].id}],
    )

    with pytest.raises(service.ReplySlaTaskConflict) as conflict_error:
        await service._process_fallback_escalation(
            database, "alice", "org-a", mails, NOW
        )

    assert conflict_error.value.error_code == "reply_sla_batch_retry_exhausted"
    assert database.savepoints == service.REPLY_SLA_MAX_BATCH_ATTEMPTS
    assert database.commits == 0
    assert database.rollbacks == 1
    assert not database.session.in_transaction()
    assert database.session.scalar(select(func.count()).select_from(TaskRow)) == 4
    assert all(task.title == "old title" for task in winners)


@pytest.mark.asyncio
async def test_non_unique_integrity_error_is_not_retried_per_mail(database):
    mail = MailRow(
        id=999,
        message_id="missing",
        user_id="alice",
        organization_id="org-a",
        workspace_id=WORKSPACE_ID,
        subject="missing",
        thread_id="missing",
        date=NOW,
    )

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await service._process_fallback_escalation(
            database, "alice", "org-a", [mail], NOW
        )

    assert database.savepoints == 1
    assert database.commits == 0
    assert database.rollbacks == 1
    assert not database.session.in_transaction()


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 50])
async def test_outer_rollback_reloads_expired_mail_in_one_workspace_scoped_select(
    database, monkeypatch, count
):
    mails = seed_mail(database, count)
    database.session.execute(select(MailRow)).all()
    missing_replies = AsyncMock(return_value=mails)
    monkeypatch.setattr(service, "check_missing_replies", missing_replies)
    monkeypatch.setattr(
        service,
        "_process_bulk_escalation",
        AsyncMock(side_effect=IntegrityError("collision", {}, None)),
    )

    @event.listens_for(database.session, "do_orm_execute")
    def forbid_implicit_reload(state):
        if state.is_column_load:
            raise AssertionError("expired Email accessed through implicit per-row SQL")

    result = await service.create_reply_sla_escalation_tasks(
        database,
        user_id="alice",
        organization_id="org-a",
        workspace_id=WORKSPACE_ID,
        overdue_hours=48,
        limit=50,
    )

    missing_replies.assert_awaited_once_with(
        database,
        "alice",
        "org-a",
        WORKSPACE_ID,
        tenant_config=None,
    )
    mail_queries = [
        query
        for query in database.statements
        if query.column_descriptions[0].get("entity") is MailRow
    ]
    assert len(mail_queries) == 1
    sql = str(mail_queries[0])
    assert "email_records.user_id" in sql
    assert "email_records.organization_id" in sql
    assert "email_records.workspace_id" in sql
    assert result.evaluated == count
    assert result.created == count
    assert [entry.source_email_id for entry in result.tasks] == [
        f"mail-{index}" for index in range(count)
    ]


@pytest.mark.asyncio
async def test_failure_before_savepoint_rolls_back_without_reconciliation(
    database, monkeypatch
):
    mails = seed_mail(database, 2)
    unrelated = seed_task(database, mails[1])
    original = database.begin_nested

    @asynccontextmanager
    async def fail_preflush():
        unrelated.title = None
        async with original():
            yield

    monkeypatch.setattr(database, "begin_nested", fail_preflush)

    with pytest.raises(IntegrityError, match="NOT NULL"):
        await service._process_fallback_escalation(
            database, "alice", "org-a", mails[:1], NOW
        )

    assert database.rollbacks == 1
    assert database.commits == 0
    assert len(database.statements) == 1
    assert not database.session.in_transaction()
    assert unrelated.title == "old title"


@pytest.mark.asyncio
@pytest.mark.parametrize("organization_id", ["org-a", None])
async def test_reload_preserves_order_null_organization_and_workspace_scope(
    database, organization_id
):
    mails = seed_mail(database, 3)
    for mail in mails:
        mail.organization_id = organization_id
    database.session.commit()
    ordered_ids = [mails[2].id, mails[0].id]
    database.session.expire_all()

    reloaded = await service._reload_overdue_replies(
        database,
        "alice",
        organization_id,
        WORKSPACE_ID,
        ordered_ids,
    )

    assert [mail.id for mail in reloaded] == ordered_ids
    assert len(database.statements) == 1
    assert "email_records.workspace_id" in str(database.statements[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["delete", "owner", "organization", "workspace"])
async def test_reload_fails_closed_when_source_leaves_authorized_scope(
    database, change
):
    mail = seed_mail(database, 1)[0]
    mail_id = mail.id
    if change == "delete":
        database.session.delete(mail)
    elif change == "owner":
        mail.user_id = "bob"
    elif change == "organization":
        mail.organization_id = "org-b"
    else:
        mail.workspace_id = "workspace-b"
    database.session.commit()

    with pytest.raises(service.ReplySlaTaskConflict) as conflict_error:
        await service._reload_overdue_replies(
            database,
            "alice",
            "org-a",
            WORKSPACE_ID,
            [mail_id],
        )

    assert conflict_error.value.error_code == "reply_sla_source_email_unavailable"
    assert database.rollbacks == 1
    assert database.commits == 0
    assert not database.session.in_transaction()


@pytest.mark.asyncio
async def test_completed_existing_task_is_not_reopened_or_committed(database):
    mail = seed_mail(database, 1)[0]
    original = seed_task(database, mail, status="done")

    created, tasks = await service._process_fallback_escalation(
        database, "alice", "org-a", [mail], NOW
    )

    assert created == 0
    assert tasks[0][0] is original
    assert original.status == "done"
    assert original.title == "old title"
    assert database.savepoints == 0
    assert database.commits == 0


@pytest.mark.asyncio
async def test_unique_failure_without_visible_winner_retains_domain_conflict(
    database, monkeypatch
):
    mail = seed_mail(database, 1)[0]
    seed_task(database, mail)
    expose_conflict_waves(monkeypatch, [set()])

    with pytest.raises(service.ReplySlaTaskConflict) as conflict_error:
        await service._process_fallback_escalation(
            database, "alice", "org-a", [mail], NOW
        )

    assert conflict_error.value.error_code == "reply_sla_task_conflict"
    assert database.rollbacks == 1
    assert database.commits == 0
    assert database.savepoints == 1
    assert not database.session.in_transaction()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("driver_code", "expected_exception"),
    [
        (None, service.ReplySlaTaskConflict),
        ("23505", service.ReplySlaTaskConflict),
        ("23503", IntegrityError),
        ("23502", IntegrityError),
        ("23514", IntegrityError),
    ],
)
async def test_unresolved_conflict_mapping_uses_driver_codes_not_error_text(
    database, monkeypatch, driver_code, expected_exception
):
    mail = seed_mail(database, 1)[0]
    driver_error = Exception("same localized message for every constraint")
    if driver_code is not None:
        driver_error.sqlstate = driver_code
    failure = IntegrityError("insert", {}, driver_error)

    async def fail_flush():
        raise failure

    monkeypatch.setattr(database, "flush", fail_flush)

    with pytest.raises(expected_exception) as captured:
        await service._process_fallback_escalation(
            database, "alice", "org-a", [mail], NOW
        )

    if expected_exception is IntegrityError:
        assert captured.value is failure
    assert database.rollbacks == 1
    assert database.commits == 0
    assert database.savepoints == 1
    assert not database.session.in_transaction()


@pytest.mark.asyncio
async def test_tasks_api_preserves_specific_reply_sla_conflict_code(monkeypatch):
    async def raise_batch_retry_exhaustion(_database_session, **_options):
        raise tasks_api.ReplySlaTaskConflict(
            "reply_sla_batch_retry_exhausted",
            "batch retry budget exhausted",
        )

    monkeypatch.setattr(
        tasks_api,
        "create_reply_sla_escalation_tasks",
        raise_batch_retry_exhaustion,
    )
    auth_context = AuthContext(
        user_id="alice",
        role="member",
        organization_id="org-a",
        group_ids=(),
        workspace_id=WORKSPACE_ID,
    )

    with pytest.raises(HTTPException) as error:
        await tasks_api.create_reply_sla_escalations(
            tasks_api.ReplySlaEscalationRequest(overdue_hours=48),
            db=object(),
            auth_context=auth_context,
        )

    assert error.value.status_code == 409
    assert error.value.detail == {
        "error_code": "reply_sla_batch_retry_exhausted",
        "message": "Overdue reply follow-up task conflict",
    }
