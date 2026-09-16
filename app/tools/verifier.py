"""
Post-action verification helpers (Integrations Layer).

Verification strategies:
    - File exists / has size / has mtime changed
    - Process is running (by name)
    - HTTP endpoint returns expected status
    - Window title contains a substring
    - Output file is a valid media file (via ffprobe if available)

Every function returns a simple dict so tools can embed the result
directly into their ToolResult.data.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import httpx

from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Files
# ---------------------------------------------------------------------- #
def file_exists(path: str, min_size_bytes: int = 0) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"verified": False, "reason": "file not found", "path": str(p)}
    try:
        size = p.stat().st_size
    except OSError as exc:
        return {"verified": False, "reason": f"stat failed: {exc}", "path": str(p)}
    if size < min_size_bytes:
        return {
            "verified": False,
            "reason": f"size {size} < min {min_size_bytes}",
            "path": str(p),
            "size": size,
        }
    return {"verified": True, "path": str(p), "size": size}


def file_changed(path: str, since_epoch: float) -> Dict[str, Any]:
    """Check that a file's mtime is newer than `since_epoch`."""
    p = Path(path)
    if not p.exists():
        return {"verified": False, "reason": "file not found", "path": str(p)}
    try:
        mtime = p.stat().st_mtime
    except OSError as exc:
        return {"verified": False, "reason": f"stat failed: {exc}"}
    return {
        "verified": mtime >= since_epoch,
        "path": str(p),
        "mtime": mtime,
        "since": since_epoch,
    }


# ---------------------------------------------------------------------- #
# Processes
# ---------------------------------------------------------------------- #
def process_running(process_name: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Best-effort check via tasklist on Windows, pgrep on POSIX."""
    name = process_name.strip()
    if not name:
        return {"verified": False, "reason": "empty process name"}

    try:
        if os.name == "nt":
            exe = name if name.lower().endswith(".exe") else f"{name}.exe"
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            out = (result.stdout or "").lower()
            running = exe.lower() in out and "no tasks" not in out
        else:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=timeout,
            )
            running = result.returncode == 0
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "reason": f"check failed: {exc}"}

    return {"verified": running, "process": name}


def wait_for_process(process_name: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Poll until the process is running or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = process_running(process_name)
        if r.get("verified"):
            return r
        time.sleep(0.5)
    return {"verified": False, "process": process_name, "reason": "timeout"}


# ---------------------------------------------------------------------- #
# HTTP
# ---------------------------------------------------------------------- #
async def http_ok(
    url: str,
    expected_status: int = 200,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "reason": f"http error: {exc}", "url": url}
    return {
        "verified": r.status_code == expected_status,
        "url": url,
        "status": r.status_code,
        "expected": expected_status,
    }


def http_ok_sync(url: str, expected_status: int = 200, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        r = httpx.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "reason": f"http error: {exc}", "url": url}
    return {"verified": r.status_code == expected_status, "url": url, "status": r.status_code}


# ---------------------------------------------------------------------- #
# Windows: active window title
# ---------------------------------------------------------------------- #
def active_window_title_contains(substring: str) -> Dict[str, Any]:
    if os.name != "nt":
        return {"verified": False, "reason": "windows only"}
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "reason": f"win32gui error: {exc}"}

    ok = substring.lower() in title.lower()
    return {"verified": ok, "title": title, "looking_for": substring}


# ---------------------------------------------------------------------- #
# Media (via ffprobe if available)
# ---------------------------------------------------------------------- #
def media_file_valid(path: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Return {verified, duration, format} for an audio/video file."""
    p = Path(path)
    if not p.exists():
        return {"verified": False, "reason": "file not found"}

    ffprobe = None
    from shutil import which
    for candidate in ("ffprobe", "ffprobe.exe"):
        found = which(candidate)
        if found:
            ffprobe = found
            break
    if not ffprobe:
        return {"verified": False, "reason": "ffprobe not installed"}

    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration,format_name", "-of", "default=noprint_wrappers=1",
             str(p)],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "reason": f"ffprobe failed: {exc}"}

    if result.returncode != 0:
        return {
            "verified": False,
            "reason": "ffprobe rejected file",
            "stderr": (result.stderr or "")[:300],
        }

    parsed: Dict[str, str] = {}
    for line in (result.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip()

    try:
        duration = float(parsed.get("duration", "0"))
    except ValueError:
        duration = 0.0

    return {
        "verified": duration > 0,
        "duration": duration,
        "format": parsed.get("format_name", ""),
        "path": str(p),
    }