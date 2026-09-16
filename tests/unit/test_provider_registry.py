import pytest

from app.brain.base import AIProvider
from app.brain.provider_registry import ProviderRegistry
from app.brain.response_models import AIResponse
from app.core.config_manager import ConfigManager, ConfigurationError


class _DummyProvider(AIProvider):
    def __init__(self, config):
        self.config = config

    async def generate(self, messages, tools=None, tool_choice=None, **kwargs):
        return AIResponse(text="dummy", provider_name="dummy")

    @property
    def capabilities(self):
        return {"supports_tool_calling": False}

    async def validate_api_key(self):
        return True


def test_register_and_list():
    ProviderRegistry.register("dummy", _DummyProvider)
    assert "dummy" in ProviderRegistry.list_providers()


def test_get_active_returns_registered():
    ProviderRegistry.register("dummy", _DummyProvider)
    ConfigManager.load()
    ConfigManager.set("ai.provider", "dummy", persist=False)
    provider = ProviderRegistry.get_active_provider()
    assert isinstance(provider, _DummyProvider)


def test_unknown_provider_raises():
    ConfigManager.load()
    ConfigManager.set("ai.provider", "nope", persist=False)
    with pytest.raises(ConfigurationError, match="not registered"):
        ProviderRegistry.get_active_provider()