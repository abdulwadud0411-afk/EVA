"""
Connection check for AI providers (Phase 17).

Sends a minimal request to the chosen provider and reports
whether the API key + endpoint work.

Public API:
    result = await check_provider("deepseek")
    result.success  # bool
    result.message  # str
    result.latency_ms  # int
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.settings.provider_catalog import ProviderCatalog
from app.settings.settings_manager import SettingsManager

logger = get_logger(__name__)


@dataclass
class ConnectionResult:
    """Result of a provider connection check."""
    success: bool
    message: str
    latency_ms: int = 0
    provider: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "provider": self.provider,
        }


async def check_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 15.0,
) -> ConnectionResult:
    """
    Check a provider's connection.

    Args:
        provider_name: catalog key (e.g. "deepseek")
        api_key: override key (if None, reads from .env / config)
        base_url: override base URL (if None, reads from config)
        model: override model (if None, reads from config)
        timeout: request timeout in seconds

    Returns:
        ConnectionResult
    """
    name = (provider_name or "").strip().lower()
    info = ProviderCatalog.get(name)
    if info is None:
        return ConnectionResult(
            success=False,
            message=f"Unknown provider: {name}",
            provider=name,
        )

    # Resolve api key
    if api_key is None:
        api_key = SettingsManager.get_api_key(name)

    if info.requires_api_key and not api_key:
        return ConnectionResult(
            success=False,
            message=f"API key not set. Set {info.env_key} in .env.",
            provider=name,
        )

    # Resolve base url
    if base_url is None:
        base_url = ConfigManager.get(f"ai.{name}.base_url") or info.base_url
    base_url = str(base_url).rstrip("/")

    # Resolve model
    if model is None:
        model = ConfigManager.get(f"ai.{name}.primary_model")
    if not model and info.models:
        model = info.models[0]

    if not base_url:
        return ConnectionResult(
            success=False,
            message="Base URL is not set.",
            provider=name,
        )

    started = time.perf_counter()

    try:
        if name == "ollama":
            return await _check_ollama(base_url, started, name)
        if name == "anthropic":
            return await _check_anthropic(base_url, api_key, model, started, name, timeout)
        if name == "gemini":
            return await _check_gemini(base_url, api_key, model, started, name, timeout)
        # DeepSeek, OpenAI, Grok, OpenRouter, custom — all OpenAI-compatible
        return await _check_openai_compatible(
            base_url, api_key, model, started, name, timeout,
        )
    except httpx.HTTPError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        logger.warning("check_provider_http_error", provider=name, error=str(exc))
        return ConnectionResult(
            success=False,
            message=f"Network error: {exc}",
            latency_ms=latency,
            provider=name,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        logger.error("check_provider_failed", provider=name, error=str(exc))
        return ConnectionResult(
            success=False,
            message=f"Unexpected error: {exc}",
            latency_ms=latency,
            provider=name,
        )


# ---------------------------------------------------------------------- #
# Provider-specific checkers
# ---------------------------------------------------------------------- #
async def _check_ollama(base_url: str, started: float, name: str) -> ConnectionResult:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{base_url}/api/tags")
    latency = int((time.perf_counter() - started) * 1000)
    if r.status_code == 200:
        data = r.json()
        models = [m.get("name", "?") for m in data.get("models", [])]
        return ConnectionResult(
            success=True,
            message=f"Ollama is running. {len(models)} model(s) available.",
            latency_ms=latency,
            provider=name,
        )
    return ConnectionResult(
        success=False,
        message=f"Ollama responded with {r.status_code}. Is it running?",
        latency_ms=latency,
        provider=name,
    )


async def _check_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    started: float,
    name: str,
    timeout: float,
) -> ConnectionResult:
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 4,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
    latency = int((time.perf_counter() - started) * 1000)

    if r.status_code == 200:
        return ConnectionResult(
            success=True,
            message=f"Connected to {name} ({model}). Latency {latency} ms.",
            latency_ms=latency,
            provider=name,
        )
    if r.status_code == 401:
        return ConnectionResult(
            success=False,
            message="Invalid API key (401).",
            latency_ms=latency,
            provider=name,
        )
    if r.status_code == 404:
        return ConnectionResult(
            success=False,
            message="Endpoint or model not found (404). Check base URL/model.",
            latency_ms=latency,
            provider=name,
        )
    if r.status_code == 429:
        return ConnectionResult(
            success=False,
            message="Rate limited (429). Try again later.",
            latency_ms=latency,
            provider=name,
        )
    body = r.text[:200]
    return ConnectionResult(
        success=False,
        message=f"HTTP {r.status_code}: {body}",
        latency_ms=latency,
        provider=name,
    )


async def _check_anthropic(
    base_url: str,
    api_key: str,
    model: str,
    started: float,
    name: str,
    timeout: float,
) -> ConnectionResult:
    url = f"{base_url}/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4,
        "messages": [{"role": "user", "content": "ping"}],
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
    latency = int((time.perf_counter() - started) * 1000)

    if r.status_code == 200:
        return ConnectionResult(
            success=True,
            message=f"Connected to Claude ({model}).",
            latency_ms=latency,
            provider=name,
        )
    if r.status_code == 401:
        return ConnectionResult(
            success=False, message="Invalid API key (401).",
            latency_ms=latency, provider=name,
        )
    return ConnectionResult(
        success=False,
        message=f"HTTP {r.status_code}: {r.text[:200]}",
        latency_ms=latency,
        provider=name,
    )


async def _check_gemini(
    base_url: str,
    api_key: str,
    model: str,
    started: float,
    name: str,
    timeout: float,
) -> ConnectionResult:
    url = f"{base_url}/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": "ping"}]}]},
        )
    latency = int((time.perf_counter() - started) * 1000)

    if r.status_code == 200:
        return ConnectionResult(
            success=True,
            message=f"Connected to Gemini ({model}).",
            latency_ms=latency,
            provider=name,
        )
    if r.status_code in (400, 403):
        return ConnectionResult(
            success=False,
            message="Invalid API key or model.",
            latency_ms=latency,
            provider=name,
        )
    return ConnectionResult(
        success=False,
        message=f"HTTP {r.status_code}: {r.text[:200]}",
        latency_ms=latency,
        provider=name,
    )