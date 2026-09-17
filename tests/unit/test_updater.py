"""Tests for Phase 22 Batch 3 — updater."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.core.config_manager import ConfigManager
from app.updater.downloader import DownloadError, UpdateDownloader
from app.updater.manifest import (
    ManifestError,
    UpdateManifest,
    compare_versions,
    fetch_manifest,
    is_newer,
    load_local_manifest,
    parse_version,
    save_local_manifest,
)
from app.updater.updater import (
    UpdateStatus,
    check_for_updates,
    get_current_version,
    run_update,
)


# ---------------------------------------------------------------------- #
# Version parsing + comparison
# ---------------------------------------------------------------------- #
def test_parse_version_stable():
    assert parse_version("0.22.0") == (0, 22, 0, "")


def test_parse_version_with_suffix():
    assert parse_version("1.2.3-beta.1") == (1, 2, 3, "-beta.1")


def test_parse_version_invalid():
    with pytest.raises(ManifestError):
        parse_version("abc")


def test_parse_version_empty():
    with pytest.raises(ManifestError):
        parse_version("")


def test_compare_equal():
    assert compare_versions("1.2.3", "1.2.3") == 0


def test_compare_less():
    assert compare_versions("1.2.3", "1.2.4") == -1
    assert compare_versions("0.22.0", "0.23.0") == -1
    assert compare_versions("1.0.0", "2.0.0") == -1


def test_compare_greater():
    assert compare_versions("1.2.4", "1.2.3") == 1
    assert compare_versions("2.0.0", "1.9.9") == 1


def test_stable_beats_prerelease():
    assert compare_versions("1.0.0", "1.0.0-beta") == 1
    assert compare_versions("1.0.0-beta", "1.0.0") == -1


def test_is_newer():
    assert is_newer("0.22.0", "0.23.0") is True
    assert is_newer("0.22.0", "0.22.0") is False
    assert is_newer("0.22.0", "0.21.0") is False


# ---------------------------------------------------------------------- #
# Manifest dataclass
# ---------------------------------------------------------------------- #
def test_manifest_from_dict():
    m = UpdateManifest.from_dict({
        "version": "0.23.0",
        "channel": "stable",
        "download_url": "https://x/y.exe",
        "sha256": "ABC123",
    })
    assert m.version == "0.23.0"
    assert m.sha256 == "abc123"      # lowercased
    assert m.download_url == "https://x/y.exe"


def test_manifest_missing_version():
    with pytest.raises(ManifestError, match="version"):
        UpdateManifest.from_dict({})


def test_manifest_invalid_version():
    with pytest.raises(ManifestError, match="Invalid version"):
        UpdateManifest.from_dict({"version": "abc"})


def test_manifest_to_dict_roundtrip():
    m = UpdateManifest.from_dict({"version": "1.2.3"})
    d = m.to_dict()
    m2 = UpdateManifest.from_dict(d)
    assert m2.version == "1.2.3"


def test_manifest_compatible_no_min():
    m = UpdateManifest.from_dict({"version": "1.0.0"})
    assert m.is_compatible_with("0.5.0") is True


def test_manifest_compatible_min_satisfied():
    m = UpdateManifest.from_dict({"version": "1.0.0", "min_supported_version": "0.9.0"})
    assert m.is_compatible_with("0.9.0") is True
    assert m.is_compatible_with("1.0.0") is True


def test_manifest_incompatible_too_old():
    m = UpdateManifest.from_dict({"version": "1.0.0", "min_supported_version": "0.9.0"})
    assert m.is_compatible_with("0.8.0") is False


# ---------------------------------------------------------------------- #
# fetch_manifest (mock transport)
# ---------------------------------------------------------------------- #
def test_fetch_manifest_success():
    payload = {
        "version": "0.23.0",
        "download_url": "https://x/y.exe",
        "sha256": "ABC",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    m = fetch_manifest("https://fake/manifest.json", transport=transport)
    assert m.version == "0.23.0"
    assert m.sha256 == "abc"


def test_fetch_manifest_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    with pytest.raises(ManifestError):
        fetch_manifest("https://fake/manifest.json", transport=transport)


def test_fetch_manifest_bad_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    transport = httpx.MockTransport(handler)
    with pytest.raises(ManifestError):
        fetch_manifest("https://fake/manifest.json", transport=transport)


def test_fetch_manifest_empty_url():
    with pytest.raises(ManifestError):
        fetch_manifest("")


# ---------------------------------------------------------------------- #
# Local manifest cache
# ---------------------------------------------------------------------- #
def test_local_manifest_roundtrip(tmp_path, monkeypatch):
    import app.updater.manifest as mf
    monkeypatch.setattr(mf, "_local_manifest_path", lambda: tmp_path / "m.json")

    m = UpdateManifest.from_dict({"version": "1.0.0", "channel": "beta"})
    save_local_manifest(m)
    loaded = load_local_manifest()
    assert loaded is not None
    assert loaded.version == "1.0.0"
    assert loaded.channel == "beta"


def test_local_manifest_load_missing(tmp_path, monkeypatch):
    import app.updater.manifest as mf
    monkeypatch.setattr(mf, "_local_manifest_path", lambda: tmp_path / "nope.json")
    assert load_local_manifest() is None


# ---------------------------------------------------------------------- #
# Downloader (mock transport)
# ---------------------------------------------------------------------- #
def test_downloader_success(tmp_path):
    content = b"EVA-installer-bytes" * 100
    expected_sha = hashlib.sha256(content).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=content,
            headers={"content-length": str(len(content))},
        )

    transport = httpx.MockTransport(handler)
    dl = UpdateDownloader(timeout=10.0)
    dest = tmp_path / "EVA_Setup.exe"

    progress = []
    result = dl.download(
        "https://fake/EVA_Setup.exe",
        dest,
        expected_sha256=expected_sha,
        on_progress=lambda d, t: progress.append((d, t)),
        transport=transport,
    )
    assert dest.exists()
    assert dest.read_bytes() == content
    assert result.verified is True
    assert result.size_bytes == len(content)
    assert len(progress) >= 1


def test_downloader_sha_mismatch(tmp_path):
    content = b"some-content"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    dl = UpdateDownloader(timeout=10.0)
    dest = tmp_path / "x.exe"

    with pytest.raises(DownloadError, match="SHA-256 mismatch"):
        dl.download(
            "https://fake/x.exe",
            dest,
            expected_sha256="deadbeef",
            transport=transport,
        )
    # No final file, no .part file
    assert not dest.exists()
    assert not (dest.with_suffix(".exe.part")).exists()


def test_downloader_no_sha_ok(tmp_path):
    content = b"anything"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    dl = UpdateDownloader(timeout=10.0)
    dest = tmp_path / "y.exe"
    result = dl.download(
        "https://fake/y.exe",
        dest,
        expected_sha256="",   # no check
        transport=transport,
    )
    assert result.verified is True
    assert dest.exists()


def test_downloader_http_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    dl = UpdateDownloader(timeout=5.0)
    with pytest.raises(DownloadError):
        dl.download("https://fake/x.exe", tmp_path / "x.exe", transport=transport)


def test_downloader_format_size():
    assert UpdateDownloader.format_size(500) == "500.0 B"
    assert UpdateDownloader.format_size(2048) == "2.0 KB"
    assert UpdateDownloader.format_size(1024 * 1024) == "1.0 MB"
    assert UpdateDownloader.format_size(1024 ** 3 * 5) == "5.0 GB"


# ---------------------------------------------------------------------- #
# Updater (integration of the above)
# ---------------------------------------------------------------------- #
def test_get_current_version():
    v = get_current_version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_check_updates_disabled():
    ConfigManager.load()
    ConfigManager.set("updater.enabled", False, persist=False)
    result = check_for_updates()
    assert result.status == UpdateStatus.DISABLED


def test_check_updates_offline_no_url():
    ConfigManager.load()
    ConfigManager.set("updater.enabled", True, persist=False)
    ConfigManager.set("updater.manifest_url", "", persist=False)
    result = check_for_updates()
    assert result.status == UpdateStatus.UP_TO_DATE


def test_check_updates_new_version_available():
    ConfigManager.load()
    ConfigManager.set("updater.enabled", True, persist=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "version": "99.0.0",
            "download_url": "https://fake/EVA.exe",
            "sha256": "abc",
        })

    transport = httpx.MockTransport(handler)
    result = check_for_updates(
        manifest_url="https://fake/manifest.json",
        transport=transport,
    )
    assert result.status == UpdateStatus.UPDATE_AVAILABLE
    assert result.latest_version == "99.0.0"


def test_check_updates_already_latest():
    ConfigManager.load()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "0.0.1"})

    transport = httpx.MockTransport(handler)
    result = check_for_updates(
        manifest_url="https://fake/manifest.json",
        transport=transport,
    )
    assert result.status == UpdateStatus.UP_TO_DATE


def test_check_updates_fetch_error():
    ConfigManager.load()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    result = check_for_updates(
        manifest_url="https://fake/manifest.json",
        transport=transport,
    )
    assert result.status == UpdateStatus.FAILED


def test_run_update_without_manifest():
    ConfigManager.load()
    result = run_update(manifest=None)
    # Depends on cached manifest — but shouldn't crash
    assert result.status in (UpdateStatus.FAILED, UpdateStatus.DOWNLOADED)


def test_run_update_manifest_no_url():
    m = UpdateManifest.from_dict({"version": "9.9.9"})
    result = run_update(manifest=m)
    assert result.status == UpdateStatus.FAILED
    assert "download_url" in result.message.lower() or result.error