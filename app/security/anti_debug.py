"""
Anti-debug checks (Phase 22).

Best-effort detection. **Never crashes** — returns a status dict
so the caller can decide. Default policy: log-only.

Public API:
    is_debugger_present() -> bool
    check() -> {"debugger": bool, "reason": str, ...}
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict


def _windows_is_debugger_present() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        return bool(kernel32.IsDebuggerPresent())
    except Exception:  # noqa: BLE001
        return False


def _windows_check_remote_debugger() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        present = ctypes.c_int(0)
        kernel32.CheckRemoteDebuggerPresent(
            kernel32.GetCurrentProcess(), ctypes.byref(present)
        )
        return bool(present.value)
    except Exception:  # noqa: BLE001
        return False


def _python_debugger_attached() -> bool:
    """Detect common Python debuggers (pdb, pydevd, debugpy)."""
    for name in ("pydevd", "debugpy", "ptvsd"):
        if name in sys.modules:
            return True
    # sys.gettrace is set when running under pdb
    try:
        if sys.gettrace() is not None:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def is_debugger_present() -> bool:
    """Return True if any debugger is detected."""
    return (
        _windows_is_debugger_present()
        or _windows_check_remote_debugger()
        or _python_debugger_attached()
    )


def check() -> Dict[str, Any]:
    """Return a detailed anti-debug status dict."""
    return {
        "debugger": is_debugger_present(),
        "windows_local": _windows_is_debugger_present(),
        "windows_remote": _windows_check_remote_debugger(),
        "python_tracer": _python_debugger_attached(),
    }