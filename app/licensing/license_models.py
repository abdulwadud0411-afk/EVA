"""
License data models (Phase 22).

All dataclasses are JSON-friendly so a license can be serialized
into a compact key string.

Public API:
    payload = LicensePayload(customer_id="...", ...)
    data = LicenseData(payload=payload, signature="...")
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LicenseTier(str, Enum):
    TRIAL = "trial"
    STANDARD = "standard"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LicenseStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    EXPIRED = "expired"
    DEVICE_MISMATCH = "device_mismatch"
    REVOKED = "revoked"
    UNKNOWN_KEY = "unknown_key"


@dataclass
class LicensePayload:
    """The actual signed content of a license."""
    customer_id: str
    customer_name: str = ""
    tier: str = LicenseTier.STANDARD.value
    issued_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""                    # ISO-8601 or "" for never
    device_ids: List[str] = field(default_factory=list)  # bound fingerprints
    features: List[str] = field(default_factory=list)
    notes: str = ""

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        """Deterministic JSON — sorted keys, no whitespace."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicensePayload":
        return cls(
            customer_id=str(data.get("customer_id", "")),
            customer_name=str(data.get("customer_name", "")),
            tier=str(data.get("tier", LicenseTier.STANDARD.value)),
            issued_at=str(data.get("issued_at", "")),
            expires_at=str(data.get("expires_at", "")),
            device_ids=list(data.get("device_ids") or []),
            features=list(data.get("features") or []),
            notes=str(data.get("notes", "")),
        )

    @classmethod
    def from_json(cls, text: str) -> "LicensePayload":
        return cls.from_dict(json.loads(text))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        return (now or datetime.now()) > exp

    def is_bound_to(self, device_id: str) -> bool:
        if not self.device_ids:
            return True    # unbound license
        return device_id in self.device_ids


@dataclass
class LicenseData:
    """Payload + cryptographic signature."""
    payload: LicensePayload
    signature: str = ""     # base64

    def to_dict(self) -> Dict[str, Any]:
        return {"payload": self.payload.to_dict(), "signature": self.signature}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LicenseData":
        payload = LicensePayload.from_dict(data.get("payload") or {})
        return cls(payload=payload, signature=str(data.get("signature", "")))