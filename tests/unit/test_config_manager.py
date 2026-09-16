from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager


def test_load_default_config():
    ConfigManager.load()
    assert ConfigManager.get("app.name") == "EVA"
    assert ConfigManager.get("ai.provider") == "deepseek"


def test_get_nested_value():
    ConfigManager.load()
    assert ConfigManager.get("ai.deepseek.primary_model") == "deepseek-v4-flash"


def test_missing_key_returns_default():
    ConfigManager.load()
    assert ConfigManager.get("does.not.exist", "fallback") == "fallback"


def test_env_override(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-secret-key")
    ConfigManager.reset()
    ConfigManager.load()
    assert ConfigManager.get("ai.deepseek.api_key") == "env-secret-key"


def test_set_persists_to_user_config(tmp_path: Path):
    ConfigManager.load()
    ConfigManager.set("ai.provider", "openai")
    assert ConfigManager.get("ai.provider") == "openai"

    user_file = ConfigManager._user_config_file
    assert user_file.exists()
    import yaml
    data = yaml.safe_load(user_file.read_text(encoding="utf-8"))
    assert data["ai"]["provider"] == "openai"


def test_set_does_not_persist_api_key(tmp_path: Path):
    ConfigManager.load()
    ConfigManager.set("ai.deepseek.api_key", "SECRET-DO-NOT-SAVE")
    user_file = ConfigManager._user_config_file
    content = user_file.read_text(encoding="utf-8") if user_file.exists() else ""
    assert "SECRET-DO-NOT-SAVE" not in content


def test_get_data_dir_is_absolute_and_exists():
    ConfigManager.load()
    d = ConfigManager.get_data_dir()
    assert d.is_absolute()
    assert d.exists()