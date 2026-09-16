import builtins
import logging


def test_setup_telemetry_redacts_exception_value_and_traceback(monkeypatch, caplog):
    from fastapi import FastAPI

    from core import telemetry

    app = FastAPI()
    secret_connection = "postgresql://telemetry-user:secret-password@db.internal/naruon"
    secret_path = "/srv/naruon/private/provider-token.txt"
    failure_detail = (
        f"provider bootstrap failed token=sk-telemetry-secret "
        f"connection={secret_connection} path={secret_path}"
    )
    original_import = builtins.__import__

    def raise_on_otel_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "opentelemetry":
            raise RuntimeError(failure_detail)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setenv("ENABLE_OTEL", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "collector.example.com:4317")
    monkeypatch.setattr(builtins, "__import__", raise_on_otel_import)
    caplog.set_level(logging.ERROR, logger=telemetry.logger.name)

    telemetry.setup_telemetry(app)

    telemetry_records = [
        record for record in caplog.records if record.name == telemetry.logger.name
    ]
    rendered = "\n".join(
        logging.Formatter("%(levelname)s %(message)s").format(record)
        for record in telemetry_records
    )

    assert getattr(app.state, "naruon_telemetry_configured", False) is False
    assert "OpenTelemetry setup failed; continuing without tracing." in rendered
    assert "exception_type=RuntimeError" in rendered
    assert "exception_fingerprint=" in rendered
    assert "sk-telemetry-secret" not in rendered
    assert secret_connection not in rendered
    assert secret_path not in rendered
    assert "Traceback (most recent call last)" not in rendered
