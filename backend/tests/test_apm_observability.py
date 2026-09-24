from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent.parent

def test_observability_compose_file_exists():
    assert (ROOT_DIR / "docker-compose.infra.yml").exists()


def test_observability_provisioning_exists():
    assert (
        ROOT_DIR / "observability/grafana/provisioning/datasources/datasources.yaml"
    ).exists()
    assert (ROOT_DIR / "observability/prometheus.yml").exists()
    assert (ROOT_DIR / "observability/tempo.yaml").exists()


def test_backend_metrics_endpoint_is_disabled_by_default():
    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 404


def test_metrics_exposure_requires_explicit_environment_gate():
    main_source = (ROOT_DIR / "backend/main.py").read_text()

    assert "ENABLE_PROMETHEUS_METRICS" in main_source
    assert "Instrumentator().instrument(app).expose" in main_source


def test_open_telemetry_setup_is_centralized_and_opt_in_by_default():
    main_source = (ROOT_DIR / "backend/main.py").read_text()
    telemetry_source = (ROOT_DIR / "backend/core/telemetry.py").read_text()

    assert "setup_telemetry(app)" in main_source
    assert "FastAPIInstrumentor.instrument_app(app)" not in main_source
    assert "from cwl_telemetry import bootstrap" in telemetry_source
    assert "runtime.tracer.start_as_current_span" in telemetry_source
    assert "FastAPIInstrumentor" not in telemetry_source
    assert "OTLPSpanExporter" not in telemetry_source
    assert "TracerProvider(" not in telemetry_source
    assert "OTEL_EXPORTER_OTLP_INSECURE" not in telemetry_source
    assert "except Exception" in telemetry_source


def test_telemetry_does_not_instrument_without_explicit_config():
    from fastapi import FastAPI
    from core import telemetry

    app = FastAPI()
    telemetry.setup_telemetry(app)

    assert getattr(app.state, "naruon_telemetry_configured", False) is False


def test_fastapi_instrumentation_uses_shared_sdk_provider():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core import telemetry
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    cwl_telemetry = pytest.importorskip("cwl_telemetry")

    app = FastAPI()
    app.add_api_route("/private/{item_id}", lambda item_id: {"ok": True})

    def failing_handler(item_id):
        raise RuntimeError("secret-exception-message")

    app.add_api_route("/failure/{item_id}", failing_handler)
    config = cwl_telemetry.TelemetryConfig(
        service="naruon-backend",
        version="0.14.4",
        environment="test",
        source_revision="a" * 40,
        route_templates=frozenset({"/private/{item_id}", "/failure/{item_id}"}),
    )

    telemetry.setup_telemetry(app, config)
    runtime = app.state.naruon_telemetry_runtime
    exporter = InMemorySpanExporter()
    runtime._providers[0].add_span_processor(SimpleSpanProcessor(exporter))
    parent_trace_id = "1" * 32
    parent_span_id = "2" * 16
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(
            "/private/secret-id?token=secret-query",
            headers={
                "traceparent": f"00-{parent_trace_id}-{parent_span_id}-01",
                "baggage": "credential=secret-baggage",
            },
        ).status_code == 200
        assert client.get("/failure/secret-id?token=secret-query").status_code == 500
    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    assert all(span.name == "http_request" for span in spans)
    assert all("secret-id" not in str(span.attributes) for span in spans)
    assert all("secret-query" not in str(span.attributes) for span in spans)
    assert all("secret-exception-message" not in str(span.events) for span in spans)
    assert all("secret-exception-message" not in str(span.status) for span in spans)
    assert all("secret-baggage" not in str(span.attributes) for span in spans)
    assert spans[0].context.trace_id == int(parent_trace_id, 16)
    assert spans[0].parent.span_id == int(parent_span_id, 16)
    assert spans[0].attributes["http_route"] == "/private/{item_id}"
    assert getattr(app.state, "naruon_telemetry_configured", False)
    telemetry.setup_telemetry(app, config)
    assert app.state.naruon_telemetry_runtime is runtime
    telemetry.shutdown_telemetry(app)
    assert app.state.naruon_telemetry_runtime is None


