"""
Install-dir-aware paths (Phase 22).

Works in BOTH dev mode (running from source) and frozen mode
(PyInstaller .exe). All other modules should use these helpers
instead of `ConfigManager.get_project_root()` directly.

Public API:
    get_app_root()      # where config/ prompts/ assets/ live
    get_data_dir()      # user-writable (AppData when frozen)
    get_config_dir()
    get_prompts_dir()
    get_assets_dir()
    get_models_dir()
    is_frozen()         # True when running as PyInstaller .exe
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """Return True if running as a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    """
    Root of the EVA installation.

    Dev mode   : project root (e.g. I:\\EVA)
    Frozen mode: PyInstaller 6.x one-folder mode puts bundled datas
                 (config/, prompts/, assets/) inside `_internal/`,
                 not next to the .exe. We detect that layout.
    """
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        # PyInstaller 6.x one-folder: datas live in _internal/
        internal = exe_dir / "_internal"
        if internal.is_dir() and (internal / "config").is_dir():
            return internal
        # PyInstaller 5.x: datas next to the exe
        return exe_dir
    return Path(__file__).resolve().parent.parent.parent


def _user_data_root() -> Path:
    """Per-user writable root (AppData on Windows)."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "EVA"
    # Fallback
    return Path.home() / ".eva"


def get_data_dir() -> Path:
    """
    Writable data directory.

    Dev mode  : <root>/data
    Frozen mode: %LOCALAPPDATA%/EVA/data  (per-user, always writable)
    """
    if is_frozen():
        d = _user_data_root() / "data"
    else:
        d = get_app_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_dir() -> Path:
    """
    Config directory (works for both dev + frozen layouts).
    """
    return get_app_root() / "config"


def get_prompts_dir() -> Path:
    return get_app_root() / "prompts"


def get_assets_dir() -> Path:
    return get_app_root() / "assets"


def get_models_dir() -> Path:
    """
    Models directory.

    Dev mode  : <root>/models
    Frozen mode: %LOCALAPPDATA%/EVA/models  (big files, user-writable)
    """
    if is_frozen():
        d = _user_data_root() / "models"
    else:
        d = get_app_root() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_certs_dir() -> Path:
    return get_app_root() / "certs"


def get_logs_dir() -> Path:
    d = get_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_env_file() -> Optional[Path]:
    """
    Search for a `.env` file in priority order.

    Frozen mode:
        1. Next to EVA.exe            (user-editable, recommended)
        2. _internal/.env             (bundled default)
        3. %LOCALAPPDATA%/EVA/.env    (per-user fallback)
    Dev mode:
        1. Project root .env
    """
    candidates: list[Path] = []

    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / ".env")
        candidates.append(exe_dir / "_internal" / ".env")
        candidates.append(_user_data_root() / ".env")
    else:
        candidates.append(get_app_root() / ".env")

    for p in candidates:
        if p.exists():
            return p
    return None


def get_user_env_path() -> Path:
    """Return the path where the user should write their .env."""
    if is_frozen():
        return Path(sys.executable).resolve().parent / ".env"
    return get_app_root() / ".env"


def describe() -> dict:
    """Return a summary dict for diagnostics."""
    info = {
        "frozen": is_frozen(),
        "executable": str(sys.executable) if is_frozen() else "(dev)",
        "app_root": str(get_app_root()),
        "data_dir": str(get_data_dir()),
        "config_dir": str(get_config_dir()),
        "models_dir": str(get_models_dir()),
        "prompts_dir": str(get_prompts_dir()),
        "assets_dir": str(get_assets_dir()),
        "env_file": str(find_env_file()) if find_env_file() else "(not found)",
    }
    info["config_file_exists"] = (get_config_dir() / "config.yaml").exists()
    return info