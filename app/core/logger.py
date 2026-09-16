"""
Structured JSONL logger with automatic secret redaction.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config_manager import ConfigManager

_SENSITIVE_KEYS = {"api_key", "apikey", "token", "secret", "password", "authorization"}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


class JSONLLogger:
    """Append-only JSONL logger."""

    _instance: Optional["JSONLLogger"] = None
    _lock = threading.Lock()

    def __init__(self, log_dir: Optional[Path] = None) -> None:
        if log_dir is None:
            log_dir = ConfigManager.get_data_dir() / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"eva-{datetime.now():%Y-%m-%d}.jsonl"

    def log(self, level: str, message: str, **fields: Any) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "level": level.upper(),
            "message": message,
        }
        if fields:
            entry["fields"] = fields
        entry = _redact(entry)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as fh:
                fh.write(line)

    def debug(self, msg: str, **f: Any) -> None: self.log("DEBUG", msg, **f)
    def info(self, msg: str, **f: Any) -> None: self.log("INFO", msg, **f)
    def warning(self, msg: str, **f: Any) -> None: self.log("WARNING", msg, **f)
    def error(self, msg: str, **f: Any) -> None: self.log("ERROR", msg, **f)


def get_logger(name: str = "eva") -> JSONLLogger:
    """Return the process-wide logger (name kept for API compatibility)."""
    if JSONLLogger._instance is None:
        JSONLLogger._instance = JSONLLogger()
    return JSONLLogger._instance