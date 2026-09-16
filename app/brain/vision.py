"""
Vision client (Phase 6).

Sends images to the active AI provider's vision model and parses the
reply. Currently DeepSeek's vision endpoint is used; the interface is
provider-agnostic so other providers can be added later.

Public API:
    VisionClient(provider_config).analyze_image(image_path, prompt) -> dict
    VisionClient(provider_config).find_element(image_path, element) -> dict
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class VisionError(Exception):
    """Raised when a vision request fails."""


# ---------------------------------------------------------------------- #
# Image helpers
# ---------------------------------------------------------------------- #
def _encode_image_base64(path: Path, max_bytes: int) -> str:
    """Return a data-URL base64 string for the given PNG."""
    if not path.exists():
        raise VisionError(f"Image not found: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise VisionError(
            f"Image too large: {size} bytes (limit {max_bytes})."
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VisionError(f"Cannot read image: {exc}") from exc
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """
    Try to pull a JSON object out of the model's reply.

    Looks for ```json ... ``` fences first, then falls back to the
    first {...} block in the string.
    """
    if not text:
        return None
    # 1. fenced code block
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        # 2. first {...}
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if not brace:
            return None
        candidate = brace.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------- #
# VisionClient
# ---------------------------------------------------------------------- #
class VisionClient:
    """Thin wrapper around the AI provider's vision endpoint."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self.provider_name = str(
            ConfigManager.get("vision.provider", "deepseek")
        ).lower()
        section = ConfigManager.get(f"ai.{self.provider_name}", {}) or {}
        self.base_url = str(section.get("base_url", "https://api.deepseek.com")).rstrip("/")
        self.api_key = section.get("api_key")
        self.model = section.get("vision_model") or section.get("primary_model")
        self.timeout = float(section.get("timeout_seconds", 120))
        self.min_confidence = float(ConfigManager.get("vision.min_confidence", 0.70))
        self.max_image_bytes = int(ConfigManager.get("vision.max_image_bytes", 5_000_000))
        self._transport = transport

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def analyze_image(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an image + prompt to the vision model, return raw text."""
        if not self.api_key:
            raise VisionError(
                f"Vision provider '{self.provider_name}' has no API key. "
                f"Set the corresponding env var."
            )
        if not self.model:
            raise VisionError("No vision model configured.")

        prompt = prompt or ConfigManager.get(
            "vision.default_prompt",
            "Describe what is visible in this screenshot.",
        )
        data_url = _encode_image_base64(image_path, self.max_image_bytes)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info("vision_analyze_image", model=self.model, size_bytes=len(data_url))

        client_kwargs: Dict[str, Any] = {"timeout": self.timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            raise VisionError(
                f"Vision HTTP error {exc.response.status_code if exc.response else '?'}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"Vision request failed: {exc}") from exc

        data = r.json()
        choices = data.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""

        return {
            "text": text,
            "raw": data,
            "model_used": data.get("model", self.model),
        }

    async def find_element(
        self,
        image_path: Path,
        element_description: str,
    ) -> Dict[str, Any]:
        """
        Ask the vision model to locate a UI element on the screenshot.

        Returns:
            {
                "found": bool,
                "element": str,
                "x": int|None,
                "y": int|None,
                "confidence": float,
                "reason": str
            }
        """
        prompt = (
            "You are a UI element locator. Look at the screenshot and find: "
            f"'{element_description}'. "
            "Respond ONLY with a JSON object of the form:\n"
            '{ "element": "<name>", "x": <int>, "y": <int>, "confidence": <0-1>, "reason": "<short>" }\n'
            "If the element is not visible, respond with:\n"
            '{ "element": "<name>", "found": false, "reason": "<short>" }\n'
            "Coordinates must be absolute screen pixels of the element's center."
        )
        result = await self.analyze_image(image_path, prompt=prompt)
        text = result.get("text", "")

        parsed = _extract_json_block(text)
        if not parsed:
            return {
                "found": False,
                "element": element_description,
                "x": None,
                "y": None,
                "confidence": 0.0,
                "reason": "Vision model returned no parseable JSON.",
                "raw_text": text,
            }

        found = bool(parsed.get("found", True))
        confidence = float(parsed.get("confidence", 0.0))

        if not found:
            return {
                "found": False,
                "element": parsed.get("element", element_description),
                "x": None,
                "y": None,
                "confidence": confidence,
                "reason": parsed.get("reason", "not found"),
                "raw_text": text,
            }

        x = parsed.get("x")
        y = parsed.get("y")
        if x is None or y is None:
            return {
                "found": False,
                "element": parsed.get("element", element_description),
                "x": None,
                "y": None,
                "confidence": confidence,
                "reason": "Vision model did not return coordinates.",
                "raw_text": text,
            }

        try:
            x = int(x)
            y = int(y)
        except (TypeError, ValueError):
            return {
                "found": False,
                "element": parsed.get("element", element_description),
                "x": None,
                "y": None,
                "confidence": confidence,
                "reason": "Vision model returned non-integer coordinates.",
                "raw_text": text,
            }

        if confidence < self.min_confidence:
            return {
                "found": False,
                "element": parsed.get("element", element_description),
                "x": x,
                "y": y,
                "confidence": confidence,
                "reason": f"Confidence {confidence:.2f} below threshold {self.min_confidence:.2f}.",
                "raw_text": text,
            }

        return {
            "found": True,
            "element": parsed.get("element", element_description),
            "x": x,
            "y": y,
            "confidence": confidence,
            "reason": parsed.get("reason", ""),
            "raw_text": text,
        }