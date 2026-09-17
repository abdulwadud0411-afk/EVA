"""
Update downloader (Phase 22 Batch 3).

Streams a file from `download_url` to a local path with:
    - Progress callback (bytes_done, total_bytes)
    - SHA-256 verification (fails if hash mismatch)
    - Resume-safe filename (appends .part while downloading)

Public API:
    dl = UpdateDownloader()
    result = dl.download(url, dest, expected_sha256="...", on_progress=fn)
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.core.logger import get_logger
from app.core.paths import get_data_dir

logger = get_logger(__name__)


class DownloadError(Exception):
    """Raised when a download fails or verification fails."""


ProgressCB = Callable[[int, int], None]   # (done_bytes, total_bytes)


@dataclass
class DownloadResult:
    path: str
    size_bytes: int
    sha256: str
    verified: bool

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "verified": self.verified,
        }


class UpdateDownloader:
    """Stream download + SHA-256 verify."""

    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def download(
        self,
        url: str,
        dest: Path,
        expected_sha256: str = "",
        on_progress: Optional[ProgressCB] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> DownloadResult:
        if not url:
            raise DownloadError("Empty download URL")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        tmp = dest.with_suffix(dest.suffix + ".part")
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

        hasher = hashlib.sha256()
        done = 0
        total = 0

        kwargs = {"timeout": self.timeout}
        if transport is not None:
            kwargs["transport"] = transport

        try:
            with httpx.Client(**kwargs) as client:
                with client.stream("GET", url) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0) or 0)
                    with open(tmp, "wb") as fh:
                        for chunk in r.iter_bytes(chunk_size=65536):
                            if not chunk:
                                continue
                            fh.write(chunk)
                            hasher.update(chunk)
                            done += len(chunk)
                            if on_progress is not None:
                                try:
                                    on_progress(done, total)
                                except Exception:  # noqa: BLE001
                                    pass
        except httpx.HTTPError as exc:
            self._cleanup(tmp)
            raise DownloadError(f"Network error: {exc}") from exc
        except OSError as exc:
            self._cleanup(tmp)
            raise DownloadError(f"Disk error: {exc}") from exc

        sha = hasher.hexdigest()

        # Verify BEFORE renaming to final
        verified = True
        if expected_sha256:
            verified = (sha.lower() == expected_sha256.lower().strip())
            if not verified:
                self._cleanup(tmp)
                raise DownloadError(
                    f"SHA-256 mismatch — expected {expected_sha256}, got {sha}"
                )

        # Atomic-ish move to final destination
        try:
            if dest.exists():
                dest.unlink()
            tmp.rename(dest)
        except OSError as exc:
            self._cleanup(tmp)
            raise DownloadError(f"Cannot finalize download: {exc}") from exc

        logger.info(
            "update_downloaded",
            path=str(dest),
            size=done,
            verified=verified,
        )
        return DownloadResult(
            path=str(dest),
            size_bytes=done,
            sha256=sha,
            verified=verified,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cleanup(p: Path) -> None:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass

    @staticmethod
    def default_download_dir() -> Path:
        d = get_data_dir() / "updates"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def format_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"