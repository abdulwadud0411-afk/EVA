"""Tests for Phase 22 Batch 2 — integrity + anti-debug + paths."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core import paths
from app.security import integrity_check


# ---------------------------------------------------------------------- #
# Paths
# ---------------------------------------------------------------------- #
def test_is_frozen_false_in_dev():
    # Running under pytest = not frozen
    assert paths.is_frozen() is False


def test_get_app_root_exists():
    root = paths.get_app_root()
    assert root.exists()
    assert root.is_dir()


def test_get_data_dir_created():
    d = paths.get_data_dir()
    assert d.exists()
    assert d.is_dir()


def test_get_config_dir_points_to_config():
    c = paths.get_config_dir()
    assert c.name == "config"
    assert c.exists()


def test_get_prompts_dir():
    p = paths.get_prompts_dir()
    assert p.name == "prompts"


def test_get_assets_dir():
    a = paths.get_assets_dir()
    assert a.name == "assets"


def test_get_models_dir_created():
    m = paths.get_models_dir()
    assert m.exists()


def test_get_logs_dir_created():
    lg = paths.get_logs_dir()
    assert lg.exists()
    assert lg.name == "logs"


def test_describe_shape():
    info = paths.describe()
    for key in ("frozen", "app_root", "data_dir", "config_dir",
                "models_dir", "prompts_dir", "assets_dir"):
        assert key in info


# ---------------------------------------------------------------------- #
# Manifest build + verify
# ---------------------------------------------------------------------- #
def test_build_manifest_returns_files(tmp_path):
    # Create a mini root (use exist_ok=True — the conftest fixture
    # already creates `config/` inside tmp_path)
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "a.py").write_text("print(1)")
    (tmp_path / "app" / "b.py").write_text("print(2)")
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "config.yaml").write_text("x: 1")

    m = integrity_check.build_manifest(root=tmp_path)
    # app/ has 2 .py files, config/ has 1 .yaml
    # Note: conftest fixture may leave extra files, so check >= instead of ==
    assert m["file_count"] >= 3
    assert "app/a.py" in m["files"]
    assert "app/b.py" in m["files"]
    assert "config/config.yaml" in m["files"]


def test_verify_ok(tmp_path):
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "a.py").write_text("x")

    m = integrity_check.build_manifest(root=tmp_path)
    r = integrity_check.verify(m, root=tmp_path)
    assert r["ok"] is True
    assert r["modified"] == []
    assert r["missing"] == []


def test_verify_detects_modified(tmp_path):
    (tmp_path / "app").mkdir(exist_ok=True)
    f = tmp_path / "app" / "a.py"
    f.write_text("version1")
    ...

    m = integrity_check.build_manifest(root=tmp_path)

    f.write_text("version2 - TAMPERED")

    r = integrity_check.verify(m, root=tmp_path)
    assert r["ok"] is False
    assert "app/a.py" in r["modified"]


def test_verify_detects_missing(tmp_path):
    (tmp_path / "app").mkdir()
    f = tmp_path / "app" / "a.py"
    f.write_text("x")

    m = integrity_check.build_manifest(root=tmp_path)
    f.unlink()

    r = integrity_check.verify(m, root=tmp_path)
    assert r["ok"] is False
    assert "app/a.py" in r["missing"]


def test_verify_reports_added(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.py").write_text("x")

    m = integrity_check.build_manifest(root=tmp_path)
    (tmp_path / "app" / "new.py").write_text("y")

    r = integrity_check.verify(m, root=tmp_path)
    # Added files don't break the check, but are reported
    assert "app/new.py" in r["added"]


def test_save_and_load_manifest(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.py").write_text("x")
    m = integrity_check.build_manifest(root=tmp_path)

    p = tmp_path / "manifest.json"
    integrity_check.save_manifest(m, p)
    assert p.exists()

    loaded = integrity_check.load_manifest(p)
    assert loaded is not None
    assert loaded["file_count"] == m["file_count"]


def test_load_manifest_missing_returns_none(tmp_path):
    assert integrity_check.load_manifest(tmp_path / "nope.json") is None


# ---------------------------------------------------------------------- #
# Anti-debug
# ---------------------------------------------------------------------- #
def test_anti_debug_check_returns_dict():
    from app.security import anti_debug_check
    r = anti_debug_check()
    assert "debugger" in r
    assert isinstance(r["debugger"], bool)


def test_anti_debug_does_not_crash():
    from app.security import is_debugger_present
    # Under pytest, sys.gettrace() may be set — we just ensure no exception
    _ = is_debugger_present()


# ---------------------------------------------------------------------- #
# Anti-tamper
# ---------------------------------------------------------------------- #
def test_anti_tamper_check_returns_dict():
    from app.security import anti_tamper_check
    r = anti_tamper_check()
    assert "exe_hash_match" in r
    assert "files_intact" in r


def test_anti_tamper_should_block_no_manifest():
    from app.security import anti_tamper_should_block
    # No manifest → should not block
    assert anti_tamper_should_block() is False