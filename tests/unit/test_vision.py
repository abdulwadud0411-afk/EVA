"""Tests for VisionClient (Phase 6)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.brain.vision import VisionClient, VisionError, _extract_json_block
from app.core.config_manager import ConfigManager


# ---------------------------------------------------------------------- #
# _extract_json_block
# ---------------------------------------------------------------------- #
def test_extract_json_from_fence():
    text = 'Here:\n```json\n{"x": 10, "y": 20}\n```\nDone.'
    result = _extract_json_block(text)
    assert result == {"x": 10, "y": 20}


def test_extract_json_from_braces():
    text = 'Response: {"found": false, "reason": "nope"} — end.'
    result = _extract_json_block(text)
    assert result == {"found": False, "reason": "nope"}


def test_extract_json_none_when_absent():
    assert _extract_json_block("No JSON here.") is None


def test_extract_json_invalid_returns_none():
    assert _extract_json_block('{ "broken": ') is None


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _make_image(tmp_path: Path) -> Path:
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fakeimagebytes")
    return p


def _mock_transport(payload: dict, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------- #
# VisionClient
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_analyze_image_success(tmp_path, monkeypatch):
    """Vision model returns text; client returns it."""
    img = _make_image(tmp_path)

    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)
    ConfigManager.set("ai.deepseek.vision_model", "deepseek-v4-flash-vision-exp", persist=False)

    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "choices": [{"message": {"role": "assistant", "content": "I see a browser window."}}],
    }

    client = VisionClient(transport=_mock_transport(payload))
    result = await client.analyze_image(img)
    assert "browser" in result["text"]
    assert result["model_used"] == "deepseek-v4-flash-vision-exp"


@pytest.mark.asyncio
async def test_analyze_image_missing_api_key(tmp_path, monkeypatch):
    img = _make_image(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    ConfigManager.load()
    # Ensure no key in config
    ConfigManager._config.setdefault("ai", {}).setdefault("deepseek", {}).pop("api_key", None)

    client = VisionClient(transport=_mock_transport({"choices": []}))
    with pytest.raises(VisionError, match="no API key"):
        await client.analyze_image(img)


@pytest.mark.asyncio
async def test_analyze_image_missing_file(tmp_path):
    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)

    client = VisionClient(transport=_mock_transport({"choices": []}))
    with pytest.raises(VisionError, match="Image not found"):
        await client.analyze_image(tmp_path / "nope.png")


@pytest.mark.asyncio
async def test_analyze_image_too_large(tmp_path):
    img = tmp_path / "big.png"
    img.write_bytes(b"x" * 6_000_000)

    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)

    client = VisionClient(transport=_mock_transport({"choices": []}))
    with pytest.raises(VisionError, match="Image too large"):
        await client.analyze_image(img)


@pytest.mark.asyncio
async def test_find_element_success(tmp_path):
    img = _make_image(tmp_path)

    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)
    ConfigManager.set("vision.min_confidence", 0.5, persist=False)

    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": '```json\n{"element": "Settings", "x": 1742, "y": 86, "confidence": 0.94}\n```',
            }
        }],
    }
    client = VisionClient(transport=_mock_transport(payload))
    result = await client.find_element(img, "Settings icon")
    assert result["found"] is True
    assert result["x"] == 1742
    assert result["y"] == 86
    assert result["confidence"] == 0.94


@pytest.mark.asyncio
async def test_find_element_low_confidence(tmp_path):
    img = _make_image(tmp_path)
    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)
    ConfigManager.set("vision.min_confidence", 0.9, persist=False)

    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": '{"element": "X", "x": 100, "y": 200, "confidence": 0.4}',
            }
        }],
    }
    client = VisionClient(transport=_mock_transport(payload))
    result = await client.find_element(img, "X")
    assert result["found"] is False
    assert "below threshold" in result["reason"]


@pytest.mark.asyncio
async def test_find_element_not_found(tmp_path):
    img = _make_image(tmp_path)
    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)

    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": '{"element": "Ghost", "found": false, "reason": "not visible"}',
            }
        }],
    }
    client = VisionClient(transport=_mock_transport(payload))
    result = await client.find_element(img, "Ghost")
    assert result["found"] is False
    assert result["x"] is None


@pytest.mark.asyncio
async def test_find_element_unparseable(tmp_path):
    img = _make_image(tmp_path)
    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "test-key", persist=False)

    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "choices": [{
            "message": {"role": "assistant", "content": "I cannot find that."},
        }],
    }
    client = VisionClient(transport=_mock_transport(payload))
    result = await client.find_element(img, "Something")
    assert result["found"] is False
    assert "no parseable JSON" in result["reason"]