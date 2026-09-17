"""
License signature checker (Phase 22).

Uses cryptography's RSA-PSS verification. Payloads are signed by the
vendor with a private key; the public key ships inside EVA.

Public API:
    ok = verify_payload(payload_bytes, signature_bytes, public_key_pem)
    signature = sign_payload(payload_bytes, private_key_pem)   # dev tool
    priv_pem, pub_pem = generate_key_pair()                    # dev tool
"""
from __future__ import annotations

import base64
from typing import Tuple

from app.core.logger import get_logger

logger = get_logger(__name__)


try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.exceptions import InvalidSignature
    _CRYPTO = True
except Exception:  # noqa: BLE001
    _CRYPTO = False
    hashes = None  # type: ignore
    serialization = None  # type: ignore
    padding = None  # type: ignore
    rsa = None  # type: ignore
    InvalidSignature = Exception  # type: ignore


class LicenseCheckError(Exception):
    """Raised when cryptography cannot be used."""


# ---------------------------------------------------------------------- #
# Verify
# ---------------------------------------------------------------------- #
def verify_payload(
    payload_bytes: bytes,
    signature_bytes: bytes,
    public_key_pem: bytes,
) -> bool:
    """Return True if the signature matches the payload."""
    if not _CRYPTO:
        raise LicenseCheckError(
            "cryptography is required for license verification. "
            "Run: pip install cryptography"
        )
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
    except Exception as exc:  # noqa: BLE001
        logger.warning("license_public_key_load_failed", error=str(exc))
        return False

    try:
        public_key.verify(
            signature_bytes,
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("license_verify_failed", error=str(exc))
        return False


# ---------------------------------------------------------------------- #
# Sign (dev / vendor side)
# ---------------------------------------------------------------------- #
def sign_payload(payload_bytes: bytes, private_key_pem: bytes) -> bytes:
    """Sign payload with the vendor's private key (RSA-PSS)."""
    if not _CRYPTO:
        raise LicenseCheckError("cryptography is required to sign licenses.")
    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None,
    )
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return signature


# ---------------------------------------------------------------------- #
# Key generation (dev only)
# ---------------------------------------------------------------------- #
def generate_key_pair(bits: int = 2048) -> Tuple[bytes, bytes]:
    """
    Generate a new RSA key pair.

    Returns:
        (private_key_pem, public_key_pem)
    """
    if not _CRYPTO:
        raise LicenseCheckError("cryptography is required for key generation.")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


# ---------------------------------------------------------------------- #
# Base64 helpers (used by LicenseManager)
# ---------------------------------------------------------------------- #
def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64_decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))