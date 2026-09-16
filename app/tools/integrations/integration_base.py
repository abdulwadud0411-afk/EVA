"""
Base class for all application-integration tools (Integrations Layer).

`AppIntegrationTool` extends the core `Tool` with:
    - App discovery via app.tools.discovery
    - Permission check via app.tools.permissions
    - Post-action verification via app.tools.verifier
    - Standardized result building

Subclasses override:
    - APP_KEY: the discovery key (e.g. "blender")
    - CONFIG_SECTION: config path (e.g. "integrations.blender")
    - name, description, parameters, risk_level
    - run_impl(**kwargs) -> ToolResult
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel
from app.tools.discovery import discover_known_app
from app.tools.permissions import PermissionManager

logger = get_logger(__name__)


class AppIntegrationTool(Tool):
    """Base class every application integration tool must inherit from."""

    # Subclasses MUST override these
    APP_KEY: str = ""
    CONFIG_SECTION: str = ""

    # Subclasses may override
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False

    # ------------------------------------------------------------------ #
    # Config helpers
    # ------------------------------------------------------------------ #
    def _config(self, key: str, default: Any = None) -> Any:
        """Read a value from this tool's config section."""
        if not self.CONFIG_SECTION:
            return default
        return ConfigManager.get(f"{self.CONFIG_SECTION}.{key}", default)

    def _is_enabled(self) -> bool:
        """Return True if the integration is enabled in config."""
        return bool(self._config("enabled", True))

    def _discover_path(self, override_key: str = "executable_path") -> Optional[str]:
        """
        Locate the app's executable via config override + discovery.
        Returns None when the app is not found.
        """
        if not self.APP_KEY:
            return None
        config_path = self._config(override_key, "auto")
        return discover_known_app(self.APP_KEY, config_path=str(config_path) if config_path else None)

    # ------------------------------------------------------------------ #
    # Permission helper
    # ------------------------------------------------------------------ #
    async def _check_permission(
        self,
        title: str = "",
        message: str = "",
    ):
        """Check whether this tool is allowed to run. Returns PermissionDecision."""
        return await PermissionManager.check(
            tool_name=self.name,
            risk=self.risk_level,
            title=title,
            message=message,
        )

    # ------------------------------------------------------------------ #
    # Result helpers
    # ------------------------------------------------------------------ #
    def _disabled_result(self) -> ToolResult:
        return ToolResult(
            success=False,
            tool=self.name,
            error={
                "code": "INTEGRATION_DISABLED",
                "message": (
                    f"Integration '{self.APP_KEY}' is disabled in config. "
                    f"Set {self.CONFIG_SECTION}.enabled = true to use it."
                ),
            },
        )

    def _not_installed_result(self, hint: str = "") -> ToolResult:
        msg = f"'{self.APP_KEY}' is not installed or could not be discovered."
        if hint:
            msg += f" {hint}"
        return ToolResult(
            success=False,
            tool=self.name,
            error={"code": "APP_NOT_FOUND", "message": msg},
        )

    def _permission_denied_result(self, reason: str) -> ToolResult:
        return ToolResult(
            success=False,
            tool=self.name,
            error={"code": "PERMISSION_DENIED", "message": reason},
        )

    # ------------------------------------------------------------------ #
    # Main run — orchestrates permission + run_impl
    # ------------------------------------------------------------------ #
    async def run(self, **kwargs: Any) -> ToolResult:
        # 1. Config gate
        if not self._is_enabled():
            logger.info("integration_disabled", tool=self.name, app=self.APP_KEY)
            return self._disabled_result()

        # 2. Permission gate
        decision = await self._check_permission(
            title=f"{self.APP_KEY.title()}: {self.description}",
            message=(
                f"Tool: {self.name}\n"
                f"Arguments: {kwargs}\n"
                f"Risk: {self.risk_level.value}"
            ),
        )
        if not decision.allowed:
            return self._permission_denied_result(decision.reason)

        # 3. Run implementation
        try:
            result = await self.run_impl(**kwargs)
        except NotImplementedError:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "NOT_IMPLEMENTED",
                    "message": f"{self.name}.run_impl is not implemented.",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("integration_run_failed", tool=self.name, error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RUN_FAILED", "message": str(exc)},
            )
        return result

    # ------------------------------------------------------------------ #
    # Subclasses implement this
    # ------------------------------------------------------------------ #
    async def run_impl(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError