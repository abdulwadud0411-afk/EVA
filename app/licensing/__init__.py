"""
EVA Licensing module (Phase 22).

Offline license verification:
    - Ed25519/RSA signed license keys
    - Device fingerprint binding
    - Expiry + feature flags
    - No phone-home required

Public API:
    from app.licensing import (
        LicenseManager, LicenseStatus, LicenseData,
        DeviceFingerprint, verify_payload,
    )
"""
from app.licensing.license_models import (  # noqa: F401
    LicenseData,
    LicensePayload,
    LicenseStatus,
    LicenseTier,
)
from app.licensing.device_fingerprint import DeviceFingerprint  # noqa: F401
from app.licensing.license_checker import (  # noqa: F401
    verify_payload,
    sign_payload,
    generate_key_pair,
    LicenseCheckError,
)
from app.licensing.license_manager import (  # noqa: F401
    LicenseManager,
    LicenseError,
)

__all__ = [
    "LicenseData",
    "LicensePayload",
    "LicenseStatus",
    "LicenseTier",
    "DeviceFingerprint",
    "verify_payload",
    "sign_payload",
    "generate_key_pair",
    "LicenseCheckError",
    "LicenseManager",
    "LicenseError",
]