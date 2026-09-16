"""
Tests for app.tools.discovery.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.tools import discovery
from app.tools.discovery import (
    discover_app,
    discover_known_app,
    is_app_installed,
    APP_HINTS,
)


def test_discover_app_config_path(tmp_path):
    """Explicit config path wins."""
    exe = tmp_path / "fake.exe"
    exe.write_bytes(b"x")
    result = discover_app("fake.exe", config_path=str(exe))
    assert result == str(exe)


def test_discover_app_config_path_missing(tmp_path):
    """Missing config path falls through to other methods."""
    missing = tmp_path / "missing.exe"
    with patch.object(discovery, "_lookup_registry", return_value=None), \
         patch.object(discovery, "_lookup_path", return_value=None):
        result = discover_app("missing.exe", config_path=str(missing))
    assert result is None


def test_discover_app_via_registry():
    with patch.object(discovery, "_lookup_registry", return_value="C:/fake/path.exe"):
        result = discover_app("path.exe")
    assert result == "C:/fake/path.exe"


def test_discover_app_via_path():
    with patch.object(discovery, "_lookup_registry", return_value=None), \
         patch.object(discovery, "_lookup_path", return_value="/usr/bin/foo"):
        result = discover_app("foo")
    assert result == "/usr/bin/foo"


def test_discover_app_via_filesystem(tmp_path):
    with patch.object(discovery, "_lookup_registry", return_value=None), \
         patch.object(discovery, "_lookup_path", return_value=None), \
         patch.object(discovery, "_lookup_filesystem", return_value="C:/found.exe"):
        result = discover_app("found.exe", install_subpaths=["Some/Path/found.exe"])
    assert result == "C:/found.exe"


def test_discover_known_app_unknown_key():
    assert discover_known_app("nonexistent_app_xyz") is None


def test_app_hints_contains_expected_apps():
    expected = [
        "blender", "unreal", "cinema4d",
        "photoshop", "illustrator", "premiere", "after_effects",
        "capcut", "word", "excel", "powerpoint", "outlook", "onenote",
        "ffmpeg", "vscode", "visual_studio", "android_studio",
        "unity", "webstorm", "flutter", "xampp", "wamp", "python",
    ]
    for key in expected:
        assert key in APP_HINTS, f"missing hint for {key}"


def test_is_app_installed_false():
    with patch.object(discovery, "discover_app", return_value=None):
        assert is_app_installed("nope.exe") is False


def test_is_app_installed_true():
    with patch.object(discovery, "discover_app", return_value="/usr/bin/x"):
        assert is_app_installed("x") is True