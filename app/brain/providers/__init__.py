"""
Registers every available provider.

Importing this module ensures all adapters are registered with
`ProviderRegistry` before use.
"""
from app.brain.provider_registry import ProviderRegistry
from app.brain.providers.deepseek_provider import DeepSeekProvider
from app.brain.providers.ollama_provider import OllamaProvider

ProviderRegistry.register("deepseek", DeepSeekProvider)
ProviderRegistry.register("ollama", OllamaProvider)