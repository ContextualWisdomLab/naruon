from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context, is_admin_role, is_tenant_admin_role
from api.runner_config import _connector_manifest
from api.runner_ws import manager as runner_connection_manager
from core.config import settings
from db.models import (
    ConnectorSignalEvent,
    ProviderWritebackRetryItem,
    WorkspaceRunnerConfig,
)
from db.session import get_db

router = APIRouter(prefix="/api/observability", tags=["observability"])

SignalState = Literal[
    "enabled",
    "not_configured",
    "intent_only",
    "instrumentation_pending",
    "registration_configured",
    "not_registered",
]
QueueDepthState = Literal["clear", "backlog", "degraded"]


class TelemetryRuntime(BaseModel):
    prometheus_metrics_enabled: bool
    otel_traces_enabled: bool
    otel_endpoint_configured: bool
    otel_endpoint_host: str | None


class ConnectorSignalEventResponse(BaseModel):
    event_uid: str
    signal_key: str
    state_code: str
    detail_text: str | None
    observed_at: str


class ProviderWritebackQueueDepth(BaseModel):
    pending_count: int
    running_count: int
    failed_count: int
    total_count: int
    next_retry_at: str | None


class ConnectorOperationalState(BaseModel):
    workspace_id: str
    registration_state: Literal["registration_configured", "not_registered"]
    connection_state: Literal["connected", "not_connected"]
    active_connection_count: int
    control_plane_domain: str
    network_mode: str
    runner_usage: str
    local_protocols: list[str]
    last_heartbeat_at: str | None
    last_disconnect_at: str | None
    queue_depth_state: QueueDepthState
    queue_depth: ProviderWritebackQueueDepth
    recent_events: list[ConnectorSignalEventResponse]


class OperationalSignal(BaseModel):
    signal_key: str
    display_name: str
    state: SignalState
    evidence_source: str
    detail: str
    provider_write_executed: bool = False


class OperationalSignalsResponse(BaseModel):
    workspace_id: str
    audit_event: Literal["observability.operational_signals.viewed"]
    telemetry: TelemetryRuntime
    connector: ConnectorOperationalState
    signals: list[OperationalSignal]


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_event_time(
    recent_events: list[ConnectorSignalEventResponse],
    signal_key: str,
    state_codes: set[str],
) -> str | None:
    for event in recent_events:
        if event.signal_key == signal_key and event.state_code in state_codes:
            return event.observed_at
    return None


def _check_org_admin(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not is_admin_role(auth_context.role):
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ORG_ADMIN_REQUIRED",
                "message": "Organization admin access required",
            },
        )
    if is_tenant_admin_role(auth_context.role) and not auth_context.organization_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ORG_SCOPE_REQUIRED",
                "message": "Organization scope is required",
            },
        )
    if not auth_context.organization_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ORG_SCOPE_REQUIRED",
                "message": "Organization scope is required",
            },
        )
    return auth_context


async def _get_runner_config(
    db: AsyncSession, organization_id: str
) -> WorkspaceRunnerConfig | None:
    result = await db.execute(
        select(WorkspaceRunnerConfig).where(
            WorkspaceRunnerConfig.organization_id == organization_id
        )
    )
    return result.scalar_one_or_none()


async def _get_connector_signal_events(
    db: AsyncSession, organization_id: str, workspace_id: str
) -> list[ConnectorSignalEventResponse]:
    result = await db.execute(
        select(ConnectorSignalEvent)
        .where(
            ConnectorSignalEvent.organization_id == organization_id,
            ConnectorSignalEvent.workspace_id == workspace_id,
        )
        .order_by(ConnectorSignalEvent.observed_at.desc())
        .limit(8)
    )
    return [
        ConnectorSignalEventResponse(
            event_uid=event.event_uid,
            signal_key=event.signal_key,
            state_code=event.state_code,
            detail_text=event.detail_text,
            observed_at=_datetime_to_utc_iso(event.observed_at),
        )
        for event in result.scalars().all()
    ]


