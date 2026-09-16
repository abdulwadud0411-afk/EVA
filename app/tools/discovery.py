"""
Application discovery (Integrations Layer).

Locate installed applications on Windows without launching them.

Sources consulted, in order:
    1. Explicit path from config.
    2. Windows registry (App Paths).
    3. Common install directories.
    4. `where` command on PATH.

Returns None when the app is not found.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Well-known Windows install roots
# ---------------------------------------------------------------------- #
_WIN_ROOTS: List[str] = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    os.path.expandvars(r"%APPDATA%"),
    os.path.expandvars(r"%LOCALAPPDATA%"),
]


# ---------------------------------------------------------------------- #
# Registry probe (Windows only)
# ---------------------------------------------------------------------- #
def _lookup_registry(app_exe: str) -> Optional[str]:
    """Look up an executable in the Windows 'App Paths' registry key."""
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_exe}"
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "")
                if value and Path(value).exists():
                    return str(value)
        except FileNotFoundError:
            continue
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------------------------------------------------------------- #
# PATH probe
# ---------------------------------------------------------------------- #
def _lookup_path(exe_name: str) -> Optional[str]:
    found = shutil.which(exe_name)
    if found and Path(found).exists():
        return found
    return None


# ---------------------------------------------------------------------- #
# Filesystem probe
# ---------------------------------------------------------------------- #
def _lookup_filesystem(subpaths: List[str]) -> Optional[str]:
    for root in _WIN_ROOTS:
        for sub in subpaths:
            candidate = Path(root) / sub
            try:
                if candidate.exists():
                    return str(candidate)
            except OSError:
                continue
    return None


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #
def discover_app(
    exe_name: str,
    install_subpaths: Optional[List[str]] = None,
    config_path: Optional[str] = None,
) -> Optional[str]:
    """
    Return the absolute path to an installed executable, or None.

    Args:
        exe_name: The executable name (e.g. "blender.exe").
        install_subpaths: Relative paths under each Windows install root.
        config_path: Explicit path from config (takes priority).
    """
    # 1. Explicit config path
    if config_path and config_path != "auto":
        p = Path(config_path)
        if p.exists():
            return str(p)
        logger.warning("discovery_config_path_missing", path=str(config_path))

    # 2. Registry
    found = _lookup_registry(exe_name)
    if found:
        logger.info("discovery_registry_hit", exe=exe_name, path=found)
        return found

    # 3. PATH
    found = _lookup_path(exe_name)
    if found:
        logger.info("discovery_path_hit", exe=exe_name, path=found)
        return found

    # 4. Filesystem
    if install_subpaths:
        found = _lookup_filesystem(install_subpaths)
        if found:
            logger.info("discovery_fs_hit", exe=exe_name, path=found)
            return found

    logger.info("discovery_miss", exe=exe_name)
    return None


def is_app_installed(exe_name: str, install_subpaths: Optional[List[str]] = None) -> bool:
    return discover_app(exe_name, install_subpaths) is not None


# ---------------------------------------------------------------------- #
# Common install path hints (used by integrations)
# ---------------------------------------------------------------------- #
APP_HINTS: Dict[str, Dict[str, object]] = {
    "blender": {
        "exe": "blender.exe",
        "subpaths": [
            r"Blender Foundation\Blender 4.2\blender.exe",
            r"Blender Foundation\Blender 4.1\blender.exe",
            r"Blender Foundation\Blender 4.0\blender.exe",
            r"Blender Foundation\Blender 3.6\blender.exe",
        ],
    },
    "unreal": {
        "exe": "UnrealEditor.exe",
        "subpaths": [
            r"Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor.exe",
            r"Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe",
            r"Epic Games\UE_5.2\Engine\Binaries\Win64\UnrealEditor.exe",
        ],
    },
    "cinema4d": {
        "exe": "Cinema 4D.exe",
        "subpaths": [
            r"Maxon\Cinema 4D 2024\Cinema 4D.exe",
            r"Maxon\Cinema 4D 2023\Cinema 4D.exe",
        ],
    },
    "photoshop": {
        "exe": "Photoshop.exe",
        "subpaths": [
            r"Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ],
    },
    "illustrator": {
        "exe": "Illustrator.exe",
        "subpaths": [
            r"Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"Adobe\Adobe Illustrator 2023\Support Files\Contents\Windows\Illustrator.exe",
        ],
    },
    "premiere": {
        "exe": "Adobe Premiere Pro.exe",
        "subpaths": [
            r"Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
        ],
    },
    "after_effects": {
        "exe": "AfterFX.exe",
        "subpaths": [
            r"Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
            r"Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        ],
    },
    "capcut": {
        "exe": "CapCut.exe",
        "subpaths": [
            os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe"),
            r"CapCut\CapCut.exe",
        ],
    },
    "word": {
        "exe": "WINWORD.EXE",
        "subpaths": [
            r"Microsoft Office\root\Office16\WINWORD.EXE",
            r"Microsoft Office\Office16\WINWORD.EXE",
        ],
    },
    "excel": {
        "exe": "EXCEL.EXE",
        "subpaths": [
            r"Microsoft Office\root\Office16\EXCEL.EXE",
            r"Microsoft Office\Office16\EXCEL.EXE",
        ],
    },
    "powerpoint": {
        "exe": "POWERPNT.EXE",
        "subpaths": [
            r"Microsoft Office\root\Office16\POWERPNT.EXE",
            r"Microsoft Office\Office16\POWERPNT.EXE",
        ],
    },
    "outlook": {
        "exe": "OUTLOOK.EXE",
        "subpaths": [
            r"Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"Microsoft Office\Office16\OUTLOOK.EXE",
        ],
    },
    "onenote": {
        "exe": "ONENOTE.EXE",
        "subpaths": [
            r"Microsoft Office\root\Office16\ONENOTE.EXE",
            r"Microsoft Office\Office16\ONENOTE.EXE",
        ],
    },
    "ffmpeg": {
        "exe": "ffmpeg.exe",
        "subpaths": [],
    },
    # --- Dev tools ---
    "vscode": {
        "exe": "Code.exe",
        "subpaths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"Microsoft VS Code\Code.exe",
        ],
    },
    "visual_studio": {
        "exe": "devenv.exe",
        "subpaths": [
            r"Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe",
            r"Microsoft Visual Studio\2022\Professional\Common7\IDE\devenv.exe",
            r"Microsoft Visual Studio\2022\Enterprise\Common7\IDE\devenv.exe",
        ],
    },
    "android_studio": {
        "exe": "studio64.exe",
        "subpaths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\AndroidStudio\bin\studio64.exe"),
            r"Android\Android Studio\bin\studio64.exe",
            r"Google\Android Studio\bin\studio64.exe",
        ],
    },
    "unity": {
        "exe": "Unity.exe",
        "subpaths": [
            r"Unity\Hub\Editor\2023.2.0f1\Editor\Unity.exe",
            r"Unity\Hub\Editor\2022.3.10f1\Editor\Unity.exe",
        ],
    },
    "webstorm": {
        "exe": "webstorm64.exe",
        "subpaths": [
            r"JetBrains\WebStorm 2024.1\bin\webstorm64.exe",
            r"JetBrains\WebStorm 2023.3\bin\webstorm64.exe",
        ],
    },
    "flutter": {
        "exe": "flutter.bat",
        "subpaths": [
            r"flutter\bin\flutter.bat",
        ],
    },
    "xampp": {
        "exe": "xampp-control.exe",
        "subpaths": [
            r"XAMPP\xampp-control.exe",
            r"xampp\xampp-control.exe",
        ],
    },
    "wamp": {
        "exe": "wampmanager.exe",
        "subpaths": [
            r"wamp64\wampmanager.exe",
            r"wamp\wampmanager.exe",
        ],
    },
    "python": {
        "exe": "python.exe",
        "subpaths": [],
    },
}


def discover_known_app(key: str, config_path: Optional[str] = None) -> Optional[str]:
    """
    Discover a well-known app by its short key (e.g. 'blender').

    Returns the absolute path to the executable, or None.
    """
    hint = APP_HINTS.get(key.lower())
    if not hint:
        return None
    return discover_app(
        exe_name=str(hint["exe"]),
        install_subpaths=list(hint["subpaths"]),  # type: ignore[arg-type]
        config_path=config_path,
    )