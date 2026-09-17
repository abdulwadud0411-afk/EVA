"""Tests for Phase 22 LicenseManager + signature verification."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.core.config_manager import ConfigManager
from app.licensing.license_models import (
    LicenseData,
    LicensePayload,
    LicenseStatus,
    LicenseTier,
)
from app.licensing.license_checker import (
    generate_key_pair,
    sign_payload,
    verify_payload,
    b64_encode,
)
from app.licensing.license_manager import (
    LicenseError,
    LicenseManager,
    make_license_key,
)


# ---------------------------------------------------------------------- #
# Key fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture
def key_pair():
    """Generate a fresh RSA key pair per test (dev-only)."""
    priv, pub = generate_key_pair(bits=2048)
    return priv, pub


@pytest.fixture
def isolated_license(tmp_path, monkeypatch):
    """Isolate license paths inside a temp dir."""
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    ConfigManager.load()
    ConfigManager.configure(project_root=tmp_path)
    ConfigManager.set("app.data_dir", str(data_dir), persist=False)

    # Reset singleton so each test gets a fresh instance
    LicenseManager._instance = None
    LicenseManager._license = None
    LicenseManager._public_key_pem = None

    yield tmp_path

    LicenseManager._instance = None
    LicenseManager._license = None
    LicenseManager._public_key_pem = None


def _write_public_key(tmp_path, pub_pem: bytes):
    (tmp_path / "config" / "license_public_key.pem").write_bytes(pub_pem)


# ---------------------------------------------------------------------- #
# Signature verification (no manager)
# ---------------------------------------------------------------------- #
def test_verify_good_signature(key_pair):
    priv, pub = key_pair
    payload = b'{"customer_id":"c1"}'
    sig = sign_payload(payload, priv)
    assert verify_payload(payload, sig, pub) is True


def test_verify_bad_signature(key_pair):
    _, pub = key_pair
    payload = b'{"customer_id":"c1"}'
    bogus_sig = b"x" * 256
    assert verify_payload(payload, bogus_sig, pub) is False


def test_verify_tampered_payload(key_pair):
    priv, pub = key_pair
    payload = b'{"customer_id":"c1"}'
    sig = sign_payload(payload, priv)
    tampered = b'{"customer_id":"c2"}'
    assert verify_payload(tampered, sig, pub) is False


# ---------------------------------------------------------------------- #
# make_license_key + install
# ---------------------------------------------------------------------- #
def test_make_license_key_roundtrip(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    payload = LicensePayload(
        customer_id="cust-001",
        customer_name="Rizvi",
        tier=LicenseTier.PRO.value,
        features=["pro", "voice"],
    )
    key = make_license_key(payload, priv)

    mgr = LicenseManager()
    status = mgr.install(key)
    assert status == LicenseStatus.VALID
    info = mgr.info()
    assert info["customer_id"] == "cust-001"
    assert info["tier"] == "pro"
    assert "voice" in info["features"]


def test_install_malformed_key(isolated_license):
    LicenseManager._instance = None
    mgr = LicenseManager()
    with pytest.raises(LicenseError, match="Malformed"):
        mgr.install("no-dot-here")


def test_install_bad_signature(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    # Create a key with a bad signature
    payload = LicensePayload(customer_id="cust-002")
    payload_b64 = b64_encode(payload.to_json().encode("utf-8"))
    bad_sig_b64 = b64_encode(b"nope")
    bad_key = f"{payload_b64}.{bad_sig_b64}"

    mgr = LicenseManager()
    status = mgr.install(bad_key)
    assert status == LicenseStatus.BAD_SIGNATURE


def test_install_no_public_key(isolated_license, key_pair):
    priv, _ = key_pair
    # Note: don't write the public key file
    payload = LicensePayload(customer_id="cust-003")
    key = make_license_key(payload, priv)
    mgr = LicenseManager()
    with pytest.raises(LicenseError, match="public key"):
        mgr.install(key)


# ---------------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------------- #
def test_validate_missing(isolated_license):
    mgr = LicenseManager()
    assert mgr.validate() == LicenseStatus.MISSING
    assert mgr.is_valid() is False


def test_validate_expired(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    past = (datetime.now() - timedelta(days=5)).isoformat()
    payload = LicensePayload(
        customer_id="cust-exp", expires_at=past,
    )
    key = make_license_key(payload, priv)

    mgr = LicenseManager()
    mgr.install(key)
    assert mgr.validate() == LicenseStatus.EXPIRED


def test_validate_device_mismatch(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    payload = LicensePayload(
        customer_id="cust-bad-device",
        device_ids=["deadbeef" * 4],  # wrong device
    )
    key = make_license_key(payload, priv)

    mgr = LicenseManager()
    mgr.install(key)
    assert mgr.validate() == LicenseStatus.DEVICE_MISMATCH


def test_validate_persists_across_reload(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    payload = LicensePayload(customer_id="cust-persist")
    key = make_license_key(payload, priv)

    mgr1 = LicenseManager()
    mgr1.install(key)

    # Simulate restart
    LicenseManager._instance = None
    LicenseManager._license = None
    LicenseManager._public_key_pem = None

    mgr2 = LicenseManager()
    status = mgr2.validate()
    assert status == LicenseStatus.VALID
    assert mgr2.info()["customer_id"] == "cust-persist"


def test_revoke_removes_license(key_pair, isolated_license):
    priv, pub = key_pair
    _write_public_key(isolated_license, pub)

    payload = LicensePayload(customer_id="cust-revoke")
    key = make_license_key(payload, priv)

    mgr = LicenseManager()
    mgr.install(key)
    assert mgr.validate() == LicenseStatus.VALID

    mgr.revoke()
    assert mgr.validate() == LicenseStatus.MISSING


# ---------------------------------------------------------------------- #
# Models
# ---------------------------------------------------------------------- #
def test_payload_json_roundtrip():
    p = LicensePayload(
        customer_id="x", customer_name="Y", features=["a", "b"],
    )
    text = p.to_json()
    p2 = LicensePayload.from_json(text)
    assert p2.customer_id == "x"
    assert p2.features == ["a", "b"]


def test_payload_is_expired_no_date():
    p = LicensePayload(customer_id="x")
    assert p.is_expired() is False


def test_payload_is_expired_future():
    future = (datetime.now() + timedelta(days=30)).isoformat()
    p = LicensePayload(customer_id="x", expires_at=future)
    assert p.is_expired() is False


def test_payload_is_bound_to_unbound_always_true():
    p = LicensePayload(customer_id="x")
    assert p.is_bound_to("anything") is True


def test_payload_is_bound_to_match():
    p = LicensePayload(customer_id="x", device_ids=["abc"])
    assert p.is_bound_to("abc") is True
    assert p.is_bound_to("xyz") is False


def test_payload_has_feature():
    p = LicensePayload(customer_id="x", features=["pro"])
    assert p.has_feature("pro") is True
    assert p.has_feature("enterprise") is False