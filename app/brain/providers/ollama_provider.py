"""
Ollama provider adapter (local LLM).

Talks to a locally running Ollama server via its OpenAI-compatible
endpoint. No API key, no internet, no cost.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from app.brain.base import AIProvider
from app.brain.response_models import AIResponse, ToolCall
from app.core.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(AIProvider):
    def __init__(
        self,
        config: Dict[str, Any],
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.config = config or {}
        self.base_url = str(self.config.get("base_url", "http://localhost:11434")).rstrip("/")
        self.model = self.config.get("primary_model", "qwen2.5:3b")
        self.temperature = float(self.config.get("temperature", 0.3))
        self.max_tokens = int(self.config.get("max_tokens", 4096))
        self.timeout = float(self.config.get("timeout_seconds", 300))
        self._transport = http_transport

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_tool_calling": True,
            "supports_vision": False,
            "supports_reasoning": False,
            "supports_streaming": False,
            "supports_json": True,
            "supports_audio": False,
        }

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> AIResponse:
        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        logger.info("ollama_request", model=payload["model"], n_messages=len(messages))

        client_kwargs: Dict[str, Any] = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:500] if exc.response is not None else ""
                status = exc.response.status_code if exc.response is not None else None
                logger.error("ollama_http_error", status=status, body=body)
                raise RuntimeError(f"Ollama API error {status}: {body[:200]}") from exc
            except httpx.HTTPError as exc:
                logger.error("ollama_transport_error", error=str(exc))
                raise RuntimeError(
                    f"Ollama request failed: {exc}. Is 'ollama serve' running?"
                ) from exc

        data = response.json()
        return self._parse_response(data)

    async def validate_api_key(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def _parse_response(self, data: Dict[str, Any]) -> AIResponse:
        choices = data.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}

        tool_calls: List[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                parsed = {"_raw": raw_args}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=parsed if isinstance(parsed, dict) else {"value": parsed},
            ))

        return AIResponse(
            text=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            provider_name="ollama",
            model_used=data.get("model", self.model),
            usage=data.get("usage") or {},
            raw=data,
        )