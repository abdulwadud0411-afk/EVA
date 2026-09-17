"""
Rate limiter (Phase 20).

Sliding-window rate limiter per tool. Prevents:
    - Runaway agent loops calling the same tool 100x/minute
    - Bulk destructive actions (delete 1000 files)

Public API:
    from app.security.rate_limiter import RateLimiter
    ok = RateLimiter.allow("delete_file")
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Sliding window per-tool rate limiter."""

    _lock = threading.Lock()
    _windows: Dict[str, Deque[float]] = defaultdict(deque)
    _default_per_minute: int = 30
    _per_tool: Dict[str, int] = {}
    _enabled: bool = True
    _loaded: bool = False

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def _load(cls) -> None:
        if cls._loaded:
            return
        cls._enabled = bool(ConfigManager.get("security.rate_limit.enabled", True))
        try:
            cls._default_per_minute = int(
                ConfigManager.get("security.rate_limit.default_per_minute", 30)
            )
        except (TypeError, ValueError):
            cls._default_per_minute = 30
        if cls._default_per_minute <= 0:
            cls._default_per_minute = 30

        per_tool = ConfigManager.get("security.rate_limit.per_tool", None)
        if isinstance(per_tool, dict):
            cls._per_tool = {}
            for k, v in per_tool.items():
                try:
                    cls._per_tool[str(k)] = int(v)
                except (TypeError, ValueError):
                    continue
        cls._loaded = True

    @classmethod
    def reload(cls) -> None:
        cls._loaded = False
        with cls._lock:
            cls._windows.clear()

    @classmethod
    def configure(
        cls,
        enabled: bool = True,
        default_per_minute: int = 30,
        per_tool: Optional[Dict[str, int]] = None,
    ) -> None:
        cls._enabled = enabled
        cls._default_per_minute = max(1, int(default_per_minute))
        cls._per_tool = dict(per_tool or {})
        cls._loaded = True

    # ------------------------------------------------------------------ #
    # Check
    # ------------------------------------------------------------------ #
    @classmethod
    def _limit_for(cls, tool_name: str) -> int:
        cls._load()
        return int(cls._per_tool.get(tool_name, cls._default_per_minute))

    @classmethod
    def allow(cls, tool_name: str) -> bool:
        """Return True if the call is allowed, False if rate-limited."""
        cls._load()
        if not cls._enabled:
            return True

        limit = cls._limit_for(tool_name)
        now = time.time()
        cutoff = now - 60.0  # 1 minute window

        with cls._lock:
            window = cls._windows[tool_name]
            # Drop old timestamps
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= limit:
                logger.warning(
                    "rate_limit_hit",
                    tool=tool_name, limit=limit, current=len(window),
                )
                return False

            window.append(now)
            return True

    @classmethod
    def reset(cls, tool_name: Optional[str] = None) -> None:
        """Clear rate-limit state (used by tests)."""
        with cls._lock:
            if tool_name is None:
                cls._windows.clear()
            else:
                cls._windows.pop(tool_name, None)

    @classmethod
    def stats(cls) -> Dict[str, Dict[str, int]]:
        cls._load()
        now = time.time()
        cutoff = now - 60.0
        out: Dict[str, Dict[str, int]] = {}
        with cls._lock:
            for tool, window in cls._windows.items():
                count = sum(1 for t in window if t >= cutoff)
                if count:
                    out[tool] = {
                        "count": count,
                        "limit": cls._limit_for(tool),
                    }
        return out