"""
DeepSeek provider adapter (OpenAI-compatible chat completions API).

Handles two tool-call formats:
    1. Standard OpenAI-style `tool_calls` field (preferred).
    2. DeepSeek's inline DSML format, where tool calls arrive inside
       `message.content` as `<||DSML|| calls>...</||DSML|| calls>` tags.
"""
from __future__ import annotations

import json
import re
import secrets
from typing import Any, Dict, List, Optional

import httpx

from app.brain.base import AIProvider
from app.brain.response_models import AIResponse, ToolCall
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# DSML parsing
#
# DeepSeek sometimes emits tool calls using full-width vertical bars
# (U+FF5C, ｜) inside a `<||DSML|| ...>` tag wrapper instead of the
# standard OpenAI `tool_calls` array. We detect and parse both.
# ---------------------------------------------------------------------- #
_DSML_BAR = r"[\|\uFF5C]{1,4}"
_DSML_OPEN = rf"<{_DSML_BAR}\s*DSML\s*{_DSML_BAR}"


def _is_dsml(text: str) -> bool:
    return bool(text) and "DSML" in text


def _parse_dsml_tool_calls(content: str) -> List[ToolCall]:
    """
    Parse DeepSeek inline DSML tool calls from message content.

    Format:
        <||DSML|| calls>
        <||DSML|| invoke name="tool_name">
        <||DSML|| parameter name="arg1" string="true">value</||DSML|| parameter>
        <||DSML|| parameter name="arg2">42</||DSML|| parameter>
        </||DSML|| invoke>
        </||DSML|| calls>
    """
    if not _is_dsml(content):
        return []

    calls: List[ToolCall] = []

    invoke_re = re.compile(
        rf'{_DSML_OPEN}\s*invoke\s+name="([^"]+)"\s*>(.*?)'
        rf'</{_DSML_BAR}\s*DSML\s*{_DSML_BAR}\s*invoke\s*>',
        re.DOTALL | re.IGNORECASE,
    )
    param_re = re.compile(
        rf'{_DSML_OPEN}\s*parameter\s+name="([^"]+)"'
        rf'(?:\s+string="(true|false)")?\s*>(.*?)'
        rf'</{_DSML_BAR}\s*DSML\s*{_DSML_BAR}\s*parameter\s*>',
        re.DOTALL | re.IGNORECASE,
    )

    for match in invoke_re.finditer(content):
        name = match.group(1).strip()
        body = match.group(2)
        if not name:
            continue

        args: Dict[str, Any] = {}
        for pm in param_re.finditer(body):
            pname = pm.group(1).strip()
            is_string = (pm.group(2) or "").lower() == "true"
            raw = pm.group(3).strip()

            if is_string:
                args[pname] = raw
            else:
                try:
                    args[pname] = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    args[pname] = raw

        calls.append(ToolCall(
            id=f"dsml_{secrets.token_hex(6)}",
            name=name,
            arguments=args,
        ))

    return calls


def _strip_dsml(content: str) -> str:
    """Remove all DSML tool-call blocks from content."""
    if not _is_dsml(content):
        return content

    # Remove whole <||DSML|| calls> ... </||DSML|| calls> blocks
    cleaned = re.sub(
        rf"{_DSML_OPEN}\s*calls\s*>.*?"
        rf"</{_DSML_BAR}\s*DSML\s*{_DSML_BAR}\s*calls\s*>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove any lingering DSML tags
    cleaned = re.sub(
        rf"</?{_DSML_BAR}\s*DSML\s*{_DSML_BAR}[^>]*>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


# ---------------------------------------------------------------------- #
# DeepSeekProvider
# ---------------------------------------------------------------------- #
class DeepSeekProvider(AIProvider):
    def __init__(
        self,
        config: Dict[str, Any],
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.config = config or {}
        self.api_key: Optional[str] = self.config.get("api_key")
        self.base_url: str = str(
            self.config.get("base_url", "https://api.deepseek.com")
        ).rstrip("/")
        self.model: str = self.config.get("primary_model", "deepseek-v4-flash")
        self.temperature: float = float(self.config.get("temperature", 0.2))
        self.max_tokens: int = int(self.config.get("max_tokens", 8192))
        self.timeout: float = float(self.config.get("timeout_seconds", 120))
        self._transport = http_transport

    # ------------------------------------------------------------------ #
    # AIProvider API
    # ------------------------------------------------------------------ #
    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_tool_calling": True,
            "supports_vision": False,
            "supports_reasoning": True,
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
            # DeepSeek auto-caching: system prompt + tools schemas
            # are cached when they repeat across requests.
            # This reduces input cost by up to 90% on cached parts.
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        logger.info(
            "deepseek_request",
            model=payload["model"],
            n_messages=len(messages),
        )

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

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #
    def _parse_response(self, data: Dict[str, Any]) -> AIResponse:
        choices = data.get("choices") or [{}]
        choice = choices[0]
        message = choice.get("message") or {}

        raw_content = message.get("content") or ""
        finish_reason = choice.get("finish_reason", "stop")

        # 1. Standard OpenAI-style tool_calls field
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
                    id=tc.get("id", "") or f"call_{secrets.token_hex(4)}",
                    name=fn.get("name", ""),
                    arguments=parsed_args if isinstance(parsed_args, dict) else {"value": parsed_args},
                )
            )

               # 2. Fallback: inline DSML in content
        text = raw_content
        if not tool_calls and _is_dsml(raw_content):
            dsml_calls = _parse_dsml_tool_calls(raw_content)
            if dsml_calls:
                logger.info(
                    "deepseek_dsml_tool_calls_parsed",
                    count=len(dsml_calls),
                    names=[c.name for c in dsml_calls],
                )
                tool_calls = dsml_calls
                text = _strip_dsml(raw_content)
                finish_reason = "tool_calls"

        # Extract usage for logging (always available)
        usage = data.get("usage") or {}
        logger.info(
            "deepseek_usage",
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            cached_tokens=usage.get("prompt_cache_hit_tokens"),
        )

        return AIResponse(
            text=text or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            provider_name="deepseek",
            model_used=data.get("model", self.model),
            usage=usage,
            raw=data,
        )