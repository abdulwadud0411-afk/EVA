"""
Provider catalog (Phase 17).

Static list of known AI providers with:
    - display name
    - default base URL
    - env var name for the API key
    - list of known models
    - capability flags
    - whether custom base URL is allowed

Adding a new provider = adding an entry here + adapter in app/brain/providers/.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProviderInfo:
    key: str
    display_name: str
    base_url: str
    env_key: str
    models: List[str] = field(default_factory=list)
    requires_api_key: bool = True
    supports_custom_base_url: bool = True
    notes: str = ""
    docs_url: str = ""


_PROVIDERS: Dict[str, ProviderInfo] = {
    "deepseek": ProviderInfo(
        key="deepseek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com",
        env_key="DEEPSEEK_API_KEY",
        models=[
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-v4-flash-vision-exp",
        ],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Default provider. Cheapest for most tasks.",
        docs_url="https://platform.deepseek.com",
    ),
    "openai": ProviderInfo(
        key="openai",
        display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        env_key="OPENAI_API_KEY",
        models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Paid. High quality for reasoning and coding.",
        docs_url="https://platform.openai.com",
    ),
    "anthropic": ProviderInfo(
        key="anthropic",
        display_name="Anthropic Claude",
        base_url="https://api.anthropic.com/v1",
        env_key="ANTHROPIC_API_KEY",
        models=[
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Paid. Excellent for long-form reasoning and code.",
        docs_url="https://console.anthropic.com",
    ),
    "gemini": ProviderInfo(
        key="gemini",
        display_name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        env_key="GOOGLE_API_KEY",
        models=[
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp",
        ],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Paid (free tier available). Strong multimodal.",
        docs_url="https://ai.google.dev",
    ),
    "ollama": ProviderInfo(
        key="ollama",
        display_name="Ollama (local)",
        base_url="http://localhost:11434",
        env_key="",  # no key needed
        models=[
            "qwen2.5:3b",
            "llama3.2:3b",
            "phi3:mini",
            "mistral:7b",
        ],
        requires_api_key=False,
        supports_custom_base_url=True,
        notes="FREE. Runs locally on your PC. No internet needed.",
        docs_url="https://ollama.com",
    ),
    "openrouter": ProviderInfo(
        key="openrouter",
        display_name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        env_key="OPENROUTER_API_KEY",
        models=[
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "meta-llama/llama-3.1-70b-instruct",
            "google/gemini-flash-1.5",
        ],
        requires_api_key=True,
        supports_custom_base_url=False,
        notes="Aggregator. Access many models via one API key.",
        docs_url="https://openrouter.ai",
    ),
    "grok": ProviderInfo(
        key="grok",
        display_name="xAI Grok",
        base_url="https://api.x.ai/v1",
        env_key="XAI_API_KEY",
        models=[
            "grok-2-1212",
            "grok-2-vision-1212",
            "grok-beta",
        ],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Paid. xAI's Grok models — needs xAI API key.",
        docs_url="https://x.ai",
    ),
    "custom": ProviderInfo(
        key="custom",
        display_name="Custom (OpenAI-compatible)",
        base_url="",
        env_key="CUSTOM_API_KEY",
        models=[],
        requires_api_key=True,
        supports_custom_base_url=True,
        notes="Any OpenAI-compatible endpoint (e.g. LM Studio, vLLM).",
        docs_url="",
    ),
}


class ProviderCatalog:
    """Read-only catalog of known providers."""

    @classmethod
    def list_providers(cls) -> List[str]:
        """Return provider keys in display order (all providers)."""
        priority = ["deepseek", "openai", "anthropic", "gemini", "grok", "openrouter", "ollama", "custom"]
        others = [k for k in _PROVIDERS.keys() if k not in priority]
        return [k for k in priority if k in _PROVIDERS] + sorted(others)

    @classmethod
    def get(cls, key: str) -> Optional[ProviderInfo]:
        return _PROVIDERS.get(key.lower())

    @classmethod
    def display_names(cls) -> Dict[str, str]:
        return {k: v.display_name for k, v in _PROVIDERS.items()}

    @classmethod
    def models_for(cls, key: str) -> List[str]:
        info = cls.get(key)
        return list(info.models) if info else []

    @classmethod
    def env_key_for(cls, key: str) -> str:
        info = cls.get(key)
        return info.env_key if info else ""

    @classmethod
    def requires_api_key(cls, key: str) -> bool:
        info = cls.get(key)
        return info.requires_api_key if info else True

    @classmethod
    def default_base_url(cls, key: str) -> str:
        info = cls.get(key)
        return info.base_url if info else ""