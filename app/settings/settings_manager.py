"""
Settings manager (Phase 17).

Thin wrapper around ConfigManager that:
    - Reads/writes active provider + its config
    - Persists to user_config.yaml
    - Never writes secrets to disk (API key stays in .env or is
      handled separately by the caller)

Public API:
    SettingsManager.get_active_provider() -> "deepseek"
    SettingsManager.set_active_provider("openai")
    SettingsManager.get_provider_config("openai") -> {...}
    SettingsManager.set_provider_config("openai", api_key="sk-...")
    SettingsManager.get_ai_settings() -> full snapshot for the GUI
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class SettingsError(Exception):
    """Raised when a settings operation fails."""


class SettingsManager:
    """Save/load AI provider settings with persistence."""

    # ------------------------------------------------------------------ #
    # Active provider
    # ------------------------------------------------------------------ #
    @classmethod
    def get_active_provider(cls) -> str:
        return str(ConfigManager.get("ai.provider", "deepseek")).lower()

    @classmethod
    def set_active_provider(cls, name: str) -> None:
        name = (name or "").strip().lower()
        if not name:
            raise SettingsError("Provider name cannot be empty")
        ConfigManager.set("ai.provider", name, persist=True)
        logger.info("settings_active_provider_changed", provider=name)

    # ------------------------------------------------------------------ #
    # Provider config
    # ------------------------------------------------------------------ #
    @classmethod
    def get_provider_config(cls, name: str) -> Dict[str, Any]:
        """Return the current config dict for the given provider."""
        name = (name or "").strip().lower()
        section = ConfigManager.get(f"ai.{name}", {}) or {}
        return dict(section)

    @classmethod
    def set_provider_config(
        cls,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        """Update a provider's config and persist (API key excluded from disk)."""
        name = (name or "").strip().lower()
        if not name:
            raise SettingsError("Provider name cannot be empty")

        if base_url is not None:
            ConfigManager.set(f"ai.{name}.base_url", base_url, persist=True)

        if model is not None:
            # Use primary_model for consistency with adapters
            ConfigManager.set(f"ai.{name}.primary_model", model, persist=True)

        if temperature is not None:
            ConfigManager.set(f"ai.{name}.temperature", float(temperature), persist=True)

        if max_tokens is not None:
            ConfigManager.set(f"ai.{name}.max_tokens", int(max_tokens), persist=True)

        # API key is special: it goes to .env, not to user_config.yaml
        if api_key is not None:
            cls._save_api_key_to_env(name, api_key)

        logger.info("settings_provider_config_saved", provider=name)

    # ------------------------------------------------------------------ #
    # API key handling
    # ------------------------------------------------------------------ #
    @classmethod
    def get_api_key(cls, name: str) -> Optional[str]:
        """Get API key from env (as configured for this provider)."""
        from app.settings.provider_catalog import ProviderCatalog
        env_key = ProviderCatalog.env_key_for(name)
        if not env_key:
            return None
        return os.getenv(env_key)

    @classmethod
    def _save_api_key_to_env(cls, name: str, api_key: str) -> None:
        """
        Save API key to the local .env file.

        - Never writes to user_config.yaml
        - Preserves other .env entries
        - Creates .env if missing
        """
        from app.settings.provider_catalog import ProviderCatalog
        env_key = ProviderCatalog.env_key_for(name)
        if not env_key:
            logger.warning("settings_no_env_key", provider=name)
            return

        env_path = ConfigManager._env_file
        env_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise SettingsError(f"Cannot read .env: {exc}") from exc

        # Replace or append
        found = False
        new_lines: list[str] = []
        for line in lines:
            if line.strip().startswith(f"{env_key}="):
                new_lines.append(f"{env_key}={api_key}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{env_key}={api_key}")

        try:
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except OSError as exc:
            raise SettingsError(f"Cannot write .env: {exc}") from exc

        # Update in-memory so tests / current session see it immediately
        os.environ[env_key] = api_key
        logger.info("settings_api_key_saved", provider=name, env_key=env_key)

    # ------------------------------------------------------------------ #
    # Snapshot for GUI
    # ------------------------------------------------------------------ #
    @classmethod
    def get_ai_settings(cls) -> Dict[str, Any]:
        """Return everything the settings dialog needs."""
        from app.settings.provider_catalog import ProviderCatalog

        active = cls.get_active_provider()
        cfg = cls.get_provider_config(active)
        return {
            "provider": active,
            "providers": ProviderCatalog.list_providers(),
            "display_names": ProviderCatalog.display_names(),
            "models": ProviderCatalog.models_for(active),
            "base_url": cfg.get("base_url", ProviderCatalog.default_base_url(active)),
            "model": cfg.get("primary_model") or (ProviderCatalog.models_for(active) or [""])[0],
            "temperature": float(cfg.get("temperature", 0.2)),
            "max_tokens": int(cfg.get("max_tokens", 8192)),
            "requires_api_key": ProviderCatalog.requires_api_key(active),
            "api_key_set": bool(cls.get_api_key(active)),
        }

    # ------------------------------------------------------------------ #
    # Reset / defaults
    # ------------------------------------------------------------------ #
    @classmethod
    def reset_to_defaults(cls) -> None:
        """Reset AI settings to catalog defaults."""
        from app.settings.provider_catalog import ProviderCatalog
        for key in ProviderCatalog.list_providers():
            info = ProviderCatalog.get(key)
            if info is None:
                continue
            ConfigManager.set(f"ai.{key}.base_url", info.base_url, persist=True)
        ConfigManager.set("ai.provider", "deepseek", persist=True)
        logger.info("settings_reset_to_defaults")