"""
Update manifest (Phase 22 Batch 3).

The manifest is a small JSON file hosted by the vendor:

    {
      "version": "0.23.0",
      "channel": "stable",
      "released_at": "2026-10-01T00:00:00",
      "download_url": "https://example.com/eva/EVA_Setup_0.23.0.exe",
      "sha256": "abc123...",
      "size_bytes": 754321000,
      "min_supported_version": "0.20.0",
      "notes": "Bug fixes + new GUI themes."
    }

Public API:
    m = fetch_manifest("https://...")     # network
    is_newer("0.22.0", "0.23.0") -> bool
    compare_versions("0.22.0", "0.23.0") -> -1
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.core.logger import get_logger
from app.core.paths import get_data_dir

logger = get_logger(__name__)


class ManifestError(Exception):
    """Raised when a manifest is invalid or unreachable."""


# ---------------------------------------------------------------------- #
# Version parsing
# ---------------------------------------------------------------------- #
_VERSION_RE = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple:
    """
    Return (major, minor, patch, suffix) from a version string.

    Suffix examples: "-beta.1", "-rc.2", "" (stable).
    Raises ManifestError if unparseable.
    """
    if not text:
        raise ManifestError("Empty version string")
    m = _VERSION_RE.match(text)
    if not m:
        raise ManifestError(f"Invalid version: {text!r}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    suffix = text[m.end():].strip()
    return (major, minor, patch, suffix)


def compare_versions(a: str, b: str) -> int:
    """
    Return -1 if a < b, 0 if equal, +1 if a > b.
    Pre-release suffixes ('-beta') sort BEFORE the stable release.
    """
    pa = parse_version(a)
    pb = parse_version(b)

    # Compare numeric parts first
    if pa[:3] < pb[:3]:
        return -1
    if pa[:3] > pb[:3]:
        return 1

    sa, sb = pa[3], pb[3]
    if sa == sb:
        return 0
    # Empty suffix (stable) is considered newer than non-empty (pre-release)
    if not sa and sb:
        return 1
    if sa and not sb:
        return -1
    return -1 if sa < sb else 1


def is_newer(current: str, candidate: str) -> bool:
    return compare_versions(current, candidate) < 0


# ---------------------------------------------------------------------- #
# Manifest dataclass
# ---------------------------------------------------------------------- #
@dataclass
class UpdateManifest:
    version: str
    channel: str = "stable"
    released_at: str = ""
    download_url: str = ""
    sha256: str = ""
    size_bytes: int = 0
    min_supported_version: str = ""
    notes: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateManifest":
        if not isinstance(data, dict):
            raise ManifestError("Manifest root must be a JSON object")
        version = str(data.get("version", "")).strip()
        if not version:
            raise ManifestError("Manifest missing 'version'")
        # Validate version format early
        parse_version(version)

        return cls(
            version=version,
            channel=str(data.get("channel", "stable")),
            released_at=str(data.get("released_at", "")),
            download_url=str(data.get("download_url", "")),
            sha256=str(data.get("sha256", "")).lower().strip(),
            size_bytes=int(data.get("size_bytes", 0) or 0),
            min_supported_version=str(data.get("min_supported_version", "")),
            notes=str(data.get("notes", "")),
            raw=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "channel": self.channel,
            "released_at": self.released_at,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "min_supported_version": self.min_supported_version,
            "notes": self.notes,
        }

    def is_compatible_with(self, current_version: str) -> bool:
        """Return False if our version is too old to upgrade directly."""
        if not self.min_supported_version:
            return True
        try:
            return compare_versions(current_version, self.min_supported_version) >= 0
        except ManifestError:
            return True


# ---------------------------------------------------------------------- #
# Fetch
# ---------------------------------------------------------------------- #
def fetch_manifest(
    url: str,
    timeout: float = 15.0,
    transport: Optional[httpx.BaseTransport] = None,
) -> UpdateManifest:
    """Download and parse a remote manifest."""
    if not url:
        raise ManifestError("Manifest URL is empty")

    try:
        kwargs: Dict[str, Any] = {"timeout": timeout}
        if transport is not None:
            kwargs["transport"] = transport
        with httpx.Client(**kwargs) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        raise ManifestError(f"Network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest is not valid JSON: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ManifestError(f"Fetch failed: {exc}") from exc

    logger.info("update_manifest_fetched", url=url, version=data.get("version"))
    return UpdateManifest.from_dict(data)


# ---------------------------------------------------------------------- #
# Local cache
# ---------------------------------------------------------------------- #
def _local_manifest_path() -> Path:
    d = get_data_dir() / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d / "last_manifest.json"


def save_local_manifest(manifest: UpdateManifest) -> None:
    try:
        _local_manifest_path().write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("manifest_save_failed", error=str(exc))


def load_local_manifest() -> Optional[UpdateManifest]:
    p = _local_manifest_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return UpdateManifest.from_dict(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("manifest_load_failed", error=str(exc))
        return None


def describe_paths() -> Dict[str, str]:
    return {"last_manifest": str(_local_manifest_path())}