"""
Tests for app.tools.permissions.PermissionManager.
"""
from __future__ import annotations

import pytest

from app.tools.base import RiskLevel
from app.tools.permissions import PermissionManager, PermissionDecision


@pytest.fixture(autouse=True)
def reset_permissions():
    PermissionManager.reset_confirmer()
    PermissionManager.clear_overrides()
    yield
    PermissionManager.reset_confirmer()
    PermissionManager.clear_overrides()


@pytest.mark.asyncio
async def test_low_risk_auto_allowed():
    decision = await PermissionManager.check("some_tool", RiskLevel.LOW)
    assert decision.allowed is True
    assert decision.confirmed is False


@pytest.mark.asyncio
async def test_medium_risk_allowed_with_logging():
    decision = await PermissionManager.check("some_tool", RiskLevel.MEDIUM)
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_high_risk_requires_confirmation_denied():
    async def deny(title, message, risk):
        return False

    PermissionManager.set_confirmer(deny)
    decision = await PermissionManager.check("dangerous_tool", RiskLevel.HIGH)
    assert decision.allowed is False
    assert "denied" in decision.reason.lower()


@pytest.mark.asyncio
async def test_high_risk_confirmed():
    async def approve(title, message, risk):
        return True

    PermissionManager.set_confirmer(approve)
    decision = await PermissionManager.check("dangerous_tool", RiskLevel.HIGH)
    assert decision.allowed is True
    assert decision.confirmed is True


@pytest.mark.asyncio
async def test_critical_risk_requires_confirmation():
    async def deny(title, message, risk):
        # CRITICAL should pass extra message
        assert "CRITICAL" in message or "critical" in message.lower()
        return False

    PermissionManager.set_confirmer(deny)
    decision = await PermissionManager.check("format_disk", RiskLevel.CRITICAL)
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_confirmer_exception_denies_safely():
    async def broken(title, message, risk):
        raise RuntimeError("confirmer broke")

    PermissionManager.set_confirmer(broken)
    decision = await PermissionManager.check("dangerous_tool", RiskLevel.HIGH)
    assert decision.allowed is False
    assert "confirmer error" in decision.reason.lower()


@pytest.mark.asyncio
async def test_tool_override_to_low():
    PermissionManager.set_tool_override("dangerous_tool", RiskLevel.LOW)
    decision = await PermissionManager.check("dangerous_tool", RiskLevel.CRITICAL)
    assert decision.allowed is True


def test_check_sync_low_and_medium():
    d1 = PermissionManager.check_sync("tool", RiskLevel.LOW)
    d2 = PermissionManager.check_sync("tool", RiskLevel.MEDIUM)
    assert d1.allowed and d2.allowed


def test_check_sync_high_rejected():
    d = PermissionManager.check_sync("tool", RiskLevel.HIGH)
    assert d.allowed is False


def test_permission_decision_defaults():
    d = PermissionDecision(allowed=True)
    assert d.reason == ""
    assert d.confirmed is False