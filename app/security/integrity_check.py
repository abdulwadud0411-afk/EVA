"""
File integrity check (Phase 22).

Computes SHA-256 hashes of critical files and stores them in a
manifest. On startup, the manifest can be verified to detect
unauthorized modifications.

Two modes:
    - "build"    — create manifest from current files
    - "verify"   — compare current files against manifest

Public API:
    build_manifest(patterns=...) -> dict
    save_manifest(path)
    load_manifest(path) -> dict | None
    verify(manifest, strict=True) -> dict
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core.logger import get_logger
from app.core.paths import get_app_root

logger = get_logger(__name__)


# Files/folders to include in the manifest
DEFAULT_INCLUDE_PATTERNS: List[str] = [
    "app/**/*.py",
    "config/*.yaml",
    "prompts/*.txt",
]


def _hash_file(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(chunk), b""):
                h.update(block)
    except OSError:
        return ""
    return h.hexdigest()


def _iter_files(root: Path, patterns: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        for p in root.glob(pattern):
            if p.is_file() and "__pycache__" not in p.parts:
                files.append(p)
    return files


# ---------------------------------------------------------------------- #
# Build
# ---------------------------------------------------------------------- #
def build_manifest(
    root: Optional[Path] = None,
    patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Hash all matching files and return a manifest dict."""
    root = Path(root or get_app_root())
    patterns = patterns or DEFAULT_INCLUDE_PATTERNS
    files = _iter_files(root, patterns)

    entries: Dict[str, str] = {}
    for f in files:
        rel = f.relative_to(root).as_posix()
        entries[rel] = _hash_file(f)

    return {
        "created_at": datetime.now().isoformat(),
        "root": str(root),
        "file_count": len(entries),
        "files": entries,
    }


def save_manifest(manifest: Dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> Optional[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("integrity_manifest_load_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Verify
# ---------------------------------------------------------------------- #
def verify(
    manifest: Dict[str, Any],
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Verify current files against a stored manifest.

    Returns:
        {
          "ok": bool,
          "checked": int,
          "modified": [paths],
          "missing": [paths],
          "added": [paths],
        }
    """
    root = Path(root or get_app_root())
    expected = manifest.get("files", {}) or {}
    patterns = DEFAULT_INCLUDE_PATTERNS
    current_files = _iter_files(root, patterns)

    current: Dict[str, str] = {}
    for f in current_files:
        rel = f.relative_to(root).as_posix()
        current[rel] = _hash_file(f)

    modified: List[str] = []
    missing: List[str] = []
    for rel, old_hash in expected.items():
        if rel not in current:
            missing.append(rel)
        elif current[rel] != old_hash:
            modified.append(rel)

    added = [rel for rel in current.keys() if rel not in expected]

    ok = not modified and not missing
    if not ok:
        logger.warning(
            "integrity_violation",
            modified=len(modified),
            missing=len(missing),
            added=len(added),
        )

    return {
        "ok": ok,
        "checked": len(expected),
        "modified": modified,
        "missing": missing,
        "added": added,
    }


# ---------------------------------------------------------------------- #
# Convenience
# ---------------------------------------------------------------------- #
def manifest_path(data_dir: Path) -> Path:
    return Path(data_dir) / "security" / "integrity.json"


def build_and_save(data_dir: Path) -> Dict[str, Any]:
    m = build_manifest()
    save_manifest(m, manifest_path(data_dir))
    return m


def verify_saved(data_dir: Path) -> Dict[str, Any]:
    m = load_manifest(manifest_path(data_dir))
    if m is None:
        return {"ok": True, "reason": "no manifest", "checked": 0,
                "modified": [], "missing": [], "added": []}
    return verify(m)