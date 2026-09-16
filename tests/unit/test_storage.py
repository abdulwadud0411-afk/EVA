"""
Tests for Phase 11 storage layer.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.storage.manager import StorageManager, StorageError
from app.storage.policies import RetentionPolicy, ContentClass, PolicyError


# ---------------------------------------------------------------------- #
# Policies
# ---------------------------------------------------------------------- #
def test_policy_defaults():
    p = RetentionPolicy()
    assert p.retention_days("temp_screenshots") == 2
    assert p.retention_days("temp_recordings") == 3
    assert p.retention_days("cache") == 1


def test_policy_protected_categories():
    p = RetentionPolicy()
    assert p.is_protected("knowledge") is True
    assert p.is_protected("memory") is True
    assert p.is_protected("user_screenshots") is True
    assert p.is_protected("temp_screenshots") is False


def test_policy_unknown_category():
    p = RetentionPolicy()
    with pytest.raises(PolicyError):
        p.get("does_not_exist")


def test_policy_expiration():
    p = RetentionPolicy()
    temp = p.get("temp_screenshots")
    assert temp.is_expired(3.0) is True
    assert temp.is_expired(1.0) is False

    protected = p.get("knowledge")
    assert protected.is_expired(999.0) is False


# ---------------------------------------------------------------------- #
# Manager - save
# ---------------------------------------------------------------------- #
def test_save_creates_file():
    path = StorageManager.save(
        category="temp_screenshots",
        filename="test.png",
        content=b"fake png data",
    )
    assert path.exists()
    assert path.read_bytes() == b"fake png data"
    path.unlink()


def test_save_rejects_bad_filename():
    with pytest.raises(StorageError):
        StorageManager.save(
            category="temp_screenshots",
            filename="../evil.png",
            content=b"x",
        )


def test_save_rejects_unknown_category():
    with pytest.raises(StorageError):
        StorageManager.save(
            category="unknown_category",
            filename="x.txt",
            content=b"x",
        )


def test_save_text():
    path = StorageManager.save_text(
        category="knowledge",
        filename="note.txt",
        text="hello world",
    )
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello world"
    path.unlink()


# ---------------------------------------------------------------------- #
# Manager - folders
# ---------------------------------------------------------------------- #
def test_folder_routing():
    f1 = StorageManager.folder_for("temp_screenshots")
    f2 = StorageManager.folder_for("user_screenshots")
    f3 = StorageManager.folder_for("knowledge")
    assert f1.name == "temp"
    assert f2.name == "user"
    assert f3.name == "knowledge"
    assert f1 != f2


# ---------------------------------------------------------------------- #
# Manager - cleanup
# ---------------------------------------------------------------------- #
def test_cleanup_removes_expired():
    old_time = time.time() - 10 * 86400
    path = StorageManager.save(
        category="temp_screenshots",
        filename="old.png",
        content=b"old",
        timestamp=old_time,
    )
    assert path.exists()

    result = StorageManager.cleanup_category("temp_screenshots")
    assert result["removed"] >= 1
    assert not path.exists()


def test_cleanup_skips_protected():
    old_time = time.time() - 999 * 86400
    path = StorageManager.save(
        category="knowledge",
        filename="important.txt",
        content=b"never delete",
        timestamp=old_time,
    )
    result = StorageManager.cleanup_category("knowledge")
    assert result["skipped_protected"] is True
    assert result["removed"] == 0
    assert path.exists()
    path.unlink()


def test_cleanup_keeps_recent_files():
    path = StorageManager.save(
        category="temp_screenshots",
        filename="recent.png",
        content=b"fresh",
    )
    result = StorageManager.cleanup_category("temp_screenshots")
    assert path.exists()
    path.unlink()


# ---------------------------------------------------------------------- #
# Manager - stats
# ---------------------------------------------------------------------- #
def test_stats_returns_categories():
    StorageManager.save("temp_screenshots", "stat_test.bin", b"x" * 1000)
    stats = StorageManager.stats()
    assert "categories" in stats
    assert "temp_screenshots" in stats["categories"]
    assert stats["total_files"] >= 1
    (StorageManager.folder_for("temp_screenshots") / "stat_test.bin").unlink()


# ---------------------------------------------------------------------- #
# Protection
# ---------------------------------------------------------------------- #
def test_protection_register_and_check(tmp_path):
    from app.storage.protection import ProtectionManager
    ProtectionManager._protected_paths = set()
    ProtectionManager._loaded = True

    fake = tmp_path / "important.txt"
    fake.write_text("x")
    ProtectionManager.protect(fake)
    assert ProtectionManager.is_protected(fake) is True

    ProtectionManager.unprotect(fake)
    assert ProtectionManager.is_protected(fake) is False


def test_protection_global_categories():
    from app.storage.protection import ProtectionManager
    assert ProtectionManager.is_category_protected("knowledge") is True
    assert ProtectionManager.is_category_protected("temp_screenshots") is False


# ---------------------------------------------------------------------- #
# Deduplicator
# ---------------------------------------------------------------------- #
def test_dedup_hash_bytes():
    from app.storage.deduplicator import Deduplicator
    h1 = Deduplicator.hash_bytes(b"hello")
    h2 = Deduplicator.hash_bytes(b"hello")
    h3 = Deduplicator.hash_bytes(b"world")
    assert h1 == h2
    assert h1 != h3


def test_dedup_find_and_register(tmp_path):
    from app.storage.deduplicator import Deduplicator
    Deduplicator._index = {}
    Deduplicator._loaded = True

    content = b"some unique content"
    assert Deduplicator.find_duplicate(content) is None

    fake_path = tmp_path / "f.txt"
    Deduplicator.register(content, fake_path)
    assert Deduplicator.find_duplicate(content) == str(fake_path)


# ---------------------------------------------------------------------- #
# Tiered storage
# ---------------------------------------------------------------------- #
def test_tier_cold_unavailable(monkeypatch):
    from app.storage.tiers import TieredStorage
    monkeypatch.setattr(TieredStorage, "cold_root", staticmethod(lambda: None))
    assert TieredStorage.is_available() is False


def test_tier_archive_path(monkeypatch, tmp_path):
    from app.storage.tiers import TieredStorage
    monkeypatch.setattr(TieredStorage, "cold_root", staticmethod(lambda: tmp_path / "cold"))
    monkeypatch.setattr(TieredStorage, "hot_root", staticmethod(lambda: tmp_path))
    src = tmp_path / "knowledge" / "a.txt"
    dst = TieredStorage.archive_path(src)
    assert dst is not None
    assert "cold" in str(dst)


# ---------------------------------------------------------------------- #
# Quota
# ---------------------------------------------------------------------- #
def test_quota_no_limit():
    from app.storage.quota import QuotaGuard
    folder = StorageManager.folder_for("temp_screenshots")
    result = QuotaGuard.check_write_allowed("temp_screenshots", 1000, folder)
    assert result["allowed"] is True


# ---------------------------------------------------------------------- #
# Compactor
# ---------------------------------------------------------------------- #
def test_compactor_log_rotation_disabled():
    from app.storage.compactor import Compactor
    ConfigManager.load()
    ConfigManager.set("storage.maintenance.rotate_logs_days", 0, persist=False)
    result = Compactor.rotate_logs()
    assert result.get("skipped") is True


# ---------------------------------------------------------------------- #
# Exporter
# ---------------------------------------------------------------------- #
def test_exporter_creates_zip(tmp_path):
    from app.storage.exporter import Exporter
    zip_path = Exporter.export_to_zip(tmp_path)
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"


def test_exporter_stats():
    from app.storage.exporter import Exporter
    stats = Exporter.export_stats()
    assert "categories" in stats