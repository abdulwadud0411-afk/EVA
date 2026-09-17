"""
Device fingerprint (Phase 22).

Generates a stable, privacy-friendly identifier for the local PC.

Sources (all optional — resilience over completeness):
    - hostname
    - MAC address (hashed, never stored raw)
    - CPU architecture
    - platform info

Public API:
    DeviceFingerprint.generate() -> "a1b2c3d4e5f6..." (32 hex chars)
"""
from __future__ import annotations

import hashlib
import platform
import socket
import uuid
from typing import Optional


class DeviceFingerprint:
    """Deterministic PC identifier."""

    _cache: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    @classmethod
    def generate(cls, force: bool = False) -> str:
        """Return a 32-char hex fingerprint (cached)."""
        if cls._cache and not force:
            return cls._cache
        cls._cache = cls._compute()
        return cls._cache

    @classmethod
    def reset(cls) -> None:
        """Clear cache (used by tests)."""
        cls._cache = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @classmethod
    def _compute(cls) -> str:
        parts = [
            cls._hostname(),
            cls._mac_hash(),
            cls._machine(),
            cls._system(),
        ]
        blob = "|".join(parts).encode("utf-8")
        digest = hashlib.sha256(blob).hexdigest()
        return digest[:32]

    @staticmethod
    def _hostname() -> str:
        try:
            return socket.gethostname() or ""
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _mac_hash() -> str:
        try:
            node = uuid.getnode()
        except Exception:  # noqa: BLE001
            return ""
        # Hash the MAC for privacy
        return hashlib.sha256(str(node).encode()).hexdigest()[:16]

    @staticmethod
    def _machine() -> str:
        try:
            return platform.machine() or ""
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _system() -> str:
        try:
            return platform.system() or ""
        except Exception:  # noqa: BLE001
            return ""

    # ------------------------------------------------------------------ #
    # Display helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def short(cls) -> str:
        """Return first 8 chars for display."""
        return cls.generate()[:8]

    @classmethod
    def describe(cls) -> dict:
        return {
            "fingerprint": cls.generate(),
            "short": cls.short(),
            "hostname": cls._hostname(),
            "machine": cls._machine(),
            "system": cls._system(),
        }