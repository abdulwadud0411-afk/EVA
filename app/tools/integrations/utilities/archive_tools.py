"""
Archive tools.

Uses Python's stdlib (zipfile, tarfile) — no external tool needed.
If 7-Zip is present, we can call it for .7z files.

Tools:
    - archive_compress  : create .zip / .tar.gz / .tar
    - archive_extract   : extract an archive
    - archive_list      : list archive contents
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _sevenzip() -> str | None:
    for name in ("7z", "7z.exe"):
        found = shutil.which(name)
        if found:
            return found
    for p in (
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if Path(p).exists():
            return p
    return None


# ---------------------------------------------------------------------- #
# Tool: archive_compress
# ---------------------------------------------------------------------- #
class ArchiveCompressTool(AppIntegrationTool):
    APP_KEY = "archive"
    CONFIG_SECTION = "integrations.utilities"

    name = "archive_compress"
    description = "Compress a folder or file into .zip, .tar.gz, or .tar."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "output": {"type": "string"},
            "format": {"type": "string"},
        },
        "required": ["source", "output"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        source = Path(str(kwargs.get("source", ""))).expanduser()
        output = Path(str(kwargs.get("output", ""))).expanduser()
        if not source.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SOURCE_NOT_FOUND", "message": str(source)},
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        fmt = str(kwargs.get("format") or "zip").lower()

        try:
            if fmt == "zip":
                with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                    if source.is_dir():
                        for f in source.rglob("*"):
                            if f.is_file():
                                zf.write(f, f.relative_to(source.parent))
                    else:
                        zf.write(source, source.name)
            elif fmt in ("tar", "tar.gz", "tgz"):
                mode = "w:gz" if fmt in ("tar.gz", "tgz") else "w"
                with tarfile.open(output, mode) as tf:
                    tf.add(source, arcname=source.name)
            else:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "UNSUPPORTED_FORMAT", "message": fmt},
                )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "COMPRESS_FAILED", "message": str(exc)},
            )

        size = output.stat().st_size if output.exists() else 0
        return ToolResult(
            success=output.exists(),
            tool=self.name,
            data={"output": str(output), "size": size, "format": fmt},
        )


# ---------------------------------------------------------------------- #
# Tool: archive_extract
# ---------------------------------------------------------------------- #
class ArchiveExtractTool(AppIntegrationTool):
    APP_KEY = "archive"
    CONFIG_SECTION = "integrations.utilities"

    name = "archive_extract"
    description = "Extract a .zip, .tar, .tar.gz, or .7z archive."
    parameters = {
        "type": "object",
        "properties": {
            "archive_path": {"type": "string"},
            "output_dir": {"type": "string"},
        },
        "required": ["archive_path", "output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        archive = Path(str(kwargs.get("archive_path", ""))).expanduser()
        out = Path(str(kwargs.get("output_dir", ""))).expanduser()
        if not archive.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "ARCHIVE_NOT_FOUND", "message": str(archive)},
            )
        out.mkdir(parents=True, exist_ok=True)

        try:
            suffix = archive.suffix.lower()
            if suffix == ".zip":
                with zipfile.ZipFile(archive, "r") as zf:
                    zf.extractall(out)
            elif suffix in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
                with tarfile.open(archive, "r:*") as tf:
                    tf.extractall(out)
            elif suffix == ".7z":
                sz = _sevenzip()
                if not sz:
                    return ToolResult(
                        success=False,
                        tool=self.name,
                        error={
                            "code": "SEVENZIP_NOT_FOUND",
                            "message": "Install 7-Zip to extract .7z archives.",
                        },
                    )
                r = subprocess.run(
                    [sz, "x", str(archive), f"-o{out}", "-y"],
                    capture_output=True, text=True, timeout=1800,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if r.returncode != 0:
                    return ToolResult(
                        success=False,
                        tool=self.name,
                        error={"code": "EXTRACT_FAILED", "message": (r.stderr or "")[-500:]},
                    )
            else:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "UNSUPPORTED_FORMAT", "message": suffix},
                )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXTRACT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"archive": str(archive), "output_dir": str(out)},
        )


# ---------------------------------------------------------------------- #
# Tool: archive_list
# ---------------------------------------------------------------------- #
class ArchiveListTool(AppIntegrationTool):
    APP_KEY = "archive"
    CONFIG_SECTION = "integrations.utilities"

    name = "archive_list"
    description = "List the contents of a .zip or .tar archive."
    parameters = {
        "type": "object",
        "properties": {
            "archive_path": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["archive_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        archive = Path(str(kwargs.get("archive_path", ""))).expanduser()
        if not archive.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "ARCHIVE_NOT_FOUND", "message": str(archive)},
            )
        try:
            limit = int(kwargs.get("limit") or 100)
        except (TypeError, ValueError):
            limit = 100
        if limit <= 0 or limit > 10000:
            limit = 100

        entries: List[str] = []
        try:
            suffix = archive.suffix.lower()
            if suffix == ".zip":
                with zipfile.ZipFile(archive, "r") as zf:
                    for name in zf.namelist():
                        entries.append(name)
                        if len(entries) >= limit:
                            break
            elif suffix in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
                with tarfile.open(archive, "r:*") as tf:
                    for m in tf.getmembers():
                        entries.append(m.name)
                        if len(entries) >= limit:
                            break
            else:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "UNSUPPORTED_FORMAT", "message": suffix},
                )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LIST_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"count": len(entries), "entries": entries},
        )