"""
Demonstration learner (Phase 15).

Two entry points:

    A. learn_from_recording(video_path)
       Reuses Phase 14's video pipeline (audio → transcript →
       frames → workflow). Good when the user has an OBS/screen
       recording.

    B. learn_from_actions(action_events, screenshot_paths)
       Builds a workflow directly from captured input events +
       sparse screenshots. Cheaper than video-based learning.

Both produce a Skill and register it via SkillRegistry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.learning.action_logger import ActionEvent
from app.skills.base import Skill, SkillStep
from app.skills.registry import SkillRegistry

logger = get_logger(__name__)


class DemonstrationError(Exception):
    """Raised when demonstration learning fails."""


_PROMPT_TEMPLATE = """You are analysing a demonstration to produce a reusable skill.

The user performed a sequence of actions on a Windows PC. We captured:
- Input events (mouse clicks, key presses, window switches)
- A short list of visual notes from a few screenshots taken at important moments

EVENTS:
{events}

VISUAL NOTES:
{visual}

Return ONLY a JSON object with this exact shape (no prose):
{{
  "name": "<short_snake_case_skill_name>",
  "description": "<one paragraph>",
  "steps": [
    {{
      "index": 1,
      "action": "<short human action>",
      "tool_name": "<one of: open_application, open_url, click, type_text, hotkey, press_key, focus_window>",
      "arguments": {{ ... }},
      "optional": false
    }}
  ],
  "required_tools": ["..."]
}}

Rules:
- 2 to 20 steps.
- tool_name MUST be from the allowed list.
- For 'click', arguments must be {{"x": int, "y": int}}.
- For 'type_text', arguments must be {{"text": "..."}}.
- For 'hotkey', arguments must be {{"keys": ["ctrl","c"]}}.
- For 'press_key', arguments must be {{"key": "enter"}}.
- For 'open_application', arguments must be {{"application": "chrome"}}.
- For 'open_url', arguments must be {{"url": "https://..."}}.
- For 'focus_window', arguments must be {{"title": "..."}}.
- If events are too sparse, return {{"name": "unknown", "steps": []}}.
"""


_ALLOWED_TOOLS = {
    "open_application", "open_url", "click", "type_text",
    "hotkey", "press_key", "focus_window",
}


class DemonstrationLearner:
    # ------------------------------------------------------------------ #
    # A. From a recorded video
    # ------------------------------------------------------------------ #
    async def learn_from_recording(
        self,
        video_path: Path,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not ConfigManager.get("learning.demonstration.enabled", True):
            raise DemonstrationError("Demonstration learning is disabled")

        try:
            from app.knowledge.learning.video_learner import VideoLearner
        except Exception as exc:  # noqa: BLE001
            raise DemonstrationError(f"VideoLearner unavailable: {exc}") from exc

        learner = VideoLearner()
        result = await learner.learn_from_file(Path(video_path), title=title)
        return result

    # ------------------------------------------------------------------ #
    # B. From captured action events + screenshots
    # ------------------------------------------------------------------ #
    async def learn_from_actions(
        self,
        events: List[ActionEvent],
        screenshot_paths: Optional[List[Path]] = None,
        title: Optional[str] = None,
    ) -> Skill:
        if not events:
            raise DemonstrationError("No action events to learn from")

        # Visual analysis (optional, capped)
        visual_notes: List[str] = []
        if screenshot_paths:
            try:
                from app.knowledge.learning.frame_analyzer import FrameAnalyzer
                fa = FrameAnalyzer(max_frames_to_analyze=6)
                visual_notes = await fa.analyze(list(screenshot_paths)[:6])
            except Exception as exc:  # noqa: BLE001
                logger.warning("demonstration_vision_failed", error=str(exc))

        # Build prompt
        events_blob = self._events_to_text(events, max_lines=200)
        visual_blob = "\n".join(f"- {v}" for v in visual_notes) or "(none)"

        prompt = _PROMPT_TEMPLATE.format(events=events_blob, visual=visual_blob)

        # Ask the provider
        provider = ProviderRegistry.get_active_provider()
        try:
            response = await provider.generate(
                messages=[
                    {"role": "system", "content": "You convert user actions into a reusable skill."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
            )
        except Exception as exc:  # noqa: BLE001
            raise DemonstrationError(f"AI request failed: {exc}") from exc

        data = self._parse_json((response.text or "").strip())
        if data is None:
            raise DemonstrationError("Could not parse workflow from AI")

        name = str(data.get("name", "")).strip()
        steps_raw = data.get("steps") or []
        if not name or len(steps_raw) < 2:
            raise DemonstrationError("AI did not produce a valid skill")

        # Convert + validate steps
        steps: List[SkillStep] = []
        for i, s in enumerate(steps_raw, start=1):
            tool = str(s.get("tool_name") or "").strip()
            if tool not in _ALLOWED_TOOLS:
                logger.warning("demonstration_step_tool_rejected", tool=tool)
                continue
            steps.append(SkillStep(
                index=int(s.get("index", i)),
                action=str(s.get("action", "")),
                tool_name=tool,
                arguments=dict(s.get("arguments") or {}),
                optional=bool(s.get("optional", False)),
            ))

        if len(steps) < 2:
            raise DemonstrationError("Not enough valid steps after filtering")

        skill = Skill(
            name=name,
            description=str(data.get("description", "")),
            version="1.0.0",
            steps=steps,
            required_tools=list(data.get("required_tools") or []),
            source="demo",
            tags=["demo", "learned"],
            verification=None,
        )

        SkillRegistry.save_skill(skill)
        logger.info("demonstration_skill_saved", name=skill.name, steps=len(skill.steps))

        return skill

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _events_to_text(events: List[ActionEvent], max_lines: int = 200) -> str:
        lines: List[str] = []
        for e in events[-max_lines:]:
            kind = e.kind
            d = e.data or {}
            if kind == "click":
                lines.append(f"CLICK {d.get('button', 'left')} at ({d.get('x')}, {d.get('y')})")
            elif kind == "key":
                lines.append(f"TYPE {d.get('char')!r}")
            elif kind == "hotkey":
                lines.append(f"HOTKEY {d.get('name')}")
            elif kind == "window":
                lines.append(f"WINDOW '{d.get('title')}'")
        return "\n".join(lines) or "(no events)"

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None