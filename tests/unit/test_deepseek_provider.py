import json

import httpx
import pytest

from app.brain.providers.deepseek_provider import DeepSeekProvider


def _mock_transport(payload: dict, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_generate_plain_text_response():
    payload = {
        "id": "x",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello world!"},
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }
    provider = DeepSeekProvider(
        {
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "primary_model": "deepseek-v4-flash",
            "timeout_seconds": 5,
        },
        http_transport=_mock_transport(payload),
    )
    result = await provider.generate([{"role": "user", "content": "hi"}])
    assert result.text == "Hello world!"
    assert result.provider_name == "deepseek"
    assert result.finish_reason == "stop"
    assert result.usage["total_tokens"] == 5
    assert result.has_tool_calls is False


@pytest.mark.asyncio
async def test_generate_parses_tool_calls():
    payload = {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "open_application",
                                "arguments": json.dumps({"application": "chrome"}),
                            },
                        }
                    ],
                },
            }
        ],
    }
    provider = DeepSeekProvider(
        {
            "api_key": "test",
            "base_url": "https://api.deepseek.com",
            "primary_model": "deepseek-v4-flash",
            "timeout_seconds": 5,
        },
        http_transport=_mock_transport(payload),
    )
    result = await provider.generate([{"role": "user", "content": "open chrome"}])
    assert result.has_tool_calls is True
    assert result.tool_calls[0].name == "open_application"
    assert result.tool_calls[0].arguments == {"application": "chrome"}


@pytest.mark.asyncio
async def test_missing_api_key_raises():
    provider = DeepSeekProvider(
        {"base_url": "https://api.deepseek.com"},
        http_transport=_mock_transport({"choices": []}),
    )
    with pytest.raises(RuntimeError, match="API key is missing"):
        await provider.generate([{"role": "user", "content": "hi"}])


def test_capabilities_declared():
    provider = DeepSeekProvider({"api_key": "x"})
    caps = provider.capabilities
    assert caps["supports_tool_calling"] is True
    assert caps["supports_vision"] is False