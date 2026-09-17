"""
Path Guard (Phase 19).

Restricts all file operations to a set of allowed roots:

    - C:\\Users\\<USER>\\Desktop
    - C:\\Users\\<USER>\\Documents
    - C:\\Users\\<USER>\\Downloads
    - I:\\EVA\\data\\workspace (EVA workspace)

Blocks access to dangerous system directories:
    - C:\\Windows
    - C:\\Program Files
    - C:\\Program Files (x86)
    - C:\\System32

Usage:
    resolved = PathGuard.resolve("C:/Users/Rizvi/Desktop/note.txt")
    # or raises PathViolation
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class PathViolation(Exception):
    """Raised when a path is outside all allowed roots or in a blocked root."""


# ---------------------------------------------------------------------- #
# Defaults
# ---------------------------------------------------------------------- #
def _user_home() -> Path:
    try:
        return Path.home()
    except Exception:  # noqa: BLE001
        return Path(os.environ.get("USERPROFILE", "C:\\Users\\User"))


def _default_allowed_roots() -> List[Path]:
    home = _user_home()
    workspace = ConfigManager.get_data_dir() / "workspace"
    return [
        (home / "Desktop").resolve(strict=False),
        (home / "Documents").resolve(strict=False),
        (home / "Downloads").resolve(strict=False),
        workspace.resolve(strict=False),
    ]


def _default_blocked_roots() -> List[Path]:
    roots = []
    for raw in (
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
    ):
        try:
            roots.append(Path(raw).resolve(strict=False))
        except Exception:  # noqa: BLE001
            continue
    return roots


# ---------------------------------------------------------------------- #
# PathGuard
# ---------------------------------------------------------------------- #
class PathGuard:
    _allowed: Optional[List[Path]] = None
    _blocked: Optional[List[Path]] = None

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def _load_config(cls) -> Tuple[List[Path], List[Path]]:
        """Load allowed/blocked roots from config, fall back to defaults."""
        cfg_allowed = ConfigManager.get("security.paths.allowed_roots", None)
        cfg_blocked = ConfigManager.get("security.paths.blocked_roots", None)

        allowed: List[Path] = []
        if isinstance(cfg_allowed, list) and cfg_allowed:
            for raw in cfg_allowed:
                try:
                    allowed.append(Path(str(raw)).expanduser().resolve(strict=False))
                except Exception:  # noqa: BLE001
                    continue
        else:
            allowed = _default_allowed_roots()

        blocked: List[Path] = []
        if isinstance(cfg_blocked, list) and cfg_blocked:
            for raw in cfg_blocked:
                try:
                    blocked.append(Path(str(raw)).resolve(strict=False))
                except Exception:  # noqa: BLE001
                    continue
        else:
            blocked = _default_blocked_roots()

        return allowed, blocked

    @classmethod
    def reload(cls) -> None:
        """Force reload (used by tests)."""
        cls._allowed = None
        cls._blocked = None

    @classmethod
    def allowed_roots(cls) -> List[Path]:
        if cls._allowed is None:
            cls._allowed, cls._blocked = cls._load_config()
        return list(cls._allowed or [])

    @classmethod
    def blocked_roots(cls) -> List[Path]:
        if cls._blocked is None:
            cls._allowed, cls._blocked = cls._load_config()
        return list(cls._blocked or [])

    # ------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------ #
    @classmethod
    def _is_under(cls, child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False

    @classmethod
    def is_allowed(cls, path) -> bool:
        """Return True if path is inside any allowed root and not blocked."""
        if path is None:
            return False
        try:
            resolved = Path(str(path)).expanduser().resolve(strict=False)
        except Exception:  # noqa: BLE001
            return False

        # Blocked check first
        for blocked in cls.blocked_roots():
            if cls._is_under(resolved, blocked):
                return False

        for allowed in cls.allowed_roots():
            if resolved == allowed or cls._is_under(resolved, allowed):
                return True

        return False

    @classmethod
    def resolve(cls, path) -> Path:
        """
        Resolve a path and verify it is inside an allowed root.

        Raises PathViolation if not.
        """
        if path is None:
            raise PathViolation("Path is None")

        try:
            resolved = Path(str(path)).expanduser().resolve(strict=False)
        except Exception as exc:  # noqa: BLE001
            raise PathViolation(f"Cannot resolve path: {exc}") from exc

        for blocked in cls.blocked_roots():
            if cls._is_under(resolved, blocked):
                logger.warning(
                    "path_blocked", path=str(resolved), blocked_root=str(blocked),
                )
                raise PathViolation(
                    f"Path '{resolved}' is inside blocked root '{blocked}'."
                )

        for allowed in cls.allowed_roots():
            if resolved == allowed or cls._is_under(resolved, allowed):
                return resolved

        logger.warning(
            "path_not_allowed",
            path=str(resolved),
            allowed=[str(p) for p in cls.allowed_roots()],
        )
        raise PathViolation(
            f"Path '{resolved}' is outside all allowed roots "
            f"({', '.join(str(p) for p in cls.allowed_roots())})."
        )

    # ------------------------------------------------------------------ #
    # Description
    # ------------------------------------------------------------------ #
    @classmethod
    def describe(cls) -> dict:
        return {
            "allowed_roots": [str(p) for p in cls.allowed_roots()],
            "blocked_roots": [str(p) for p in cls.blocked_roots()],
        }