from pathlib import Path

import pytest

from core.env_paths import (
    ENV_FILE_PATHS,
    expand_operator_path,
    operator_env_file_paths,
    operator_home,
)


def test_operator_home_resolves_home_override(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    assert operator_home() == home.resolve()
    assert expand_operator_path("~/.env") == home.resolve() / ".env"


def test_operator_home_rejects_symlink(monkeypatch, tmp_path: Path) -> None:
    real_home = tmp_path / "real-home"
    linked_home = tmp_path / "linked-home"
    real_home.mkdir()
    linked_home.symlink_to(real_home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(linked_home))

    with pytest.raises(ValueError, match="non-symlink"):
        operator_home()


def test_expand_operator_path_rejects_home_escape(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    with pytest.raises(ValueError, match="escapes"):
        expand_operator_path("~/../outside.env")


def test_operator_env_file_paths_default(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    paths = operator_env_file_paths()
    expected = tuple(str(expand_operator_path(p)) for p in ENV_FILE_PATHS)
    assert paths == expected
    assert str(home.resolve() / ".env") in paths


def test_operator_env_file_paths_custom(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    custom_paths = ["~/.env.custom", "local.env", "~"]
    paths = operator_env_file_paths(custom_paths)
    expected = (
        str(home.resolve() / ".env.custom"),
        "local.env",
        str(home.resolve()),
    )
    assert paths == expected
