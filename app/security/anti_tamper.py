"""
Anti-tamper checks (Phase 22).

Higher-level wrapper that:
    1. Checks if the running executable matches the last known hash
    2. Checks if critical files were modified
    3. Reports (does NOT crash by default)

Public API:
    check_all() -> dict
    should_block() -> bool
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.logger import get_logger
from app.core.paths import get_app_root, get_data_dir, is_frozen
from app.security.integrity_check import verify_saved

logger = get_logger(__name__)


def _hash_exe() -> Optional[str]:
    """Hash the running executable when frozen."""
    if not is_frozen():
        return None
    try:
        path = Path(sys.executable)
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:  # noqa: BLE001
        logger.warning("anti_tamper_exe_hash_failed", error=str(exc))
        return None


def _stored_exe_hash_path() -> Path:
    return get_data_dir() / "security" / "exe.hash"


def _load_stored_exe_hash() -> Optional[str]:
    p = _stored_exe_hash_path()
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _save_exe_hash(h: str) -> None:
    p = _stored_exe_hash_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(h, encoding="utf-8")
    except OSError as exc:
        logger.warning("anti_tamper_save_exe_hash_failed", error=str(exc))


# ---------------------------------------------------------------------- #
# Public
# ---------------------------------------------------------------------- #
def check_all() -> Dict[str, Any]:
    """
    Run all tamper checks. Never raises.

    Returns:
        {
          "exe_hash_match": bool|None,
          "files_intact": bool,
          "modified_files": [..],
          "missing_files": [..],
        }
    """
    result: Dict[str, Any] = {
        "exe_hash_match": None,
        "files_intact": True,
        "modified_files": [],
        "missing_files": [],
    }

    # 1. Executable hash (only when frozen)
    if is_frozen():
        current = _hash_exe()
        stored = _load_stored_exe_hash()
        if stored is None:
            # First run — record current hash
            if current:
                _save_exe_hash(current)
            result["exe_hash_match"] = True
        else:
            result["exe_hash_match"] = (current == stored)

    # 2. File integrity
    try:
        integ = verify_saved(get_data_dir())
        result["files_intact"] = bool(integ.get("ok", True))
        result["modified_files"] = list(integ.get("modified", []))
        result["missing_files"] = list(integ.get("missing", []))
    except Exception as exc:  # noqa: BLE001
        logger.warning("anti_tamper_integrity_failed", error=str(exc))

    return result


def should_block() -> bool:
    """Return True if tamper detection is severe enough to block startup."""
    r = check_all()
    if r.get("exe_hash_match") is False:
        return True
    return False