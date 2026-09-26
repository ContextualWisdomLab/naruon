"""Naruon's explicit opt-in to the shared CWL telemetry runtime."""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from cwl_telemetry import TelemetryConfig


logger = logging.getLogger(__name__)
_TELEMETRY_STATE_KEY = "naruon_telemetry_configured"
_TELEMETRY_RUNTIME_KEY = "naruon_telemetry_runtime"
_TELEMETRY_RECEIVER_HOST_KEY = "naruon_telemetry_receiver_host"
_TELEMETRY_ROUTES_KEY = "naruon_telemetry_routes"
_TELEMETRY_MIDDLEWARE_KEY = "naruon_telemetry_middleware_installed"
_HTTP_ACTIONS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


def setup_telemetry(app: FastAPI, config: "TelemetryConfig | None" = None) -> None:
    """Instrument the app only after an operator supplies validated SDK config."""
    if not getattr(app.state, _TELEMETRY_MIDDLEWARE_KEY, False):
        @app.middleware("http")
        async def trace_request(request: Request, call_next):
            runtime = getattr(request.app.state, _TELEMETRY_RUNTIME_KEY, None)
            if runtime is None or not getattr(request.app.state, _TELEMETRY_STATE_KEY, False):
                return await call_next(request)
            from opentelemetry.context import attach, detach

            parent = attach(runtime.extract_trace(request.headers))
            try:
                with runtime.tracer.start_as_current_span(
                    "http_request",
                    {"operation_code": "http_request", "bounded_context": "backend"},
                ) as span:
                    started = time.monotonic_ns()
                    status_code = 500
                    try:
                        response = await call_next(request)
                        if type(response.status_code) is int and 100 <= response.status_code <= 599:
                            status_code = response.status_code
                        return response
                    finally:
                        span.set_attribute("action", request.method.lower() if request.method in _HTTP_ACTIONS else "unknown")
                        span.set_attribute("status", f"http_{status_code}")
                        span.set_attribute("result", "success" if status_code < 400 else "failure")
                        span.set_attribute("duration_ms", min(max((time.monotonic_ns() - started) / 1_000_000, 0), 1_000_000_000))
                        route = request.scope.get("route")
                        template = getattr(route, "path_format", None)
                        routes = getattr(request.app.state, _TELEMETRY_ROUTES_KEY, frozenset())
                        if isinstance(template, str) and template in routes:
                            span.set_attribute("http_route", template)
            finally:
                detach(parent)

        setattr(app.state, _TELEMETRY_MIDDLEWARE_KEY, True)
    if getattr(app.state, _TELEMETRY_STATE_KEY, False):
        logger.debug("OpenTelemetry instrumentation is already configured.")
        return
    if config is None:
        logger.info("OpenTelemetry is disabled.")
        return

    runtime = None
    try:
        from cwl_telemetry import bootstrap

        runtime = bootstrap(config)

        setattr(app.state, _TELEMETRY_RUNTIME_KEY, runtime)
        setattr(app.state, _TELEMETRY_ROUTES_KEY, config.route_templates)
        setattr(
            app.state,
            _TELEMETRY_RECEIVER_HOST_KEY,
            urlsplit(config.receiver).netloc if config.receiver else None,
        )
        setattr(app.state, _TELEMETRY_STATE_KEY, True)
        logger.info("OpenTelemetry instrumentation completed successfully.")
    except Exception:
        if runtime is not None:
            runtime.shutdown()
        logger.error("OpenTelemetry setup failed; continuing without tracing.")


def _source_revision() -> str:
    """Read the exact source revision sealed into the built image."""
    for root in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
        candidate = root / ".source-revision"
        if candidate.is_file():
            return candidate.read_text(encoding="ascii").strip()
    return ""


async def activate_deployment_telemetry(app: FastAPI) -> None:
    """Load the operator's encrypted receiver credential before serving requests."""
    try:
        from core.version import get_release_version
        from db.models import TelemetryDeploymentConfig
        from db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            deployment = await session.get(TelemetryDeploymentConfig, 1)
            if deployment is None or not deployment.enabled:
                return
            from cwl_telemetry import TelemetryConfig

            routes = frozenset(
                route.path_format for route in app.routes
                if isinstance(getattr(route, "path_format", None), str)
            )
            config = TelemetryConfig(
                service="naruon-backend", version=get_release_version(),
                environment=deployment.environment, source_revision=_source_revision(),
                receiver=deployment.receiver, token=deployment.bearer_token,
                ca_file=deployment.ca_file,
                operation_codes={"http_request"}, bounded_contexts={"backend"},
                route_templates=routes,
            )
        setup_telemetry(app, config)
    except Exception:
        logger.error("OpenTelemetry configuration unavailable; continuing without tracing.")


def shutdown_telemetry(app: FastAPI) -> None:
    """Release the optional shared runtime and reset app telemetry state."""
    runtime = getattr(app.state, _TELEMETRY_RUNTIME_KEY, None)
    if runtime is not None:
        runtime.shutdown()
        setattr(app.state, _TELEMETRY_RUNTIME_KEY, None)
        setattr(app.state, _TELEMETRY_RECEIVER_HOST_KEY, None)
        setattr(app.state, _TELEMETRY_ROUTES_KEY, frozenset())
        setattr(app.state, _TELEMETRY_STATE_KEY, False)
