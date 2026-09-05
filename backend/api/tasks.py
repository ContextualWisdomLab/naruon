import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from api.emails import canonical_thread_key
from db.models import Email, TicketTask
from db.session import get_db
from services.reply_sla_escalation_service import (
    ReplySlaEscalationResult,
    ReplySlaTaskConflict,
    create_reply_sla_escalation_tasks,
)
from services.text_safety import contains_html_markup

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


TaskStatus = Literal["open", "in_progress", "blocked", "done"]
TaskPriority = Literal["low", "normal", "high", "urgent"]


class TicketTaskWireModel(BaseModel):
    """Translate specific ticket-task domain names to established API wire keys."""

    model_config = ConfigDict(populate_by_name=True)


class CreateTasksFromEmailRequest(TicketTaskWireModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_email_id: str
    thread_id: str | None = None
    task_items: list[str] = Field(alias="items")


class TicketTaskResponse(TicketTaskWireModel):
    task_uid: str = Field(alias="id")
    task_title: str = Field(alias="title")
    task_status: TaskStatus = Field(alias="status")
    task_priority: TaskPriority = Field(alias="priority")
    source_type: str
    source_email_id: str | None
    related_thread_id: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CreateTasksFromEmailResponse(TicketTaskWireModel):
    created_task_count: int = Field(alias="created")
    ticket_tasks: list[TicketTaskResponse] = Field(alias="tasks")


class ReplySlaEscalationRequest(TicketTaskWireModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    overdue_hours: int = Field(default=48, ge=1, le=720)
    escalation_limit: int = Field(default=10, ge=1, le=50, alias="limit")


class ReplySlaPolicyResponse(TicketTaskWireModel):
    overdue_hours: int


class ReplySlaEscalationResponse(TicketTaskWireModel):
    evaluated_email_count: int = Field(alias="evaluated")
    created_task_count: int = Field(alias="created")
    reply_sla_policy: ReplySlaPolicyResponse = Field(alias="policy")
    ticket_tasks: list[TicketTaskResponse] = Field(alias="tasks")


class UpdateTicketTaskRequest(TicketTaskWireModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task_status: TaskStatus | None = Field(default=None, alias="status")
    task_priority: TaskPriority | None = Field(default=None, alias="priority")


def _normalize_execution_items(task_items: list[str]) -> list[str]:
    normalized_items = []
    for task_item in task_items:
        trimmed_item = task_item.replace("\x00", "").strip()
        if trimmed_item:
            if contains_html_markup(trimmed_item):
                raise HTTPException(
                    status_code=422, detail="Execution items must be plain text"
                )
            normalized_items.append(trimmed_item)
    return normalized_items


def _email_matches_auth(email: Email, auth_context: AuthContext) -> bool:
    return (
        email.user_id == auth_context.user_id
        and email.organization_id == auth_context.organization_id
    )


def _task_response(
    ticket_task: TicketTask,
    source_email_id: str | None,
) -> TicketTaskResponse:
    scoped_thread_id = (
        ticket_task.related_thread_id if source_email_id is not None else None
    )
    return TicketTaskResponse(
        task_uid=ticket_task.task_uid,
        task_title=ticket_task.title,
        task_status=cast(TaskStatus, ticket_task.status),
        task_priority=cast(TaskPriority, ticket_task.priority),
        source_type=ticket_task.source_type,
        source_email_id=source_email_id,
        related_thread_id=scoped_thread_id,
        created_at=ticket_task.created_at,
        updated_at=ticket_task.updated_at,
    )


def _reply_sla_response(
    escalation_result: ReplySlaEscalationResult,
) -> ReplySlaEscalationResponse:
    return ReplySlaEscalationResponse(
        evaluated_email_count=escalation_result.evaluated_email_count,
        created_task_count=escalation_result.created_task_count,
        reply_sla_policy=ReplySlaPolicyResponse(
            overdue_hours=escalation_result.overdue_hours
        ),
        ticket_tasks=[
            _task_response(entry.ticket_task, entry.source_email_id)
            for entry in escalation_result.ticket_tasks
        ],
    )


@router.post("/reply-sla-escalations", response_model=ReplySlaEscalationResponse)
async def create_reply_sla_escalations(
    request: ReplySlaEscalationRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> ReplySlaEscalationResponse:
    try:
        escalation_result = await create_reply_sla_escalation_tasks(
            db,
            user_id=auth_context.user_id,
            organization_id=auth_context.organization_id,
            overdue_hours=request.overdue_hours,
            limit=request.escalation_limit,
        )
    except ReplySlaTaskConflict:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "reply_sla_task_conflict",
                "message": "Overdue reply follow-up task conflict",
            },
        ) from None
    return _reply_sla_response(escalation_result)


def _build_task_query(auth_context: AuthContext):
    return (
        select(TicketTask, Email.message_id)
        .outerjoin(
            Email,
            and_(
                TicketTask.related_email_id == Email.id,
                Email.user_id == auth_context.user_id,
                Email.organization_id == auth_context.organization_id,
            ),
        )
        .where(
            TicketTask.user_id == auth_context.user_id,
            TicketTask.organization_id == auth_context.organization_id,
        )
    )


@router.get("", response_model=list[TicketTaskResponse])
async def list_ticket_tasks(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> list[TicketTaskResponse]:
    task_query_result = await db.execute(
        _build_task_query(auth_context).order_by(TicketTask.updated_at.desc())
    )
    return [
        _task_response(ticket_task, source_email_id)
        for ticket_task, source_email_id in task_query_result.all()
    ]


@router.patch("/{task_uid}", response_model=TicketTaskResponse)
async def update_ticket_task(
    task_uid: str,
    request: UpdateTicketTaskRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> TicketTaskResponse:
    if request.task_status is None and request.task_priority is None:
        raise HTTPException(
            status_code=422, detail="At least one ticket field is required"
        )

    task_query_result = await db.execute(
        _build_task_query(auth_context).where(TicketTask.task_uid == task_uid)
    )
    task_row = task_query_result.one_or_none()
    if task_row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    ticket_task, source_email_id = task_row
    if request.task_status is not None:
        ticket_task.status = request.task_status
    if request.task_priority is not None:
        ticket_task.priority = request.task_priority
    ticket_task.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(ticket_task)
    return _task_response(ticket_task, source_email_id)


def _validate_execution_items(task_items: list[str]) -> list[str]:
    normalized_items = _normalize_execution_items(task_items)
    if not normalized_items:
        raise HTTPException(
            status_code=422, detail="At least one execution item is required"
        )
    if len(normalized_items) > 50:
        raise HTTPException(status_code=422, detail="Too many execution items")
    return normalized_items


async def _fetch_source_email(
    db: AsyncSession,
    request: CreateTasksFromEmailRequest,
    auth_context: AuthContext,
) -> Email:
    email_query_result = await db.execute(
        select(Email).where(
            Email.message_id == request.source_email_id,
            Email.user_id == auth_context.user_id,
            Email.organization_id == auth_context.organization_id,
        )
    )
    source_email = email_query_result.scalar_one_or_none()
    if source_email is None or not _email_matches_auth(source_email, auth_context):
        raise HTTPException(status_code=404, detail="Source email not found")
    return source_email


@router.post("/from-email", response_model=CreateTasksFromEmailResponse)
async def create_tasks_from_email(
    request: CreateTasksFromEmailRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> CreateTasksFromEmailResponse:
    task_items = _validate_execution_items(request.task_items)
    source_email = await _fetch_source_email(db, request, auth_context)

    related_thread_id = canonical_thread_key(source_email) or request.thread_id
    ticket_tasks = [
        TicketTask(
            user_id=auth_context.user_id,
            organization_id=auth_context.organization_id,
            title=task_item,
            status="open",
            priority="normal",
            source_type="email",
            related_email_id=source_email.id,
            related_thread_id=related_thread_id,
        )
        for task_item in task_items
    ]
    for ticket_task in ticket_tasks:
        db.add(ticket_task)

    await db.commit()

    return CreateTasksFromEmailResponse(
        created_task_count=len(ticket_tasks),
        ticket_tasks=[
            _task_response(ticket_task, source_email.message_id)
            for ticket_task in ticket_tasks
        ],
    )
