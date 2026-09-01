"""Semantic naming contracts for Naruon's ticket-task API models."""

import datetime

from api.tasks import (
    CreateTasksFromEmailRequest,
    CreateTasksFromEmailResponse,
    ReplySlaEscalationRequest,
    ReplySlaEscalationResponse,
    ReplySlaPolicyResponse,
    TicketTaskResponse,
    UpdateTicketTaskRequest,
)


def _ticket_task_response() -> TicketTaskResponse:
    """Build one task using only the organization-owned semantic field names."""
    observed_at = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
    return TicketTaskResponse(
        task_uid="task-public-1",
        task_title="Confirm rehearsal owner",
        task_status="open",
        task_priority="high",
        source_type="email",
        source_email_id="<source@example.com>",
        related_thread_id="thread-1",
        created_at=observed_at,
        updated_at=observed_at,
    )


def test_ticket_task_models_use_semantically_specific_internal_fields() -> None:
    """Reject generic one-word fields where the ticket-task meaning is known."""
    assert {"task_uid", "task_title", "task_status", "task_priority"} <= set(
        TicketTaskResponse.model_fields
    )
    assert {"id", "title", "status", "priority"}.isdisjoint(
        TicketTaskResponse.model_fields
    )

    assert "task_items" in CreateTasksFromEmailRequest.model_fields
    assert "items" not in CreateTasksFromEmailRequest.model_fields
    assert {"created_task_count", "ticket_tasks"} <= set(
        CreateTasksFromEmailResponse.model_fields
    )
    assert {"created", "tasks"}.isdisjoint(CreateTasksFromEmailResponse.model_fields)

    assert "escalation_limit" in ReplySlaEscalationRequest.model_fields
    assert "limit" not in ReplySlaEscalationRequest.model_fields
    assert {
        "evaluated_email_count",
        "created_task_count",
        "reply_sla_policy",
        "ticket_tasks",
    } <= set(ReplySlaEscalationResponse.model_fields)
    assert {"evaluated", "created", "policy", "tasks"}.isdisjoint(
        ReplySlaEscalationResponse.model_fields
    )

    assert {"task_status", "task_priority"} <= set(UpdateTicketTaskRequest.model_fields)
    assert {"status", "priority"}.isdisjoint(UpdateTicketTaskRequest.model_fields)


def test_ticket_task_models_preserve_established_wire_keys_through_aliases() -> None:
    """Keep current clients compatible while internal task language becomes specific."""
    ticket_task = _ticket_task_response()
    task_wire = ticket_task.model_dump(by_alias=True)

    assert task_wire["id"] == "task-public-1"
    assert task_wire["title"] == "Confirm rehearsal owner"
    assert task_wire["status"] == "open"
    assert task_wire["priority"] == "high"
    assert "task_uid" not in task_wire
    assert "task_title" not in task_wire
    assert "task_status" not in task_wire
    assert "task_priority" not in task_wire

    create_request = CreateTasksFromEmailRequest.model_validate(
        {
            "source_email_id": "<source@example.com>",
            "thread_id": "thread-1",
            "items": ["Confirm rehearsal owner"],
        }
    )
    assert create_request.task_items == ["Confirm rehearsal owner"]

    update_request = UpdateTicketTaskRequest.model_validate(
        {"status": "done", "priority": "urgent"}
    )
    assert update_request.task_status == "done"
    assert update_request.task_priority == "urgent"

    escalation_request = ReplySlaEscalationRequest.model_validate(
        {"overdue_hours": 48, "limit": 7}
    )
    assert escalation_request.escalation_limit == 7

    create_wire = CreateTasksFromEmailResponse(
        created_task_count=1,
        ticket_tasks=[ticket_task],
    ).model_dump(by_alias=True)
    assert create_wire["created"] == 1
    assert create_wire["tasks"][0]["id"] == "task-public-1"

    escalation_wire = ReplySlaEscalationResponse(
        evaluated_email_count=2,
        created_task_count=1,
        reply_sla_policy=ReplySlaPolicyResponse(overdue_hours=48),
        ticket_tasks=[ticket_task],
    ).model_dump(by_alias=True)
    assert escalation_wire["evaluated"] == 2
    assert escalation_wire["created"] == 1
    assert escalation_wire["policy"] == {"overdue_hours": 48}
    assert escalation_wire["tasks"][0]["id"] == "task-public-1"
