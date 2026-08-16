"""Signed-session API for in-process Noema judgments."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.session import get_db
from services.agent_registry import resolve_agent_for_task
from services.noema_agent import run_noema_decision

router = APIRouter(prefix="/api/noema", tags=["noema"])


class NoemaDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgment_kind: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=8000)
    writeback_enabled: bool = False


class NoemaDecisionResponse(BaseModel):
    status: Literal["ok", "unavailable", "error"]
    judgment_kind: str
    recommendation: str = ""
    rationale: str = ""
    notice: str | None = None
    error_code: str | None = None
    model_alias: str | None = None
    tool_calls: list[str] = Field(default_factory=list)


@router.post("/decisions", response_model=None)
async def create_noema_decision(
    body: NoemaDecisionRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
):
    agent = resolve_agent_for_task(body.judgment_kind)
    if agent is None or agent.agent_role != "decision":
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "unknown_judgment_kind",
                "judgment_kind": body.judgment_kind,
            },
        )

    result = await run_noema_decision(
        session,
        user_id=auth_context.user_id,
        organization_id=auth_context.organization_id,
        workspace_id=auth_context.workspace_id,
        judgment_kind=body.judgment_kind,
        prompt=body.prompt,
        writeback_enabled=body.writeback_enabled,
    )
    return NoemaDecisionResponse(
        status=result.status,
        judgment_kind=result.judgment_kind,
        recommendation=result.recommendation,
        rationale=result.rationale,
        notice=result.notice,
        error_code=result.error_code,
        model_alias=result.model_alias,
        tool_calls=list(result.tool_calls),
    )
