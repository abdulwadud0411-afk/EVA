"""
Network whitelist (Phase 20).

Restricts outbound HTTP/WebSocket calls to a set of approved domains.

Public API:
    from app.security.network_whitelist import NetworkWhitelist
    decision = NetworkWhitelist.check("https://api.deepseek.com/v1/...")
    if not decision.allow:
        raise NetworkBlocked(decision.reason)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class NetworkBlocked(Exception):
    """Raised when a host is not allowed by the whitelist."""


@dataclass
class WhitelistDecision:
    allow: bool
    host: str = ""
    reason: str = ""
    matched_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "host": self.host,
            "reason": self.reason,
            "matched_rule": self.matched_rule,
        }


# ---------------------------------------------------------------------- #
# Defaults (used if config file missing)
# ---------------------------------------------------------------------- #
_DEFAULT_ALLOWED = [
    "api.deepseek.com",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "openrouter.ai",
    "localhost",
    "127.0.0.1",
]


class NetworkWhitelist:
    """Check if a URL's host is on the whitelist."""

    _config: Optional[Dict[str, Any]] = None
    _config_file: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def _config_path(cls) -> Path:
        if cls._config_file is not None:
            return cls._config_file
        return ConfigManager.get_project_root() / "config" / "network_whitelist.yaml"

    @classmethod
    def configure(cls, path=None) -> None:
        """Set a custom config path (or pass None to reset to default)."""
        if path is not None:
            cls._config_file = Path(path)
        else:
            cls._config_file = None
        cls._config = None

    @classmethod
    def reload(cls) -> None:
        cls._config = None

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        if cls._config is not None:
            return cls._config

        path = cls._config_path()
        if not path.exists():
            logger.info("network_whitelist_using_defaults")
            cls._config = {
                "whitelist_enabled": True,
                "allow_subdomains": True,
                "block_all_others": True,
                "allowed_domains": list(_DEFAULT_ALLOWED),
                "denied_domains": [],
            }
            return cls._config

        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            cfg = raw.get("network", raw) or {}
            cls._config = {
                "whitelist_enabled": bool(cfg.get("whitelist_enabled", True)),
                "allow_subdomains": bool(cfg.get("allow_subdomains", True)),
                "block_all_others": bool(cfg.get("block_all_others", True)),
                "allowed_domains": [
                    str(d).lower().strip()
                    for d in (cfg.get("allowed_domains") or [])
                    if str(d).strip()
                ],
                "denied_domains": [
                    str(d).lower().strip()
                    for d in (cfg.get("denied_domains") or [])
                    if str(d).strip()
                ],
            }
            return cls._config
        except Exception as exc:  # noqa: BLE001
            logger.error("network_whitelist_load_failed", error=str(exc))
            cls._config = {}
            return cls._config

    # ------------------------------------------------------------------ #
    # Match helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_host(url: str) -> str:
        if not url:
            return ""
        # Handle bare hostnames (no scheme)
        if "://" not in url:
            url = "http://" + url
        try:
            parsed = urlparse(url)
            return (parsed.hostname or "").lower()
        except Exception:  # noqa: BLE001
            return ""

    @classmethod
    def _matches(cls, host: str, domain: str, allow_sub: bool) -> bool:
        host = host.lower()
        domain = domain.lower()
        if host == domain:
            return True
        if allow_sub and host.endswith("." + domain):
            return True
        return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @classmethod
    def check(cls, url: str) -> WhitelistDecision:
        cfg = cls._load()

        if not cfg.get("whitelist_enabled", True):
            return WhitelistDecision(
                allow=True, reason="whitelist disabled",
                matched_rule="disabled",
            )

        host = cls._extract_host(url)
        if not host:
            return WhitelistDecision(
                allow=False, host="", reason="cannot parse host from URL",
                matched_rule="invalid_url",
            )

        allow_sub = bool(cfg.get("allow_subdomains", True))

        # Denied domains take priority
        for d in cfg.get("denied_domains", []) or []:
            if cls._matches(host, d, allow_sub):
                return WhitelistDecision(
                    allow=False, host=host,
                    reason=f"host '{host}' explicitly denied",
                    matched_rule="denied",
                )

        # Allowed domains
        for d in cfg.get("allowed_domains", []) or []:
            if cls._matches(host, d, allow_sub):
                return WhitelistDecision(
                    allow=True, host=host,
                    reason=f"host '{host}' allowed",
                    matched_rule="allowed",
                )

        # Not in whitelist
        if cfg.get("block_all_others", True):
            logger.warning("network_blocked", host=host, url=url[:200])
            return WhitelistDecision(
                allow=False, host=host,
                reason=f"host '{host}' is not on the whitelist",
                matched_rule="unlisted",
            )

        # Log-only mode
        logger.info("network_unlisted_allowed", host=host)
        return WhitelistDecision(
            allow=True, host=host,
            reason="host not on whitelist but block_all_others=false",
            matched_rule="unlisted_log_only",
        )

    @classmethod
    def is_allowed(cls, url: str) -> bool:
        return cls.check(url).allow

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        cfg = cls._load()
        return {
            "enabled": cfg.get("whitelist_enabled", True),
            "allow_subdomains": cfg.get("allow_subdomains", True),
            "block_all_others": cfg.get("block_all_others", True),
            "allowed_domains": list(cfg.get("allowed_domains") or []),
            "denied_domains": list(cfg.get("denied_domains") or []),
        }