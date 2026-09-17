"""
License manager (Phase 22).

Loads, saves, verifies, and activates licenses.

Storage:
    data/security/license.json   — currently installed license
    config/license_public_key.pem — vendor's public key

Public API:
    lm = LicenseManager()
    status = lm.validate()                       # LicenseStatus
    lm.install(license_key_string)               # activate
    lm.load_from_disk()                          # read saved license
    info = lm.info()                             # summary dict
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.licensing.device_fingerprint import DeviceFingerprint
from app.licensing.license_checker import (
    b64_decode,
    b64_encode,
    verify_payload,
    LicenseCheckError,
)
from app.licensing.license_models import (
    LicenseData,
    LicensePayload,
    LicenseStatus,
)

logger = get_logger(__name__)


class LicenseError(Exception):
    """Raised when a license operation fails."""


class LicenseManager:
    """Singleton-style license loader/validator."""

    _instance: Optional["LicenseManager"] = None
    _license: Optional[LicenseData] = None
    _public_key_pem: Optional[bytes] = None

    def __new__(cls, *_args, **_kwargs) -> "LicenseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    @staticmethod
    def _license_path() -> Path:
        d = ConfigManager.get_data_dir() / "security"
        d.mkdir(parents=True, exist_ok=True)
        return d / "license.json"

    @staticmethod
    def _public_key_path() -> Path:
        return ConfigManager.get_project_root() / "config" / "license_public_key.pem"

    # ------------------------------------------------------------------ #
    # Public key
    # ------------------------------------------------------------------ #
    def _load_public_key(self) -> Optional[bytes]:
        if self._public_key_pem is not None:
            return self._public_key_pem

        path = self._public_key_path()
        if not path.exists():
            logger.info("license_public_key_missing", path=str(path))
            return None

        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.warning("license_public_key_read_failed", error=str(exc))
            return None

        # Reject placeholder files
        if b"REPLACE" in data or len(data) < 100:
            logger.info("license_public_key_placeholder")
            return None

        self._public_key_pem = data
        return data

    def reload_public_key(self) -> None:
        self._public_key_pem = None

    # ------------------------------------------------------------------ #
    # Load / Save
    # ------------------------------------------------------------------ #
    def load_from_disk(self) -> Optional[LicenseData]:
        path = self._license_path()
        if not path.exists():
            self._license = None
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("license_load_failed", error=str(exc))
            self._license = None
            return None

        try:
            self._license = LicenseData.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("license_parse_failed", error=str(exc))
            self._license = None
        return self._license

    def save_to_disk(self) -> None:
        if self._license is None:
            return
        path = self._license_path()
        try:
            path.write_text(
                json.dumps(self._license.to_dict(), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise LicenseError(f"Cannot write license: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Install from key string
    # ------------------------------------------------------------------ #
    def install(self, license_key: str) -> LicenseStatus:
        """
        Accept a compact license key string:
            base64(payload_json).base64(signature)
        """
        license_key = (license_key or "").strip()
        if not license_key or "." not in license_key:
            raise LicenseError("Malformed license key (missing separator).")

        payload_b64, _, sig_b64 = license_key.partition(".")
        try:
            payload_bytes = b64_decode(payload_b64)
            signature_bytes = b64_decode(sig_b64)
        except Exception as exc:  # noqa: BLE001
            raise LicenseError(f"License key is not valid base64: {exc}") from exc

        public_pem = self._load_public_key()
        if public_pem is None:
            raise LicenseError(
                "No public key installed. Add config/license_public_key.pem."
            )

        try:
            ok = verify_payload(payload_bytes, signature_bytes, public_pem)
        except LicenseCheckError as exc:
            raise LicenseError(str(exc)) from exc

        if not ok:
            return LicenseStatus.BAD_SIGNATURE

        try:
            payload = LicensePayload.from_json(payload_bytes.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise LicenseError(f"Cannot parse payload: {exc}") from exc

        self._license = LicenseData(payload=payload, signature=sig_b64)
        self.save_to_disk()
        logger.info("license_installed", customer=payload.customer_id)
        return self.validate()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def validate(self) -> LicenseStatus:
        if self._license is None:
            self.load_from_disk()
        if self._license is None:
            return LicenseStatus.MISSING

        payload = self._license.payload

        # 1. Expiry
        if payload.is_expired():
            return LicenseStatus.EXPIRED

        # 2. Device binding
        device_id = DeviceFingerprint.generate()
        if not payload.is_bound_to(device_id):
            return LicenseStatus.DEVICE_MISMATCH

        # 3. Signature re-check
        public_pem = self._load_public_key()
        if public_pem is None:
            # No key installed — accept as "trial" (dev-friendly)
            return LicenseStatus.VALID

        try:
            signature_bytes = b64_decode(self._license.signature)
            payload_bytes = payload.to_json().encode("utf-8")
            ok = verify_payload(payload_bytes, signature_bytes, public_pem)
        except Exception as exc:  # noqa: BLE001
            logger.warning("license_reverify_failed", error=str(exc))
            return LicenseStatus.BAD_SIGNATURE

        return LicenseStatus.VALID if ok else LicenseStatus.BAD_SIGNATURE

    def is_valid(self) -> bool:
        return self.validate() == LicenseStatus.VALID

    # ------------------------------------------------------------------ #
    # Info
    # ------------------------------------------------------------------ #
    def info(self) -> Dict[str, Any]:
        if self._license is None:
            self.load_from_disk()

        device = DeviceFingerprint.describe()
        if self._license is None:
            return {
                "status": LicenseStatus.MISSING.value,
                "customer_id": None,
                "tier": None,
                "expires_at": None,
                "device_id": device["short"],
            }

        p = self._license.payload
        return {
            "status": self.validate().value,
            "customer_id": p.customer_id,
            "customer_name": p.customer_name,
            "tier": p.tier,
            "issued_at": p.issued_at,
            "expires_at": p.expires_at or "(never)",
            "features": list(p.features),
            "device_id": device["short"],
            "bound_devices": list(p.device_ids),
        }

    def revoke(self) -> None:
        """Delete the local license file."""
        path = self._license_path()
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("license_revoke_failed", error=str(exc))
        self._license = None


# ---------------------------------------------------------------------- #
# Convenience module-level helpers (used by main.py)
# ---------------------------------------------------------------------- #
def get_manager() -> LicenseManager:
    return LicenseManager()


def make_license_key(
    payload: LicensePayload,
    private_key_pem: bytes,
) -> str:
    """
    Dev helper: create a license key string from a payload.

    Requires the vendor's private key.
    """
    from app.licensing.license_checker import sign_payload
    payload_bytes = payload.to_json().encode("utf-8")
    signature = sign_payload(payload_bytes, private_key_pem)
    return f"{b64_encode(payload_bytes)}.{b64_encode(signature)}"