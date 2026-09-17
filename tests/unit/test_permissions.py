"""Tests for Phase 20 PermissionManager."""
from __future__ import annotations

import pytest
import yaml

from app.security.permissions import PermissionManager, PermissionDecision


@pytest.fixture(autouse=True)
def isolated_permissions(tmp_path):
    perm_file = tmp_path / "permissions.yaml"
    perm_file.write_text(
        yaml.safe_dump({
            "permissions": {
                "require_confirmation_master": False,
                "scope": {
                    "file_read": "allow",
                    "file_write": "confirm",
                    "file_delete": "confirm",
                    "app_control": "allow",
                    "terminal": "confirm",
                    "network": "allow",
                },
                "tool_overrides": {
                    "delete_file": {"scope": "confirm", "reason": "destructive"},
                    "write_file": {"scope": "allow"},
                },
                "risk_defaults": {
                    "LOW": "allow",
                    "MEDIUM": "allow",
                    "HIGH": "confirm",
                    "CRITICAL": "confirm",
                },
            }
        }),
        encoding="utf-8",
    )
    PermissionManager.configure(perm_file)
    yield
    PermissionManager.reload()


def test_allow_by_tool_override():
    d = PermissionManager.check("write_file", risk="MEDIUM")
    assert d.allow is True
    assert d.matched_rule == "tool_override"


def test_confirm_by_tool_override():
    d = PermissionManager.check("delete_file", risk="MEDIUM")
    assert d.allow is False
    assert d.requires_confirmation is True
    assert d.matched_rule == "tool_override"


def test_allow_by_category():
    d = PermissionManager.check("open_application", risk="LOW")
    assert d.allow is True
    assert d.matched_rule == "scope"


def test_confirm_by_category():
    d = PermissionManager.check("run_terminal_command", risk="HIGH")
    assert d.allow is False
    assert d.requires_confirmation is True
    assert d.matched_rule == "scope"


def test_risk_default_high_confirm():
    d = PermissionManager.check("unknown_tool_xyz", risk="HIGH")
    assert d.allow is False
    assert d.requires_confirmation is True
    assert d.matched_rule == "risk_default"


def test_risk_default_low_allow():
    d = PermissionManager.check("unknown_tool_xyz", risk="LOW")
    assert d.allow is True
    assert d.matched_rule == "risk_default"


def test_master_switch_forces_confirm(tmp_path):
    perm_file = tmp_path / "permissions.yaml"
    perm_file.write_text(
        yaml.safe_dump({
            "permissions": {
                "require_confirmation_master": True,
                "scope": {"file_read": "allow"},
            }
        }),
        encoding="utf-8",
    )
    PermissionManager.configure(perm_file)
    PermissionManager.reload()
    d = PermissionManager.check("read_file", risk="LOW")
    assert d.allow is False
    assert d.requires_confirmation is True
    assert d.matched_rule == "master"


def test_unknown_scope_defaults_to_confirm(tmp_path):
    perm_file = tmp_path / "permissions.yaml"
    perm_file.write_text(
        yaml.safe_dump({
            "permissions": {
                "tool_overrides": {"weird_tool": {"scope": "bogus_value"}},
            }
        }),
        encoding="utf-8",
    )
    PermissionManager.configure(perm_file)
    PermissionManager.reload()
    d = PermissionManager.check("weird_tool", risk="LOW")
    assert d.allow is False
    assert d.requires_confirmation is True


def test_decision_to_dict():
    d = PermissionDecision(allow=True, scope="allow", matched_rule="scope")
    as_dict = d.to_dict()
    assert as_dict["allow"] is True
    assert as_dict["matched_rule"] == "scope"


def test_describe_shape():
    info = PermissionManager.describe()
    assert "master_switch" in info
    assert "scopes" in info
    assert "tool_overrides" in info


def test_missing_permissions_file_defaults(tmp_path):
    PermissionManager.configure(tmp_path / "does_not_exist.yaml")
    PermissionManager.reload()
    d = PermissionManager.check("read_file", risk="LOW")
    assert isinstance(d, PermissionDecision)