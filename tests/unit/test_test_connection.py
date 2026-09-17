"""Tests for Phase 17 connection check."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config_manager import ConfigManager
from app.settings.test_connection import ConnectionResult, check_provider


@pytest.mark.asyncio
async def test_unknown_provider():
    result = await check_provider("does_not_exist")
    assert result.success is False
    assert "unknown" in result.message.lower()


@pytest.mark.asyncio
async def test_deepseek_missing_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    ConfigManager.load()
    ConfigManager._config.setdefault("ai", {}).setdefault("deepseek", {}).pop("api_key", None)
    result = await check_provider("deepseek", api_key=None)
    assert result.success is False
    assert "api key" in result.message.lower()


@pytest.mark.asyncio
async def test_ollama_success(monkeypatch):
    fake = MagicMock()
    fake.status_code = 200
    fake.json = lambda: {"models": [{"name": "qwen2.5:3b"}]}
    with patch("httpx.AsyncClient.get", return_value=fake):
        result = await check_provider("ollama")
    assert result.success is True
    assert "ollama" in result.message.lower()


@pytest.mark.asyncio
async def test_ollama_unreachable():
    with patch("httpx.AsyncClient.get", side_effect=Exception("offline")):
        result = await check_provider("ollama")
    assert result.success is False


@pytest.mark.asyncio
async def test_deepseek_401(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-bad")
    fake = MagicMock()
    fake.status_code = 401
    fake.text = "invalid"
    with patch("httpx.AsyncClient.post", return_value=fake):
        result = await check_provider("deepseek", api_key="sk-bad")
    assert result.success is False
    assert "401" in result.message or "invalid" in result.message.lower()


@pytest.mark.asyncio
async def test_deepseek_success(monkeypatch):
    fake = MagicMock()
    fake.status_code = 200
    fake.json = lambda: {"choices": [{"message": {"content": "pong"}}]}
    with patch("httpx.AsyncClient.post", return_value=fake):
        result = await check_provider("deepseek", api_key="sk-good")
    assert result.success is True
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_anthropic_uses_x_api_key(monkeypatch):
    captured = {}

    async def _post(url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        fake = MagicMock()
        fake.status_code = 200
        return fake

    with patch("httpx.AsyncClient.post", side_effect=_post):
        await check_provider("anthropic", api_key="sk-ant")
    assert "x-api-key" in captured["headers"]


def test_connection_result_to_dict():
    r = ConnectionResult(success=True, message="ok", latency_ms=42, provider="deepseek")
    d = r.to_dict()
    assert d["success"] is True
    assert d["latency_ms"] == 42