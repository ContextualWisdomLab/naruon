import os
from pathlib import Path
from core.env_paths import operator_home, expand_operator_path

def test_operator_home_with_env(monkeypatch):
    monkeypatch.setenv("HOME", "/custom/home")
    assert operator_home() == Path("/custom/home").expanduser()

def test_operator_home_without_env(monkeypatch):
    monkeypatch.delenv("HOME", raising=False)
    assert operator_home() == Path.home()

def test_expand_operator_path_tilde(monkeypatch):
    monkeypatch.setenv("HOME", "/custom/home")
    assert expand_operator_path("~") == Path("/custom/home").expanduser()

def test_expand_operator_path_tilde_slash(monkeypatch):
    monkeypatch.setenv("HOME", "/custom/home")
    assert expand_operator_path("~/foo") == Path("/custom/home").expanduser() / "foo"

def test_expand_operator_path_tilde_backslash(monkeypatch):
    monkeypatch.setenv("HOME", "/custom/home")
    assert expand_operator_path("~\\foo") == Path("/custom/home").expanduser() / "foo"

def test_expand_operator_path_normal():
    assert expand_operator_path("/absolute/path") == Path("/absolute/path")
