"""
Audit log (Phase 20).

Append-only, HMAC-signed JSONL log for every security-relevant event.

Each line is a JSON object containing:
    - timestamp
    - event     (e.g. "TOOL_STARTED", "CONFIRMATION_APPROVED")
    - actor     ("user" | "agent" | "system")
    - tool      (name)
    - risk      (LOW/MEDIUM/HIGH/CRITICAL)
    - data      (sanitized payload)
    - hmac      (HMAC-SHA256 of the line, using a per-install secret)

Tampering with any line breaks the HMAC chain and can be detected.

Public API:
    from app.security.audit_log import AuditLog
    AuditLog.log("TOOL_STARTED", tool="delete_file", risk="HIGH", data={...})
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.security.redactor import Redactor

logger = get_logger(__name__)


class AuditLog:
    """HMAC-signed JSONL audit log."""

    _secret: Optional[bytes] = None
    _log_path: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # Paths & secret
    # ------------------------------------------------------------------ #
    @classmethod
    def _security_dir(cls) -> Path:
        d = ConfigManager.get_data_dir() / "security" / "audit"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def _secret_path(cls) -> Path:
        return ConfigManager.get_data_dir() / "security" / "audit.secret"

    @classmethod
    def _get_secret(cls) -> bytes:
        if cls._secret is not None:
            return cls._secret

        path = cls._secret_path()
        if path.exists():
            try:
                cls._secret = path.read_bytes().strip()
                return cls._secret
            except OSError as exc:
                logger.warning("audit_secret_read_failed", error=str(exc))

        # Generate a new secret
        secret = secrets.token_bytes(32)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(secret)
        except OSError as exc:
            logger.warning("audit_secret_write_failed", error=str(exc))
        cls._secret = secret
        return cls._secret

    @classmethod
    def _get_log_path(cls) -> Path:
        if cls._log_path is not None:
            return cls._log_path
        return cls._security_dir() / f"audit-{datetime.now():%Y-%m-%d}.jsonl"

    @classmethod
    def configure(cls, log_path: Path) -> None:
        cls._log_path = Path(log_path)

    @classmethod
    def reload(cls) -> None:
        cls._secret = None
        cls._log_path = None

    # ------------------------------------------------------------------ #
    # Core
    # ------------------------------------------------------------------ #
    @classmethod
    def _sign(cls, payload: bytes) -> str:
        return hmac.new(cls._get_secret(), payload, hashlib.sha256).hexdigest()

    @classmethod
    def log(
        cls,
        event: str,
        actor: str = "agent",
        tool: str = "",
        risk: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "event": str(event),
            "actor": str(actor),
            "tool": str(tool),
            "risk": str(risk),
            "data": Redactor.redact(data or {}),
        }
        # Serialize with sorted keys so HMAC is deterministic
        body = json.dumps(entry, ensure_ascii=False, sort_keys=True).encode("utf-8")
        entry["hmac"] = cls._sign(body)

        line = json.dumps(entry, ensure_ascii=False)
        try:
            with open(cls._get_log_path(), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.warning("audit_write_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #
    @classmethod
    def verify_file(cls, path: Path) -> Dict[str, Any]:
        """
        Verify every line in a log file.

        Returns {ok, total, broken_lines: [ints]}
        """
        path = Path(path)
        if not path.exists():
            return {"ok": False, "reason": "file not found", "total": 0, "broken_lines": []}

        broken = []
        total = 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for i, line in enumerate(fh, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        broken.append(i)
                        continue
                    claimed = entry.pop("hmac", None)
                    if not claimed:
                        broken.append(i)
                        continue
                    body = json.dumps(
                        entry, ensure_ascii=False, sort_keys=True,
                    ).encode("utf-8")
                    expected = cls._sign(body)
                    if not hmac.compare_digest(claimed, expected):
                        broken.append(i)
        except OSError as exc:
            return {"ok": False, "reason": str(exc), "total": total, "broken_lines": broken}

        return {
            "ok": len(broken) == 0,
            "total": total,
            "broken_lines": broken,
            "path": str(path),
        }

    @classmethod
    def recent(cls, limit: int = 50) -> list:
        path = cls._get_log_path()
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out