"""
Permission manager (Phase 20).

Central gate for tool execution. Reads permission scopes from
`config/permissions.yaml` and decides whether a given tool call is:
    - allowed   (run without confirmation)
    - confirm   (ask user first)
    - denied    (block entirely)

Public API:
    from app.security.permissions import PermissionManager, PermissionDecision
    decision = PermissionManager.check("delete_file", risk="MEDIUM")
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PermissionDecision:
    """Outcome of a permission check."""
    allow: bool
    requires_confirmation: bool = False
    reason: str = ""
    scope: str = ""
    matched_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "scope": self.scope,
            "matched_rule": self.matched_rule,
        }


class PermissionManager:
    """Decide whether a tool call is allowed."""

    _config: Optional[Dict[str, Any]] = None
    _permissions_file: Optional[Path] = None

    # Tool → category mapping
    _TOOL_CATEGORY: Dict[str, str] = {
        "read_file": "file_read",
        "write_file": "file_write",
        "move_file": "file_write",
        "copy_file": "file_write",
        "delete_file": "file_delete",
        "create_folder": "file_write",
        "list_directory": "file_read",
        "search_files": "file_read",
        "open_application": "app_control",
        "close_application": "app_control",
        "list_running_applications": "system_info",
        "focus_window": "app_control",
        "minimize_window": "app_control",
        "maximize_window": "app_control",
        "run_terminal_command": "terminal",
        "open_url": "network",
        "search_web": "network",
        "new_tab": "network",
        "close_tab": "network",
        "download_file": "network",
        "get_system_info": "system_info",
        "get_disk_usage": "system_info",
        "list_top_processes": "system_info",
        "get_battery_status": "system_info",
        "get_network_info": "system_info",
        "get_clipboard_text": "clipboard",
        "set_clipboard_text": "clipboard",
        "take_screenshot": "vision",
        "analyze_screen": "vision",
        "find_ui_element": "vision",
    }

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def _permissions_path(cls) -> Path:
        if cls._permissions_file is not None:
            return cls._permissions_file
        return ConfigManager.get_project_root() / "config" / "permissions.yaml"

    @classmethod
    def configure(cls, path: Path) -> None:
        cls._permissions_file = Path(path)
        cls._config = None

    @classmethod
    def reload(cls) -> None:
        cls._config = None

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        if cls._config is not None:
            return cls._config

        path = cls._permissions_path()
        if not path.exists():
            logger.warning("permissions_file_missing", path=str(path))
            cls._config = {}
            return cls._config

        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            cls._config = data.get("permissions", data) or {}
            return cls._config
        except Exception as exc:  # noqa: BLE001
            logger.error("permissions_load_failed", error=str(exc))
            cls._config = {}
            return cls._config

    # ------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------ #
    @classmethod
    def check(
        cls,
        tool_name: str,
        risk: str = "LOW",
    ) -> PermissionDecision:
        cfg = cls._load()
        tool_name = (tool_name or "").strip()
        risk = (risk or "LOW").upper()

        # 1. Master switch
        if cfg.get("require_confirmation_master", False):
            return PermissionDecision(
                allow=False,
                requires_confirmation=True,
                reason="Master switch forces confirmation for every action.",
                scope="confirm",
                matched_rule="master",
            )

        # 2. Per-tool override
        overrides = cfg.get("tool_overrides", {}) or {}
        override = overrides.get(tool_name)
        if isinstance(override, dict):
            scope = str(override.get("scope", "")).lower()
            reason = str(override.get("reason", "tool override"))
            return cls._decision_from_scope(scope, reason, "tool_override")

        # 3. Per-category scope
        category = cls._TOOL_CATEGORY.get(tool_name)
        if category:
            scopes = cfg.get("scope", {}) or {}
            scope = str(scopes.get(category, "")).lower()
            if scope:
                return cls._decision_from_scope(
                    scope, f"category '{category}'", "scope",
                )

        # 4. Risk-level default
        risk_defaults = cfg.get("risk_defaults", {}) or {}
        scope = str(risk_defaults.get(risk, "allow")).lower()
        return cls._decision_from_scope(
            scope, f"risk level {risk}", "risk_default",
        )

    @staticmethod
    def _decision_from_scope(scope: str, reason: str, rule: str) -> PermissionDecision:
        scope = (scope or "allow").lower()
        if scope == "allow":
            return PermissionDecision(
                allow=True, requires_confirmation=False,
                reason=f"Allowed by {reason}.",
                scope="allow", matched_rule=rule,
            )
        if scope == "confirm":
            return PermissionDecision(
                allow=False, requires_confirmation=True,
                reason=f"Confirmation required by {reason}.",
                scope="confirm", matched_rule=rule,
            )
        if scope == "deny":
            return PermissionDecision(
                allow=False, requires_confirmation=False,
                reason=f"Denied by {reason}.",
                scope="deny", matched_rule=rule,
            )
        return PermissionDecision(
            allow=False, requires_confirmation=True,
            reason=f"Unknown scope '{scope}' — defaulting to confirm.",
            scope="confirm", matched_rule=rule,
        )

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @classmethod
    def describe(cls) -> Dict[str, Any]:
        cfg = cls._load()
        return {
            "master_switch": bool(cfg.get("require_confirmation_master", False)),
            "scopes": dict(cfg.get("scope", {}) or {}),
            "tool_overrides": dict(cfg.get("tool_overrides", {}) or {}),
            "risk_defaults": dict(cfg.get("risk_defaults", {}) or {}),
        }