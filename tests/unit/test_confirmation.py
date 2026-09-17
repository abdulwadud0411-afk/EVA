"""Tests for Phase 20 ConfirmationGate."""
from __future__ import annotations

import pytest

from app.security.confirmation import ConfirmationGate, ConfirmationRequest


@pytest.fixture(autouse=True)
def reset_gate():
    ConfirmationGate.reset_confirmer()
    ConfirmationGate.set_auto_approve(False)
    yield
    ConfirmationGate.reset_confirmer()
    ConfirmationGate.set_auto_approve(False)


@pytest.mark.asyncio
async def test_custom_confirmer_approves():
    async def approve(req):
        return True
    ConfirmationGate.set_confirmer(approve)
    assert await ConfirmationGate.request("delete_file", {"path": "x"}, risk="HIGH")


@pytest.mark.asyncio
async def test_custom_confirmer_denies():
    async def deny(req):
        return False
    ConfirmationGate.set_confirmer(deny)
    assert await ConfirmationGate.request("delete_file", risk="HIGH") is False


@pytest.mark.asyncio
async def test_auto_approve_skips_prompt():
    ConfirmationGate.set_auto_approve(True)
    assert await ConfirmationGate.request("delete_file", risk="CRITICAL") is True


@pytest.mark.asyncio
async def test_confirmer_exception_denies_safely():
    async def boom(req):
        raise RuntimeError("confirmer broke")
    ConfirmationGate.set_confirmer(boom)
    assert await ConfirmationGate.request("delete_file", risk="HIGH") is False


@pytest.mark.asyncio
async def test_request_passes_arguments():
    seen = {}
    async def capture(req):
        seen["tool"] = req.tool_name
        seen["args"] = req.arguments
        seen["risk"] = req.risk
        return True
    ConfirmationGate.set_confirmer(capture)
    await ConfirmationGate.request(
        "write_file",
        arguments={"path": "/tmp/x", "content": "hi"},
        risk="MEDIUM",
    )
    assert seen["tool"] == "write_file"
    assert seen["args"]["path"] == "/tmp/x"
    assert seen["risk"] == "MEDIUM"


def test_confirmation_request_to_dict():
    req = ConfirmationRequest(
        tool_name="test", arguments={"a": 1}, risk="HIGH", reason="r",
    )
    d = req.to_dict()
    assert d["tool_name"] == "test"
    assert d["arguments"] == {"a": 1}
    assert d["risk"] == "HIGH"


def test_sync_wrapper_auto_approve():
    ConfirmationGate.set_auto_approve(True)
    assert ConfirmationGate.request_sync("x") is True