"""Tests for Phase 17 provider catalog."""
from __future__ import annotations

from app.settings.provider_catalog import ProviderCatalog, ProviderInfo


def test_list_providers_returns_expected():
    providers = ProviderCatalog.list_providers()
    assert "deepseek" in providers
    assert "openai" in providers
    assert "anthropic" in providers
    assert "gemini" in providers
    assert "ollama" in providers
    assert "openrouter" in providers
    assert "custom" in providers


def test_deepseek_first():
    providers = ProviderCatalog.list_providers()
    assert providers[0] == "deepseek"
    assert providers[1] == "ollama"


def test_get_provider_info():
    info = ProviderCatalog.get("deepseek")
    assert isinstance(info, ProviderInfo)
    assert info.display_name == "DeepSeek"
    assert info.env_key == "DEEPSEEK_API_KEY"
    assert "deepseek-v4-flash" in info.models


def test_get_unknown_provider_returns_none():
    assert ProviderCatalog.get("nonexistent") is None


def test_ollama_no_api_key():
    assert ProviderCatalog.requires_api_key("ollama") is False
    assert ProviderCatalog.env_key_for("ollama") == ""


def test_deepseek_requires_api_key():
    assert ProviderCatalog.requires_api_key("deepseek") is True


def test_models_for_returns_list():
    models = ProviderCatalog.models_for("openai")
    assert isinstance(models, list)
    assert len(models) > 0


def test_models_for_unknown_empty():
    assert ProviderCatalog.models_for("nonexistent") == []


def test_display_names():
    names = ProviderCatalog.display_names()
    assert names["deepseek"] == "DeepSeek"
    assert names["openai"] == "OpenAI"


def test_default_base_url():
    assert ProviderCatalog.default_base_url("deepseek") == "https://api.deepseek.com"
    assert ProviderCatalog.default_base_url("ollama") == "http://localhost:11434"


def test_custom_provider_supports_custom_url():
    info = ProviderCatalog.get("custom")
    assert info is not None
    assert info.supports_custom_base_url is True