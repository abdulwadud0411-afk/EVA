"""
Workflow extractor (Phase 14).

Combines transcript + frame descriptions and asks the AI provider
to produce a structured step-by-step workflow.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


_PROMPT_TEMPLATE = """You are analysing a video to extract a reusable step-by-step workflow.

TITLE: {title}

TRANSCRIPT (may be partial):
{transcript}

VISUAL NOTES (from sampled frames):
{visual_notes}

Return ONLY a JSON object with this exact shape (no prose, no code fences):
{{
  "title": "<short workflow name>",
  "summary": "<one-paragraph summary>",
  "steps": [
    {{"index": 1, "action": "<short action>", "details": "<optional details>", "tool_hint": "<app or tool name or empty>"}}
  ],
  "required_tools": ["app or tool name"]
}}

Rules:
- 2 to 20 steps.
- Each step must be concrete and observable.
- Never invent a step that is not supported by the transcript or visual notes.
- If nothing useful can be extracted, return {{"title": "Unknown", "summary": "", "steps": [], "required_tools": []}}.
"""


class WorkflowExtractor:
    async def extract(
        self,
        title: str,
        transcript: str,
        visual_notes: List[str],
    ) -> Optional[Dict[str, Any]]:
        provider = ProviderRegistry.get_active_provider()

        visual_text = "\n".join(f"- {v}" for v in visual_notes if v) or "(none)"
        prompt = _PROMPT_TEMPLATE.format(
            title=title or "Untitled",
            transcript=(transcript or "")[:15000],
            visual_notes=visual_text,
        )

        try:
            response = await provider.generate(
                messages=[
                    {"role": "system", "content": "You extract structured workflows from video."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("workflow_ai_failed", error=str(exc))
            return None

        text = (response.text or "").strip()
        data = self._parse_json(text)
        if data is None:
            logger.warning("workflow_parse_failed", preview=text[:200])
            return None

        # Basic sanity
        if not isinstance(data.get("steps"), list):
            return None

        min_steps = int(ConfigManager.get("learning.workflow.min_steps", 2))
        max_steps = int(ConfigManager.get("learning.workflow.max_steps", 20))
        if len(data["steps"]) < min_steps:
            return None
        data["steps"] = data["steps"][:max_steps]
        return data

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        # Strip code fences if present
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try to find first { ... last }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None