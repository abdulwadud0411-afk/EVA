"""Tests for Phase 19 system tools."""
from __future__ import annotations

import pytest

from app.tools.system_tools import (
    GetSystemInfoTool, GetDiskUsageTool, ListTopProcessesTool,
    GetBatteryStatusTool, GetNetworkInfoTool,
)


@pytest.mark.asyncio
async def test_system_info():
    r = await GetSystemInfoTool().run()
    assert r.success is True
    assert "os" in r.data
    assert "hostname" in r.data
    assert "cpu_count" in r.data


@pytest.mark.asyncio
async def test_disk_usage():
    r = await GetDiskUsageTool().run()
    assert r.success is True
    assert "drives" in r.data


@pytest.mark.asyncio
async def test_top_processes_sort_cpu():
    r = await ListTopProcessesTool().run(sort_by="cpu", limit=5)
    if r.success:
        assert len(r.data["processes"]) <= 5
        assert r.data["sort_by"] == "cpu"


@pytest.mark.asyncio
async def test_top_processes_sort_memory():
    r = await ListTopProcessesTool().run(sort_by="memory", limit=3)
    if r.success:
        assert r.data["sort_by"] == "memory"


@pytest.mark.asyncio
async def test_top_processes_invalid_sort():
    r = await ListTopProcessesTool().run(sort_by="invalid", limit=2)
    if r.success:
        assert r.data["sort_by"] == "cpu"


@pytest.mark.asyncio
async def test_battery_status():
    r = await GetBatteryStatusTool().run()
    if r.success:
        assert "present" in r.data


@pytest.mark.asyncio
async def test_network_info():
    r = await GetNetworkInfoTool().run()
    assert r.success is True
    assert "hostname" in r.data
    assert "interfaces" in r.data