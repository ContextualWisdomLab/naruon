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
    with patch("shutil.which", return_value=binary), patch(
        "urllib.request.urlopen"
    ) as request:
        request.return_value.status = 200
        with pytest.raises(SystemExit) as result:
            exec(command)
        assert result.value.code == expected
        assert request.called == bool(binary)
