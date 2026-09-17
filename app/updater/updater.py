"""
Updater (Phase 22 Batch 3).

Ties manifest + downloader together. Two public flows:

    check_for_updates() -> UpdateResult         # read-only check
    run_update(manifest, on_progress) -> UpdateResult
                                                # download installer
                                                # (does NOT install silently)

Installation is intentionally a hand-off: we save the installer and
return its path so the GUI can show a "Run installer" button. This
respects the user's control over what runs on their PC.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.updater.downloader import DownloadError, UpdateDownloader
from app.updater.manifest import (
    ManifestError,
    UpdateManifest,
    fetch_manifest,
    is_newer,
    load_local_manifest,
    save_local_manifest,
)

logger = get_logger(__name__)


class UpdateStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class UpdateResult:
    status: UpdateStatus
    message: str = ""
    current_version: str = ""
    latest_version: str = ""
    manifest: Optional[UpdateManifest] = None
    installer_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "installer_path": self.installer_path,
            "error": self.error,
        }


def get_current_version() -> str:
    """Read EVA's current version from app package."""
    try:
        import app as app_pkg
        return getattr(app_pkg, "__version__", "0.0.0")
    except Exception:  # noqa: BLE001
        return "0.0.0"


# ---------------------------------------------------------------------- #
# Check
# ---------------------------------------------------------------------- #
def check_for_updates(
    manifest_url: Optional[str] = None,
    transport=None,
) -> UpdateResult:
    """
    Check for available updates. Read-only.

    URL resolution order:
        1. explicit argument
        2. config: updater.manifest_url
        3. offline (returns UP_TO_DATE)
    """
    if not bool(ConfigManager.get("updater.enabled", True)):
        return UpdateResult(
            status=UpdateStatus.DISABLED,
            message="Updater disabled in config.",
            current_version=get_current_version(),
        )

    url = manifest_url or str(ConfigManager.get("updater.manifest_url", "") or "")
    current = get_current_version()

    if not url:
        # No URL configured — treat as up-to-date (offline mode)
        local = load_local_manifest()
        return UpdateResult(
            status=UpdateStatus.UP_TO_DATE,
            message="No update URL configured (offline).",
            current_version=current,
            latest_version=local.version if local else current,
        )

    try:
        manifest = fetch_manifest(url, transport=transport)
    except ManifestError as exc:
        logger.warning("update_check_failed", error=str(exc))
        return UpdateResult(
            status=UpdateStatus.FAILED,
            message=str(exc),
            current_version=current,
            error=str(exc),
        )

    save_local_manifest(manifest)

    if not manifest.is_compatible_with(current):
        return UpdateResult(
            status=UpdateStatus.FAILED,
            message=(
                f"Your version ({current}) is too old for a direct upgrade "
                f"(requires at least {manifest.min_supported_version}). "
                f"Please install a fresh copy from the website."
            ),
            current_version=current,
            latest_version=manifest.version,
            manifest=manifest,
        )

    if is_newer(current, manifest.version):
        return UpdateResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            message=f"Update available: {current} → {manifest.version}",
            current_version=current,
            latest_version=manifest.version,
            manifest=manifest,
        )

    return UpdateResult(
        status=UpdateStatus.UP_TO_DATE,
        message=f"You are on the latest version ({current}).",
        current_version=current,
        latest_version=manifest.version,
        manifest=manifest,
    )


# ---------------------------------------------------------------------- #
# Run (download only)
# ---------------------------------------------------------------------- #
def run_update(
    manifest: Optional[UpdateManifest] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> UpdateResult:
    """
    Download the installer for `manifest`. Does NOT install silently.

    Returns UpdateResult with `installer_path` set for the GUI to
    offer a "Run installer" button.
    """
    current = get_current_version()
    if manifest is None:
        # Try local cache
        manifest = load_local_manifest()
        if manifest is None:
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message="No manifest available. Run check first.",
                current_version=current,
                error="No manifest",
            )

    if not manifest.download_url:
        return UpdateResult(
            status=UpdateStatus.FAILED,
            message="Manifest has no download_url.",
            current_version=current,
            latest_version=manifest.version,
            manifest=manifest,
            error="No download_url",
        )

    downloader = UpdateDownloader(
        timeout=float(ConfigManager.get("updater.download_timeout_seconds", 600)),
    )
    dest = downloader.default_download_dir() / _safe_filename(manifest.download_url)

    try:
        result = downloader.download(
            manifest.download_url,
            dest,
            expected_sha256=manifest.sha256,
            on_progress=on_progress,
        )
    except DownloadError as exc:
        logger.error("update_download_failed", error=str(exc))
        return UpdateResult(
            status=UpdateStatus.FAILED,
            message=str(exc),
            current_version=current,
            latest_version=manifest.version,
            manifest=manifest,
            error=str(exc),
        )

    # Windows tip: run installer with UAC prompt
    return UpdateResult(
        status=UpdateStatus.DOWNLOADED,
        message=(
            f"Downloaded EVA {manifest.version}. "
            f"Run the installer to update."
        ),
        current_version=current,
        latest_version=manifest.version,
        manifest=manifest,
        installer_path=result.path,
    )


def launch_installer(installer_path: str) -> bool:
    """
    Start the downloaded installer. Fails silently if OS blocks it.
    """
    path = Path(installer_path)
    if not path.exists():
        logger.warning("installer_missing", path=installer_path)
        return False
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        logger.info("installer_launched", path=installer_path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("installer_launch_failed", error=str(exc))
        return False


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _safe_filename(url: str) -> str:
    """Extract a clean filename from a URL, fallback to a default."""
    try:
        base = url.rsplit("/", 1)[-1].split("?", 1)[0]
        # Keep only safe characters
        safe = "".join(c for c in base if c.isalnum() or c in "._-")
        return safe or "EVA_Setup.exe"
    except Exception:  # noqa: BLE001
        return "EVA_Setup.exe"