"""
EVA Updater module (Phase 22 Batch 3).

Checks for and downloads new versions of EVA.

Flow:
    1. Read remote manifest.json (https)
    2. Compare version
    3. Download installer (.exe) with SHA-256 verify
    4. Hand off to user (does NOT silently install)

Public API:
    from app.updater import (
        UpdateManifest, fetch_manifest, compare_versions,
        UpdateDownloader, UpdateResult,
    )
"""
from app.updater.manifest import (  # noqa: F401
    UpdateManifest,
    fetch_manifest,
    load_local_manifest,
    save_local_manifest,
    compare_versions,
    is_newer,
    ManifestError,
)
from app.updater.downloader import (  # noqa: F401
    UpdateDownloader,
    DownloadError,
    DownloadResult,
)
from app.updater.updater import (  # noqa: F401
    UpdateResult,
    UpdateStatus,
    check_for_updates,
    run_update,
    get_current_version,
)

__all__ = [
    "UpdateManifest",
    "fetch_manifest",
    "load_local_manifest",
    "save_local_manifest",
    "compare_versions",
    "is_newer",
    "ManifestError",
    "UpdateDownloader",
    "DownloadError",
    "DownloadResult",
    "UpdateResult",
    "UpdateStatus",
    "check_for_updates",
    "run_update",
    "get_current_version",
]