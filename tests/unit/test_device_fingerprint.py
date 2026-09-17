"""Tests for Phase 22 DeviceFingerprint."""
from __future__ import annotations

import re

import pytest

from app.licensing.device_fingerprint import DeviceFingerprint


@pytest.fixture(autouse=True)
def reset_fp():
    DeviceFingerprint.reset()
    yield
    DeviceFingerprint.reset()


def test_fingerprint_is_hex_string():
    fp = DeviceFingerprint.generate()
    assert isinstance(fp, str)
    assert len(fp) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", fp)


def test_fingerprint_is_stable():
    fp1 = DeviceFingerprint.generate()
    fp2 = DeviceFingerprint.generate()
    assert fp1 == fp2


def test_fingerprint_cached_until_reset():
    fp1 = DeviceFingerprint.generate()
    DeviceFingerprint.reset()
    fp2 = DeviceFingerprint.generate()
    # Same machine — should match again
    assert fp1 == fp2


def test_fingerprint_force_regenerates():
    fp1 = DeviceFingerprint.generate()
    fp2 = DeviceFingerprint.generate(force=True)
    assert fp1 == fp2    # deterministic


def test_short_returns_first_8():
    short = DeviceFingerprint.short()
    assert len(short) == 8
    assert re.fullmatch(r"[0-9a-f]{8}", short)
    assert DeviceFingerprint.generate().startswith(short)


def test_describe_shape():
    info = DeviceFingerprint.describe()
    assert "fingerprint" in info
    assert "short" in info
    assert "hostname" in info
    assert "machine" in info
    assert "system" in info
    assert len(info["fingerprint"]) == 32


def test_individual_parts_dont_crash():
    assert isinstance(DeviceFingerprint._hostname(), str)
    assert isinstance(DeviceFingerprint._mac_hash(), str)
    assert isinstance(DeviceFingerprint._machine(), str)
    assert isinstance(DeviceFingerprint._system(), str)