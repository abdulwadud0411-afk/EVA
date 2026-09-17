"""
API Vault (Phase 20).

Encrypts API keys at rest using Fernet (symmetric AES-128).
Secrets are stored in `data/security/vault.json` (encrypted),
not in `.env` (plaintext).

On first use, a random key is generated at `data/security/vault.key`.

Public API:
    from app.security.api_vault import APIVault
    APIVault.set("deepseek", "sk-...")
    key = APIVault.get("deepseek")
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    _FERNET = True
except Exception:  # noqa: BLE001
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _FERNET = False


class VaultError(Exception):
    """Raised when a vault operation fails."""


class APIVault:
    """Fernet-encrypted store for API keys."""

    _cache: Optional[Dict[str, str]] = None
    _fernet: Optional[Any] = None

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    @classmethod
    def _security_dir(cls) -> Path:
        d = ConfigManager.get_data_dir() / "security"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def _vault_path(cls) -> Path:
        return cls._security_dir() / "vault.json"

    @classmethod
    def _key_path(cls) -> Path:
        return cls._security_dir() / "vault.key"

    # ------------------------------------------------------------------ #
    # Crypto
    # ------------------------------------------------------------------ #
    @classmethod
    def _get_fernet(cls):
        if not _FERNET:
            raise VaultError(
                "cryptography not installed. Run: pip install cryptography"
            )
        if cls._fernet is not None:
            return cls._fernet

        key_path = cls._key_path()
        if key_path.exists():
            try:
                key = key_path.read_bytes().strip()
            except OSError as exc:
                raise VaultError(f"Cannot read vault key: {exc}") from exc
        else:
            key = Fernet.generate_key()
            try:
                key_path.write_bytes(key)
                # Restrict permissions on POSIX; on Windows this is a hint
                try:
                    os.chmod(key_path, 0o600)
                except OSError:
                    pass
            except OSError as exc:
                raise VaultError(f"Cannot write vault key: {exc}") from exc
            logger.info("vault_key_created", path=str(key_path))

        cls._fernet = Fernet(key)
        return cls._fernet

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    @classmethod
    def _load(cls) -> Dict[str, str]:
        if cls._cache is not None:
            return cls._cache

        path = cls._vault_path()
        if not path.exists():
            cls._cache = {}
            return cls._cache

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("vault_load_failed", error=str(exc))
            cls._cache = {}
            return cls._cache

        fernet = cls._get_fernet()
        plain: Dict[str, str] = {}
        for provider, token in (raw or {}).items():
            try:
                enc = token.encode("ascii") if isinstance(token, str) else token
                plain[provider] = fernet.decrypt(enc).decode("utf-8")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "vault_decrypt_failed", provider=provider, error=str(exc),
                )
        cls._cache = plain
        return cls._cache

    @classmethod
    def _save(cls) -> None:
        if cls._cache is None:
            return
        fernet = cls._get_fernet()
        encrypted: Dict[str, str] = {}
        for provider, value in cls._cache.items():
            token = fernet.encrypt(value.encode("utf-8"))
            encrypted[provider] = token.decode("ascii")

        path = cls._vault_path()
        try:
            path.write_text(
                json.dumps(encrypted, indent=2),
                encoding="utf-8",
            )
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError as exc:
            raise VaultError(f"Cannot write vault: {exc}") from exc

    @classmethod
    def reload(cls) -> None:
        """Drop the in-memory cache (used by tests)."""
        cls._cache = None
        cls._fernet = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @classmethod
    def set(cls, provider: str, api_key: str) -> None:
        if not provider:
            raise VaultError("provider name cannot be empty")
        if cls._cache is None:
            cls._load()
        cls._cache[provider] = str(api_key)
        cls._save()
        logger.info("vault_set", provider=provider)

    @classmethod
    def get(cls, provider: str) -> Optional[str]:
        if cls._cache is None:
            cls._load()
        return cls._cache.get(provider)

    @classmethod
    def delete(cls, provider: str) -> bool:
        if cls._cache is None:
            cls._load()
        if provider in cls._cache:
            del cls._cache[provider]
            cls._save()
            return True
        return False

    @classmethod
    def list_providers(cls) -> list:
        if cls._cache is None:
            cls._load()
        return sorted(cls._cache.keys())

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        return {
            "available": _FERNET,
            "vault_path": str(cls._vault_path()),
            "key_path": str(cls._key_path()),
            "providers": cls.list_providers(),
        }