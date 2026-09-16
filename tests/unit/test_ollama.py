"""Tests for the Ollama provider adapter."""
from __future__ import annotations

import json

import httpx
import pytest

from app.brain.providers.ollama_provider import OllamaProvider


def _mock_transport(payload: dict, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_generate_plain_text():
    payload = {
        "model": "qwen2.5:3b",
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "Hello from Ollama"},
        }],
        "usage": {"total_tokens": 10},
    }
    provider = OllamaProvider(
        {"base_url": "http://localhost:11434", "primary_model": "qwen2.5:3b"},
        http_transport=_mock_transport(payload),
    )
    result = await provider.generate([{"role": "user", "content": "hi"}])
    assert result.text == "Hello from Ollama"
    assert result.provider_name == "ollama"


@pytest.mark.asyncio
async def test_generate_parses_tool_calls():
    payload = {
        "model": "qwen2.5:3b",
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "open_application",
                        "arguments": json.dumps({"application": "notepad"}),
                    },
                }],
            },
        }],
    }
    provider = OllamaProvider(
        {"base_url": "http://localhost:11434", "primary_model": "qwen2.5:3b"},
        http_transport=_mock_transport(payload),
    )
    result = await provider.generate([{"role": "user", "content": "open notepad"}])
    assert result.has_tool_calls is True
    assert result.tool_calls[0].name == "open_application"
    assert result.tool_calls[0].arguments == {"application": "notepad"}


def test_capabilities_declared():
    provider = OllamaProvider({"base_url": "http://localhost:11434"})
    caps = provider.capabilities
    assert caps["supports_tool_calling"] is True
    assert caps["supports_audio"] is False