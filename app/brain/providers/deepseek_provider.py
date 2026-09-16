"""
DeepSeek provider adapter (OpenAI-compatible chat completions API).

Important: This is the ONLY file in Phase 1 that knows the DeepSeek API
shape. The rest of EVA depends solely on `AIProvider`.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from app.brain.base import AIProvider
from app.brain.response_models import AIResponse, ToolCall
from app.core.logger import get_logger

logger = get_logger(__name__)


class DeepSeekProvider(AIProvider):
    def __init__(
        self,
        config: Dict[str, Any],
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.config = config or {}
        self.api_key: Optional[str] = self.config.get("api_key")
        self.base_url: str = str(self.config.get("base_url", "https://api.deepseek.com")).rstrip("/")
        self.model: str = self.config.get("primary_model", "deepseek-v4-flash")
        self.temperature: float = float(self.config.get("temperature", 0.2))
        self.max_tokens: int = int(self.config.get("max_tokens", 8192))
        self.timeout: float = float(self.config.get("timeout_seconds", 120))
        self._transport = http_transport  # injectable for tests

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_tool_calling": True,
            "supports_vision": False,          # vision is a separate model
            "supports_reasoning": True,
            "supports_streaming": False,       # not implemented in Phase 1
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
        if not self.api_key:
            raise RuntimeError(
                "DeepSeek API key is missing. Set DEEPSEEK_API_KEY in .env "
                "or configure ai.deepseek.api_key."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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

        logger.info("deepseek_request", model=payload["model"], n_messages=len(messages))

        client_kwargs: Dict[str, Any] = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if exc.response is not None else ""
                status = exc.response.status_code if exc.response is not None else None
                logger.error("deepseek_http_error", status=status, body=body[:500])
                raise RuntimeError(
                    f"DeepSeek API error {status}: {body[:200]}"
                ) from exc
            except httpx.HTTPError as exc:
                logger.error("deepseek_transport_error", error=str(exc))
                raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

        data = response.json()
        return self._parse_response(data)

    async def validate_api_key(self) -> bool:
        try:
            await self.generate(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=4,
            )
            return True
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
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                parsed_args = {"_raw": raw_args}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=parsed_args if isinstance(parsed_args, dict) else {"value": parsed_args},
                )
            )

        return AIResponse(
            text=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            provider_name="deepseek",
            model_used=data.get("model", self.model),
            usage=data.get("usage") or {},
            raw=data,
        )