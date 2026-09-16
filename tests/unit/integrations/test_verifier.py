"""
Tests for app.tools.verifier.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools import verifier


# ---------------------------------------------------------------------- #
# file_exists
# ---------------------------------------------------------------------- #
def test_file_exists_true(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    r = verifier.file_exists(str(f))
    assert r["verified"] is True
    assert r["size"] == 5


def test_file_exists_false(tmp_path):
    r = verifier.file_exists(str(tmp_path / "missing.txt"))
    assert r["verified"] is False


def test_file_exists_min_size_fail(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("x")
    r = verifier.file_exists(str(f), min_size_bytes=100)
    assert r["verified"] is False


# ---------------------------------------------------------------------- #
# file_changed
# ---------------------------------------------------------------------- #
def test_file_changed_true(tmp_path):
    import time
    f = tmp_path / "a.txt"
    f.write_text("x")
    future_epoch = time.time() - 10
    r = verifier.file_changed(str(f), since_epoch=future_epoch)
    assert r["verified"] is True


def test_file_changed_false(tmp_path):
    import time
    f = tmp_path / "a.txt"
    f.write_text("x")
    far_future = time.time() + 3600
    r = verifier.file_changed(str(f), since_epoch=far_future)
    assert r["verified"] is False


def test_file_changed_missing(tmp_path):
    r = verifier.file_changed(str(tmp_path / "no.txt"), since_epoch=0)
    assert r["verified"] is False


# ---------------------------------------------------------------------- #
# process_running
# ---------------------------------------------------------------------- #
def test_process_running_empty_name():
    r = verifier.process_running("")
    assert r["verified"] is False


def test_process_running_found():
    fake = MagicMock()
    fake.stdout = "Image Name   PID\npython.exe   1234\n"
    with patch("subprocess.run", return_value=fake):
        r = verifier.process_running("python")
    assert r["verified"] is True


def test_process_running_not_found():
    fake = MagicMock()
    fake.stdout = "INFO: No tasks are running which match the specified criteria."
    with patch("subprocess.run", return_value=fake):
        r = verifier.process_running("ghost")
    assert r["verified"] is False


# ---------------------------------------------------------------------- #
# wait_for_process
# ---------------------------------------------------------------------- #
def test_wait_for_process_immediate():
    with patch.object(verifier, "process_running", return_value={"verified": True}):
        r = verifier.wait_for_process("x", timeout=1.0)
    assert r["verified"] is True


def test_wait_for_process_timeout():
    with patch.object(verifier, "process_running", return_value={"verified": False}), \
         patch("time.sleep", return_value=None), \
         patch("time.time", side_effect=[0, 0.5, 1.5]):
        r = verifier.wait_for_process("x", timeout=1.0)
    assert r["verified"] is False


# ---------------------------------------------------------------------- #
# HTTP
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_http_ok_true():
    fake = MagicMock()
    fake.status_code = 200
    with patch("httpx.AsyncClient.get", return_value=fake):
        r = await verifier.http_ok("http://example.com")
    assert r["verified"] is True


@pytest.mark.asyncio
async def test_http_ok_error():
    with patch("httpx.AsyncClient.get", side_effect=Exception("boom")):
        r = await verifier.http_ok("http://example.com")
    assert r["verified"] is False


def test_http_ok_sync_error():
    with patch("httpx.get", side_effect=Exception("boom")):
        r = verifier.http_ok_sync("http://example.com")
    assert r["verified"] is False


# ---------------------------------------------------------------------- #
# media_file_valid
# ---------------------------------------------------------------------- #
def test_media_file_valid_missing(tmp_path):
    r = verifier.media_file_valid(str(tmp_path / "no.mp4"))
    assert r["verified"] is False


def test_media_file_valid_no_ffprobe(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"fake")
    with patch("shutil.which", return_value=None):
        r = verifier.media_file_valid(str(f))
    assert r["verified"] is False
    assert "ffprobe" in r["reason"].lower()