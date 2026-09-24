"""Naruon's explicit opt-in to the shared CWL telemetry runtime."""

import logging
import os
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


def setup_telemetry(app: FastAPI, config: "TelemetryConfig | None" = None) -> None:
    """Instrument the app only after an operator supplies validated SDK config."""
    if getattr(app.state, _TELEMETRY_STATE_KEY, False):
        logger.debug("OpenTelemetry instrumentation is already configured.")
        return
    if config is None:
        if "CWL_TELEMETRY_RECEIVER" not in os.environ:
            logger.info("OpenTelemetry is disabled.")
            return
        try:
            from core.config import settings
            from cwl_telemetry import TelemetryConfig

            config = TelemetryConfig(
                service="naruon-backend", version=app.version,
                environment=settings.RUNTIME_ENVIRONMENT,
                source_revision=os.environ["CWL_SOURCE_REVISION"],
                receiver=os.environ["CWL_TELEMETRY_RECEIVER"],
                token=Path(os.environ["CWL_TELEMETRY_TOKEN_FILE"])
                .read_text(encoding="utf-8")
                .rstrip("\n"),
                ca_file=os.environ.get("CWL_TELEMETRY_CA_FILE"),
                operation_codes={"http_request"}, bounded_contexts={"backend"},
            )
        except Exception:
            logger.exception("OpenTelemetry configuration rejected; continuing without tracing.")
            return

    runtime = None
    try:
        from cwl_telemetry import bootstrap
        from opentelemetry.context import attach, detach

        runtime = bootstrap(config)

        @app.middleware("http")
        async def trace_request(request: Request, call_next):
            parent = attach(runtime.extract_trace(request.headers))
            try:
                with runtime.tracer.start_as_current_span(
                    "http_request",
                    {"operation_code": "http_request", "bounded_context": "backend"},
                ) as span:
                    try:
                        return await call_next(request)
                    finally:
                        route = request.scope.get("route")
                        template = getattr(route, "path_format", None)
                        if isinstance(template, str) and template in config.route_templates:
                            span.set_attribute("http_route", template)
            finally:
                detach(parent)

        setattr(app.state, _TELEMETRY_RUNTIME_KEY, runtime)
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
        logger.exception("OpenTelemetry setup failed; continuing without tracing.")


def shutdown_telemetry(app: FastAPI) -> None:
    """Release the optional shared runtime and reset app telemetry state."""
    runtime = getattr(app.state, _TELEMETRY_RUNTIME_KEY, None)
    if runtime is not None:
        runtime.shutdown()
        setattr(app.state, _TELEMETRY_RUNTIME_KEY, None)
        setattr(app.state, _TELEMETRY_RECEIVER_HOST_KEY, None)
        setattr(app.state, _TELEMETRY_STATE_KEY, False)
