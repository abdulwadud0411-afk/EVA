"""
System info tools (Phase 19).

Tools:
    - get_system_info
    - get_disk_usage
    - list_top_processes
    - get_battery_status
    - get_network_info
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)


try:
    import psutil  # type: ignore
    _PSUTIL = True
except Exception:  # noqa: BLE001
    psutil = None  # type: ignore
    _PSUTIL = False


# ---------------------------------------------------------------------- #
# Tool: get_system_info
# ---------------------------------------------------------------------- #
class GetSystemInfoTool(Tool):
    name = "get_system_info"
    description = "Return basic system information (OS, CPU, RAM, host)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        info = {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cpu_model": platform.processor(),
        }

        if _PSUTIL:
            try:
                vm = psutil.virtual_memory()
                info["ram_total_mb"] = round(vm.total / (1024 * 1024), 1)
                info["ram_used_mb"] = round((vm.total - vm.available) / (1024 * 1024), 1)
                info["ram_percent"] = vm.percent
            except Exception:  # noqa: BLE001
                pass

        return ToolResult(success=True, tool=self.name, data=info)


# ---------------------------------------------------------------------- #
# Tool: get_disk_usage
# ---------------------------------------------------------------------- #
class GetDiskUsageTool(Tool):
    name = "get_disk_usage"
    description = "Report disk usage for all mounted drives."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        drives: List[dict] = []

        if _PSUTIL:
            try:
                for part in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                    except Exception:  # noqa: BLE001
                        continue
                    drives.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "percent": usage.percent,
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("disk_usage_failed", error=str(exc))

        if not drives:
            try:
                total, used, free = shutil.disk_usage(os.getcwd())
                drives.append({
                    "device": os.path.splitdrive(os.getcwd())[0] or "/",
                    "mountpoint": os.getcwd(),
                    "fstype": "",
                    "total_gb": round(total / (1024 ** 3), 2),
                    "used_gb": round(used / (1024 ** 3), 2),
                    "free_gb": round(free / (1024 ** 3), 2),
                    "percent": round(used * 100.0 / total, 1),
                })
            except Exception:  # noqa: BLE001
                pass

        return ToolResult(success=True, tool=self.name, data={
            "count": len(drives),
            "drives": drives,
        })


# ---------------------------------------------------------------------- #
# Tool: list_top_processes
# ---------------------------------------------------------------------- #
class ListTopProcessesTool(Tool):
    name = "list_top_processes"
    description = "List processes sorted by CPU or memory usage."
    parameters = {
        "type": "object",
        "properties": {
            "sort_by": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        if not _PSUTIL:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PSUTIL_MISSING",
                "message": "psutil is required. Run: pip install psutil",
            })

        sort_by = str(kwargs.get("sort_by", "cpu")).lower()
        if sort_by not in ("cpu", "memory"):
            sort_by = "cpu"
        try:
            limit = int(kwargs.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        if limit <= 0 or limit > 200:
            limit = 20

        try:
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    procs.append({
                        "pid": info.get("pid"),
                        "name": info.get("name") or "?",
                        "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                        "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                    })
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, tool=self.name, error={
                "code": "PROCESS_LIST_FAILED", "message": str(exc),
            })

        key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
        procs.sort(key=lambda p: p[key], reverse=True)

        return ToolResult(success=True, tool=self.name, data={
            "sort_by": sort_by,
            "count": min(len(procs), limit),
            "processes": procs[:limit],
        })


# ---------------------------------------------------------------------- #
# Tool: get_battery_status
# ---------------------------------------------------------------------- #
class GetBatteryStatusTool(Tool):
    name = "get_battery_status"
    description = "Return battery percentage and charging status (if present)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        if not _PSUTIL:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PSUTIL_MISSING", "message": "psutil is required.",
            })

        try:
            bat = psutil.sensors_battery()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, tool=self.name, error={
                "code": "BATTERY_READ_FAILED", "message": str(exc),
            })

        if bat is None:
            return ToolResult(success=True, tool=self.name, data={
                "present": False,
                "message": "No battery detected (desktop PC).",
            })

        secs = bat.secsleft
        remaining_min = None
        if isinstance(secs, (int, float)) and secs > 0:
            remaining_min = int(secs // 60)

        return ToolResult(success=True, tool=self.name, data={
            "present": True,
            "percent": bat.percent,
            "plugged_in": bool(bat.power_plugged),
            "remaining_minutes": remaining_min,
        })


# ---------------------------------------------------------------------- #
# Tool: get_network_info
# ---------------------------------------------------------------------- #
class GetNetworkInfoTool(Tool):
    name = "get_network_info"
    description = "Return hostname, local IPs, and network interfaces."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        info: dict = {
            "hostname": socket.gethostname(),
            "interfaces": [],
        }

        try:
            info["local_ip"] = socket.gethostbyname(socket.gethostname())
        except Exception:  # noqa: BLE001
            info["local_ip"] = None

        if _PSUTIL:
            try:
                addrs = psutil.net_if_addrs()
                for name, addr_list in addrs.items():
                    iface = {"name": name, "addresses": []}
                    for a in addr_list:
                        iface["addresses"].append({
                            "family": str(a.family),
                            "address": a.address,
                            "netmask": a.netmask,
                        })
                    info["interfaces"].append(iface)
            except Exception as exc:  # noqa: BLE001
                logger.warning("net_info_failed", error=str(exc))

        return ToolResult(success=True, tool=self.name, data=info)