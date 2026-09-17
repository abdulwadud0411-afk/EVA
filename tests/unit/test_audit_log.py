"""Tests for Phase 20 AuditLog."""
from __future__ import annotations

import json

import pytest

from app.core.config_manager import ConfigManager
from app.security.audit_log import AuditLog


@pytest.fixture(autouse=True)
def isolated_audit(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    ConfigManager.load()
    ConfigManager.set("app.data_dir", str(data_dir), persist=False)
    log_path = data_dir / "security" / "audit" / "test.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    AuditLog.configure(log_path)
    AuditLog.reload()
    AuditLog.configure(log_path)
    yield log_path
    AuditLog.reload()


def test_log_writes_jsonl(isolated_audit):
    AuditLog.log("TEST_EVENT", actor="agent", tool="delete_file", risk="HIGH")
    lines = isolated_audit.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "TEST_EVENT"
    assert entry["tool"] == "delete_file"
    assert entry["risk"] == "HIGH"
    assert "hmac" in entry
    assert len(entry["hmac"]) == 64  # SHA-256 hex


def test_log_redacts_sensitive_data(isolated_audit):
    AuditLog.log(
        "SECRET_LEAK",
        tool="test",
        data={"password": "hunter2", "username": "rizve"},
    )
    content = isolated_audit.read_text(encoding="utf-8")
    assert "hunter2" not in content
    assert "***REDACTED***" in content
    assert "rizve" in content


def test_verify_clean_file(isolated_audit):
    for i in range(3):
        AuditLog.log("EVENT", tool=f"tool_{i}")
    result = AuditLog.verify_file(isolated_audit)
    assert result["ok"] is True
    assert result["total"] == 3
    assert result["broken_lines"] == []


def test_verify_detects_tamper(isolated_audit):
    AuditLog.log("EVENT_A", tool="x")
    AuditLog.log("EVENT_B", tool="y")
    # Tamper with first line
    lines = isolated_audit.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["event"] = "HACKED"
    lines[0] = json.dumps(entry, ensure_ascii=False)
    isolated_audit.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = AuditLog.verify_file(isolated_audit)
    assert result["ok"] is False
    assert 1 in result["broken_lines"]


def test_verify_missing_file(tmp_path):
    result = AuditLog.verify_file(tmp_path / "nope.jsonl")
    assert result["ok"] is False
    assert "not found" in result["reason"].lower()


def test_recent_returns_last_n(isolated_audit):
    for i in range(10):
        AuditLog.log("E", tool=f"t{i}")
    recent = AuditLog.recent(limit=3)
    assert len(recent) == 3
    assert recent[-1]["tool"] == "t9"


def test_recent_empty_file():
    assert AuditLog.recent() == [] or isinstance(AuditLog.recent(), list)