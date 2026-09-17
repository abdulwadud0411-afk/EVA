"""
Central configuration manager.

Sources, in increasing order of precedence:
    1. config/config.yaml        (defaults, safe to commit)
    2. config/user_config.yaml   (user overrides, safe to commit)
    3. .env                      (secrets + runtime overrides; never committed)
    4. OS environment variables  (highest priority)

Secrets are NEVER written to user_config.yaml.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import yaml
from dotenv import load_dotenv

from app.core.paths import (
    get_app_root,
    get_config_dir,
    get_data_dir,
    find_env_file,
    get_user_env_path,
)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or required values are missing."""


_Converter = Callable[[str], Any]


class ConfigManager:
    """Load and access EVA configuration."""

    _project_root: Path = get_app_root()

    _config_file: Path = get_config_dir() / "config.yaml"
    _user_config_file: Path = get_config_dir() / "user_config.yaml"
    _env_file: Path = get_app_root() / ".env"   # fallback; overridden in load()

    _config: Dict[str, Any] = {}
    _initialized: bool = False

    # ------------------------------------------------------------------ #
    # Path configuration (mainly for tests)
    # ------------------------------------------------------------------ #
    @classmethod
    def configure(
        cls,
        project_root: Optional[Path] = None,
        config_file: Optional[Path] = None,
        user_config_file: Optional[Path] = None,
        env_file: Optional[Path] = None,
    ) -> None:
        """Override file paths. Used by tests and embedded launches."""
        if project_root is not None:
            cls._project_root = Path(project_root)
        if config_file is not None:
            cls._config_file = Path(config_file)
        if user_config_file is not None:
            cls._user_config_file = Path(user_config_file)
        if env_file is not None:
            cls._env_file = Path(env_file)
        cls._initialized = False

    @classmethod
    def reset(cls) -> None:
        """Clear cached config (used by tests)."""
        cls._config = {}
        cls._initialized = False

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls) -> None:
        """Load config from all sources."""
        if cls._initialized:
            return

        # Find .env in the correct location for dev/frozen mode
        env_path = find_env_file()
        if env_path is not None:
            cls._env_file = env_path
            load_dotenv(env_path, override=False)

        if not cls._config_file.exists():
            raise FileNotFoundError(f"Default config not found: {cls._config_file}")
        with open(cls._config_file, "r", encoding="utf-8") as fh:
            merged: Dict[str, Any] = yaml.safe_load(fh) or {}

        if cls._user_config_file.exists():
            with open(cls._user_config_file, "r", encoding="utf-8") as fh:
                user_cfg = yaml.safe_load(fh) or {}
            if isinstance(user_cfg, dict):
                merged = cls._deep_merge(merged, user_cfg)

        merged = cls._apply_env_overrides(merged)

        cls._config = merged
        cls._initialized = True

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #
    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        """Get a value using dot-notation (e.g. 'ai.deepseek.primary_model')."""
        if not cls._initialized:
            cls.load()
        cursor: Any = cls._config
        for part in key_path.split("."):
            if isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                return default
        return cursor if cursor is not None else default

    @classmethod
    def set(cls, key_path: str, value: Any, persist: bool = True) -> None:
        """Set a value; optionally persist user-only overrides to disk."""
        if not cls._initialized:
            cls.load()

        parts = key_path.split(".")
        cursor = cls._config
        for part in parts[:-1]:
            if part not in cursor or not isinstance(cursor[part], dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value

        if persist:
            cls._persist_user_config()

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        if not cls._initialized:
            cls.load()
        return cls._config

    @classmethod
    def get_data_dir(cls) -> Path:
        """
        Return the absolute data directory, ensuring it exists.

        Uses paths.get_data_dir() as the base, so packaged .exe writes
        into %LOCALAPPDATA%/EVA/data automatically.
        """
        if not cls._initialized:
            cls.load()
        raw = cls.get("app.data_dir", "")
        # If user explicitly configured an absolute path, honor it.
        if raw:
            p = Path(raw)
            if p.is_absolute():
                p.mkdir(parents=True, exist_ok=True)
                return p
        # Default: use install-aware path helper
        return get_data_dir()
    @classmethod
    def get_project_root(cls) -> Path:
        return cls._project_root

    @classmethod
    def get_secret(cls, provider: str) -> Optional[str]:
        """
        Return an API key for a provider.

        Resolution order (Phase 20):
            1. Encrypted vault (data/security/vault.json)
            2. Environment variable (.env)
            3. Plaintext config (legacy fallback)

        Args:
            provider: provider key (e.g. "deepseek")
        """
        provider = (provider or "").strip().lower()
        if not provider:
            return None

        # 1. Vault
        try:
            from app.security.api_vault import APIVault
            key = APIVault.get(provider)
            if key:
                return key
        except Exception as exc:  # noqa: BLE001
            # Vault unavailable (cryptography missing) — fall through
            logger_debug = True  # noqa: F841

        # 2. Env var (via ProviderCatalog mapping)
        try:
            from app.settings.provider_catalog import ProviderCatalog
            env_key = ProviderCatalog.env_key_for(provider)
            if env_key:
                value = os.getenv(env_key)
                if value:
                    return value
        except Exception:  # noqa: BLE001
            pass

        # 3. Plaintext config (legacy)
        return cls.get(f"ai.{provider}.api_key", None)
    @classmethod
    def save_to_user_config(cls) -> None:
        """Public helper to persist current config (without secrets)."""
        cls._persist_user_config()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def _deep_merge(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _apply_env_overrides(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Map environment variables to config paths."""
        def _to_bool(v: str) -> bool:
            return v.strip().lower() in ("1", "true", "yes", "on")

        mapping: Dict[str, Tuple[Tuple[str, ...], Optional[_Converter]]] = {
            "EVA_DEBUG":          (("app", "debug"),                            _to_bool),
            "EVA_DATA_DIR":       (("app", "data_dir"),                         None),
            "DEEPSEEK_API_KEY":   (("ai", "deepseek", "api_key"),               None),
            "OPENAI_API_KEY":     (("ai", "openai", "api_key"),                 None),
            "ANTHROPIC_API_KEY":  (("ai", "anthropic", "api_key"),              None),
            "GOOGLE_API_KEY":     (("ai", "gemini", "api_key"),                 None),
            "ELEVENLABS_API_KEY": (("voice", "tts", "elevenlabs", "api_key"),   None),
        }

        for env_key, (path, converter) in mapping.items():
            raw = os.getenv(env_key)
            if raw is None:
                continue
            value: Any = converter(raw) if converter else raw
            target = config
            for p in path[:-1]:
                target = target.setdefault(p, {})
            target[path[-1]] = value

        return config

    @classmethod
    def _persist_user_config(cls) -> None:
        """Persist current merged config to user_config.yaml, stripping secrets."""
        def _strip_secrets(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: _strip_secrets(v)
                    for k, v in obj.items()
                    if k.lower() not in {"api_key", "token", "secret", "password"}
                }
            if isinstance(obj, list):
                return [_strip_secrets(v) for v in obj]
            return obj

        safe = _strip_secrets(cls._config)
        cls._user_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cls._user_config_file, "w", encoding="utf-8") as fh:
            yaml.safe_dump(safe, fh, default_flow_style=False, allow_unicode=True)