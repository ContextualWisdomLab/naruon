"""Verify the optional runtime probe rejects a live API without MinerU."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


@pytest.mark.parametrize("binary, expected", [(None, 1), ("/app/.venv/bin/mineru", 0)])
def test_nvidia_runtime_probe_requires_mineru(binary, expected):
    configuration = yaml.safe_load(
        (Path(__file__).parents[2] / "docker-compose.newsdom-nvidia.yml").read_text()
    )
    command = configuration["services"]["newsdom"]["healthcheck"]["test"][3]
    with (
        patch("shutil.which", return_value=binary),
        patch("urllib.request.urlopen") as request,
    ):
        request.return_value.status = 200
        with pytest.raises(SystemExit) as result:
            exec(command)
        assert result.value.code == expected
        assert request.called == bool(binary)
        if binary:
            request.assert_called_once_with("http://localhost:8000/ready")


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("nvidia", [False, True])
def test_compose_forwards_existing_extraction_settings(configured, nvidia):
    import json
    import os
    import shutil
    import subprocess

    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker Compose CLI unavailable")
    environment = {
        "PATH": os.environ["PATH"],
        "POSTGRES_PASSWORD": "synthetic",
        "AUTH_SESSION_HMAC_SECRET": "synthetic",
        "ENCRYPTION_KEY": "synthetic",
    }
    expected = {
        "PROJECT_GRAPH_EXTRACTION_ENABLED": "false",
        "PROJECT_GRAPH_EXTRACTOR": "keyword",
        "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL": "",
        "ALLOWED_LLM_BASE_URL_HOSTS": "ollama",
    }
    if configured:
        expected.update(
            PROJECT_GRAPH_EXTRACTION_ENABLED="true",
            PROJECT_GRAPH_EXTRACTOR="orchestrator",
            PROJECT_GRAPH_ORCHESTRATOR_BASE_URL="http://orchestrator:8000/v1",
        )
        environment.update(expected)
        environment["NEWSDOM_API_TOKEN"] = "synthetic-parser-token"
    result = subprocess.run(
        [
            docker,
            "compose",
            "--profile",
            "newsdom",
            "--env-file",
            "/dev/null",
            "-f",
            "docker-compose.yml",
            *(["-f", "docker-compose.newsdom-nvidia.yml"] if nvidia else []),
            "config",
            "--format",
            "json",
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)["services"]["backend"]["environment"]
    assert {key: actual[key] for key in expected} == expected

    newsdom = json.loads(result.stdout)["services"]["newsdom"]
    assert newsdom["environment"] == {
        "NEWSDOM_API_TOKEN": "synthetic-parser-token" if configured else "",
        "NEWSDOM_AUTH_MODE": "required",
        "NEWSDOM_RUNTIME_PROFILE": "production",
    }
    assert "/ready" in newsdom["healthcheck"]["test"][-1]
    assert newsdom["build"]["context"].endswith(
        "#65696f393224a1e08ab42fff5151cbf3639a8a4e"
    )

    assert newsdom["read_only"] is True
    assert "no-new-privileges:true" in newsdom["security_opt"]
    assert "/tmp" in newsdom["tmpfs"]
    assert any(
        mount["type"] == "volume"
        and mount["source"] == "newsdom-model-cache"
        and mount["target"] == "/home/newsdom"
        for mount in newsdom["volumes"]
    )