def test_deployment_can_activate_after_app_start_without_registering_middleware_late():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core import telemetry
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    cwl_telemetry = pytest.importorskip("cwl_telemetry")
    app = FastAPI()
    telemetry.setup_telemetry(app)
    app.add_api_route("/ready", lambda: {"ok": True})
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        telemetry.setup_telemetry(app, cwl_telemetry.TelemetryConfig(
            service="naruon-backend", version="0.14.4", environment="test",
            source_revision="a" * 40, route_templates={"/ready"},
        ))
        exporter = InMemorySpanExporter()
        app.state.naruon_telemetry_runtime._providers[0].add_span_processor(
            SimpleSpanProcessor(exporter)
        )
        assert client.get("/ready").status_code == 200
    assert [span.attributes["http_route"] for span in exporter.get_finished_spans()] == ["/ready"]
    telemetry.shutdown_telemetry(app)


def test_deployment_credential_is_encrypted_at_rest(monkeypatch):
    from cryptography.fernet import Fernet
    from pydantic import SecretStr
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from core.config import settings
    from db.models import TelemetryDeploymentConfig

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", SecretStr(Fernet.generate_key().decode()))
    engine = create_engine("sqlite:///:memory:")
    TelemetryDeploymentConfig.__table__.create(engine)
    token = "synthetic-telemetry-token-12345"
    with Session(engine) as session:
        session.add(TelemetryDeploymentConfig(
            id=1, receiver="https://collector.example", bearer_token=token,
            environment="test", enabled=True,
        ))
        session.commit()
        raw = session.execute(text("SELECT bearer_token FROM telemetry_deployment_config")).scalar_one()
        assert token not in raw
        assert session.get(TelemetryDeploymentConfig, 1).bearer_token == token
    engine.dispose()


def test_startup_loads_enabled_credential_without_exposing_token(monkeypatch, caplog):
    import asyncio
    from types import SimpleNamespace
    from fastapi import FastAPI
    from core import telemetry
    from db import session as db_session

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _model, key):
            assert key == 1
            return SimpleNamespace(
                enabled=True, environment="test", receiver="https://127.0.0.1:1",
                bearer_token="synthetic-telemetry-token-12345", ca_file=None,
            )

    monkeypatch.setattr(db_session, "AsyncSessionLocal", Session)
    monkeypatch.setattr(telemetry, "_source_revision", lambda: "a" * 40)
    app = FastAPI()
    telemetry.setup_telemetry(app)
    app.add_api_route("/ready", lambda: {"ok": True})
    asyncio.run(telemetry.activate_deployment_telemetry(app))

    assert app.state.naruon_telemetry_configured is True
    assert app.state.naruon_telemetry_receiver_host == "127.0.0.1:1"
    assert "/ready" in app.state.naruon_telemetry_routes
    assert "synthetic-telemetry-token-12345" not in caplog.text
    telemetry.shutdown_telemetry(app)


def test_operator_cli_does_not_expose_credentials_on_preflight_error():
    import os
    import subprocess
    import sys

    environment = dict(os.environ, PYTHONPATH=".")
    environment.pop("DATABASE_URL", None)
    token = "synthetic-telemetry-token-12345"
    help_result = subprocess.run(
        [sys.executable, "-m", "scripts.configure_telemetry", "--help"],
        capture_output=True, text=True, env=environment, check=False,
    )
    assert help_result.returncode == 0
    result = subprocess.run(
        [sys.executable, "-m", "scripts.configure_telemetry",
         "--receiver", "http://collector.example", "--environment", "prod"],
        input=token + "\n", capture_output=True, text=True,
        env=environment, check=False,
    )
    assert result.returncode != 0
    assert "Telemetry provisioning failed" in result.stderr
    assert token not in result.stderr


def test_sdk_rejects_plaintext_or_missing_revision_before_bootstrap():
    cwl_telemetry = pytest.importorskip("cwl_telemetry")

    base = dict(service="naruon-backend", version="0.14.4", environment="test")
    with pytest.raises(ValueError, match="source_revision"):
        cwl_telemetry.TelemetryConfig(**base, source_revision="unknown")
    with pytest.raises(ValueError, match="receiver"):
        cwl_telemetry.TelemetryConfig(
            **base,
            source_revision="a" * 40,
            receiver="http://collector.example:4318",
            token="scoped-token-123456",
        )