async def _get_writeback_retry_items(
    db: AsyncSession,
    organization_id: str,
    workspace_id: str,
) -> list[ProviderWritebackRetryItem]:
    result = await db.execute(
        select(ProviderWritebackRetryItem).where(
            ProviderWritebackRetryItem.organization_id == organization_id,
            ProviderWritebackRetryItem.workspace_id == workspace_id,
        )
    )
    return list(result.scalars().all())


def _queue_depth(
    retry_items: list[ProviderWritebackRetryItem],
) -> tuple[QueueDepthState, ProviderWritebackQueueDepth]:
    pending_items = [item for item in retry_items if item.retry_state == "pending"]
    running_items = [item for item in retry_items if item.retry_state == "running"]
    failed_items = [
        item for item in retry_items if item.retry_state.startswith("failed")
    ]
    next_retry_candidates = sorted(
        item.next_retry_at for item in pending_items if item.next_retry_at is not None
    )
    total_count = len(pending_items) + len(running_items) + len(failed_items)
    if failed_items:
        state: QueueDepthState = "degraded"
    elif pending_items or running_items:
        state = "backlog"
    else:
        state = "clear"
    return state, ProviderWritebackQueueDepth(
        pending_count=len(pending_items),
        running_count=len(running_items),
        failed_count=len(failed_items),
        total_count=total_count,
        next_retry_at=(
            _datetime_to_utc_iso(next_retry_candidates[0])
            if next_retry_candidates
            else None
        ),
    )


def _telemetry_runtime(request: Request) -> TelemetryRuntime:
    receiver_host = getattr(request.app.state, "naruon_telemetry_receiver_host", None)
    configured = bool(getattr(request.app.state, "naruon_telemetry_runtime", None))
    return TelemetryRuntime(
        prometheus_metrics_enabled=settings.ENABLE_PROMETHEUS_METRICS,
        otel_traces_enabled=configured and bool(receiver_host),
        otel_endpoint_configured=bool(receiver_host),
        otel_endpoint_host=receiver_host,
    )


def _connector_state(
    organization_id: str,
    workspace_id: str,
    config: WorkspaceRunnerConfig | None,
    recent_events: list[ConnectorSignalEventResponse],
    retry_items: list[ProviderWritebackRetryItem],
) -> ConnectorOperationalState:
    manifest = _connector_manifest()
    connection_snapshot = runner_connection_manager.snapshot(
        organization_id=organization_id,
        workspace_id=config.workspace_id if config is not None else workspace_id,
    )
    connection_state: Literal["connected", "not_connected"] = (
        "connected"
        if connection_snapshot.connection_state == "connected"
        else "not_connected"
    )
    registration_state: Literal["registration_configured", "not_registered"] = (
        "registration_configured"
        if config is not None and bool(config.registration_token)
        else "not_registered"
    )
    queue_depth_state, queue_depth = _queue_depth(retry_items)
    return ConnectorOperationalState(
        workspace_id=config.workspace_id if config is not None else workspace_id,
        registration_state=registration_state,
        connection_state=connection_state,
        active_connection_count=connection_snapshot.active_connection_count,
        control_plane_domain=str(manifest["control_plane_domain"]),
        network_mode=str(manifest["network_mode"]),
        runner_usage=str(manifest["runner_usage"]),
        local_protocols=list(manifest["local_protocols"]),
        last_heartbeat_at=connection_snapshot.last_seen_at
        or _latest_event_time(
            recent_events, "connector_heartbeat", {"connected", "heartbeat"}
        ),
        last_disconnect_at=connection_snapshot.last_disconnect_at
        or _latest_event_time(recent_events, "connector_heartbeat", {"disconnected"}),
        queue_depth_state=queue_depth_state,
        queue_depth=queue_depth,
        recent_events=recent_events,
    )


