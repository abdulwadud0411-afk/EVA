"""Tests for Phase 17 settings manager."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.settings.settings_manager import SettingsManager, SettingsError


def test_get_active_provider_default():
    ConfigManager.load()
    assert SettingsManager.get_active_provider() == "deepseek"


def test_set_active_provider_persists(tmp_path):
    ConfigManager.load()
    SettingsManager.set_active_provider("openai")
    assert SettingsManager.get_active_provider() == "openai"

    # Reload from disk
    ConfigManager.reset()
    ConfigManager.load()
    assert SettingsManager.get_active_provider() == "openai"


def test_set_active_provider_empty_raises():
    with pytest.raises(SettingsError, match="cannot be empty"):
        SettingsManager.set_active_provider("")


def test_get_provider_config():
    ConfigManager.load()
    cfg = SettingsManager.get_provider_config("deepseek")
    assert isinstance(cfg, dict)
    assert "base_url" in cfg


def test_set_provider_config_persists(tmp_path):
    ConfigManager.load()
    SettingsManager.set_provider_config(
        "deepseek",
        base_url="https://custom.example.com",
        model="deepseek-v4-pro",
    )
    cfg = SettingsManager.get_provider_config("deepseek")
    assert cfg.get("base_url") == "https://custom.example.com"
    assert cfg.get("primary_model") == "deepseek-v4-pro"


def test_api_key_goes_to_env_not_config(tmp_path, monkeypatch):
    # Point .env to a temp file
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=1\n", encoding="utf-8")
    ConfigManager.configure(env_file=env_file)
    ConfigManager.load()

    SettingsManager.set_provider_config("deepseek", api_key="sk-test-123")

    # Verify .env file contains the key
    content = env_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-test-123" in content
    assert "EXISTING=1" in content  # preserved

    # Verify user_config.yaml does NOT contain the key
    if ConfigManager._user_config_file.exists():
        user_cfg = ConfigManager._user_config_file.read_text(encoding="utf-8")
        assert "sk-test-123" not in user_cfg


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
    assert SettingsManager.get_api_key("deepseek") == "sk-from-env"


def test_get_api_key_ollama_none():
    assert SettingsManager.get_api_key("ollama") is None


def test_get_ai_settings_snapshot():
    ConfigManager.load()
    snapshot = SettingsManager.get_ai_settings()
    assert "provider" in snapshot
    assert "providers" in snapshot
    assert "models" in snapshot
    assert "base_url" in snapshot
    assert "requires_api_key" in snapshot
    assert snapshot["provider"] in snapshot["providers"]