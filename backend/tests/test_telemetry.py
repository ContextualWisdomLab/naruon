from fastapi import FastAPI
from core.telemetry import setup_telemetry, _TELEMETRY_STATE_KEY, _env_flag, _otel_endpoint_has_hostname
from unittest.mock import patch

def test_env_flag(monkeypatch):
    monkeypatch.delenv("TEST_FLAG", raising=False)
    assert not _env_flag("TEST_FLAG")
    assert _env_flag("TEST_FLAG", True)

    monkeypatch.setenv("TEST_FLAG", "1")
    assert _env_flag("TEST_FLAG")
    monkeypatch.setenv("TEST_FLAG", "true")
    assert _env_flag("TEST_FLAG")
    monkeypatch.setenv("TEST_FLAG", "YES")
    assert _env_flag("TEST_FLAG")
    monkeypatch.setenv("TEST_FLAG", "on")
    assert _env_flag("TEST_FLAG")

    monkeypatch.setenv("TEST_FLAG", "0")
    assert not _env_flag("TEST_FLAG")

def test_otel_endpoint_has_hostname():
    assert not _otel_endpoint_has_hostname("")
    assert not _otel_endpoint_has_hostname("   ")
    assert _otel_endpoint_has_hostname("http://localhost:4317")
    assert _otel_endpoint_has_hostname("localhost:4317")
    assert not _otel_endpoint_has_hostname("://")

def test_setup_telemetry_already_configured():
    app = FastAPI()
    setattr(app.state, _TELEMETRY_STATE_KEY, True)

    with patch("core.telemetry.logger.debug") as mock_debug:
        setup_telemetry(app)
        mock_debug.assert_called_with("OpenTelemetry instrumentation is already configured.")

def test_setup_telemetry_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_OTEL", raising=False)
    app = FastAPI()
    with patch("core.telemetry.logger.info") as mock_info:
        setup_telemetry(app)
        mock_info.assert_called_with("OpenTelemetry is disabled.")

def test_setup_telemetry_invalid_endpoint(monkeypatch):
    monkeypatch.setenv("ENABLE_OTEL", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "://")
    app = FastAPI()
    with patch("core.telemetry.logger.error") as mock_error:
        setup_telemetry(app)
        mock_error.assert_called_with("Invalid OTEL exporter endpoint URL: missing hostname; continuing without tracing.")

def test_setup_telemetry_success(monkeypatch):
    monkeypatch.setenv("ENABLE_OTEL", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_INSECURE", "true")

    app = FastAPI()

    with patch("opentelemetry.trace.set_tracer_provider"), \
         patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"), \
         patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"), \
         patch("opentelemetry.sdk.resources.Resource"), \
         patch("opentelemetry.sdk.trace.TracerProvider"), \
         patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"), \
         patch("core.telemetry.logger.info") as mock_info:

        setup_telemetry(app)

        assert getattr(app.state, _TELEMETRY_STATE_KEY, False) is True
        mock_info.assert_any_call("Setting up OpenTelemetry export.")
        mock_info.assert_any_call("OpenTelemetry instrumentation completed successfully.")

def test_setup_telemetry_exception(monkeypatch):
    monkeypatch.setenv("ENABLE_OTEL", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    app = FastAPI()

    with patch("opentelemetry.trace.set_tracer_provider") as mock_trace, \
         patch("core.telemetry.logger.exception") as mock_exception:

        mock_trace.side_effect = Exception("Test Exception")

        setup_telemetry(app)

        mock_exception.assert_called_with("OpenTelemetry setup failed; continuing without tracing.")
        assert not getattr(app.state, _TELEMETRY_STATE_KEY, False)