def _operational_signals(
    telemetry: TelemetryRuntime, connector: ConnectorOperationalState
) -> list[OperationalSignal]:
    metrics_state: SignalState = (
        "enabled" if telemetry.prometheus_metrics_enabled else "not_configured"
    )
    traces_state: SignalState = (
        "enabled" if telemetry.otel_traces_enabled else "not_configured"
    )
    return [
        OperationalSignal(
            signal_key="prometheus_metrics",
            display_name="Prometheus metrics",
            state=metrics_state,
            evidence_source="ENABLE_PROMETHEUS_METRICS",
            detail="Prometheus /metrics exposure is opt-in and remains behind a trusted scrape path.",
        ),
        OperationalSignal(
            signal_key="otel_traces",
            display_name="OpenTelemetry traces",
            state=traces_state,
            evidence_source="active shared telemetry runtime",
            detail="Trace export starts after the shared runtime is configured with an authenticated Collector.",
        ),
        OperationalSignal(
            signal_key="connector_heartbeat",
            display_name="Connector heartbeat",
            state="enabled" if connector.connection_state == "connected" else connector.registration_state,
            evidence_source="runner WebSocket manager and workspace_runner_configs.registration_token",
            detail="Live heartbeat uses active outbound runner sockets and durable connector_signal_events history.",
        ),
        OperationalSignal(
            signal_key="writeback_retry_queue",
            display_name="Writeback retry queue",
            state="enabled",
            evidence_source="provider_writeback_retry_items",
            detail=(
                f"{connector.queue_depth.total_count} queued writeback retry items are tracked by state."
            ),
        ),
        OperationalSignal(
            signal_key="sync_lag",
            display_name="Sync lag",
            state="instrumentation_pending",
            evidence_source="IMAP, POP3, CalDAV, CardDAV, WebDAV workers",
            detail="Provider sync lag will be emitted by source-backed connector jobs, not inferred in the browser.",
        ),
        OperationalSignal(
            signal_key="provider_throttling",
            display_name="Provider throttling",
            state="instrumentation_pending",
            evidence_source="provider adapters",
            detail="Throttle and retry budgets require provider adapter events before dashboard claims are enabled.",
        ),
        OperationalSignal(
            signal_key="writeback_conflicts",
            display_name="Writeback conflicts",
            state="intent_only",
            evidence_source="calendar and WebDAV writeback-intent APIs",
            detail="Conflict handling is surfaced at intent boundaries until connector write execution records ETags.",
        ),
        OperationalSignal(
            signal_key="ai_action_audit",
            display_name="AI action audit",
            state="instrumentation_pending",
            evidence_source="task, mail, ontology, and WebDAV intent APIs",
            detail="Audit event names are returned by intent APIs; centralized trace correlation is still planned.",
        ),
    ]


@router.get("/operational-signals", response_model=OperationalSignalsResponse)
async def get_operational_signals(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(_check_org_admin),
):
    organization_id = auth_context.organization_id
    if organization_id is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ORG_SCOPE_REQUIRED",
                "message": "Organization scope is required",
            },
        )

    workspace_id = auth_context.workspace_id
    config = await _get_runner_config(db, organization_id)
    connector_workspace_id = config.workspace_id if config is not None else workspace_id
    recent_events = await _get_connector_signal_events(
        db, organization_id, connector_workspace_id
    )
    retry_items = await _get_writeback_retry_items(
        db,
        organization_id,
        connector_workspace_id,
    )
    telemetry = _telemetry_runtime(request)
    connector = _connector_state(
        organization_id,
        workspace_id,
        config,
        recent_events,
        retry_items,
    )
    return OperationalSignalsResponse(
        workspace_id=connector.workspace_id,
        audit_event="observability.operational_signals.viewed",
        telemetry=telemetry,
        connector=connector,
        signals=_operational_signals(telemetry, connector),
    )
