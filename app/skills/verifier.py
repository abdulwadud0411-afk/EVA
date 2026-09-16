"""
Skill verifier (Phase 15).

Runs a lightweight verification after a skill finishes. If the skill
declares a `verification` string, the verifier interprets it as a
simple check keyword:
    "file_exists:<path>"
    "process_running:<name>"
    "active_window_contains:<substring>"
    "none"

If the string is empty or uninterpretable, verification passes.
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.logger import get_logger
from app.skills.base import Skill

logger = get_logger(__name__)


class SkillVerifier:
    async def verify(self, skill: Skill) -> bool:
        spec = (skill.verification or "").strip()
        if not spec or spec.lower() == "none":
            return True

        try:
            kind, _, value = spec.partition(":")
            kind = kind.strip().lower()
            value = value.strip()

            if kind == "file_exists" and value:
                from app.tools.verifier import file_exists
                return bool(file_exists(value).get("verified"))

            if kind == "process_running" and value:
                from app.tools.verifier import process_running
                return bool(process_running(value).get("verified"))

            if kind == "active_window_contains" and value:
                from app.tools.verifier import active_window_title_contains
                return bool(active_window_title_contains(value).get("verified"))

            logger.warning("unknown_verification_spec", spec=spec)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill_verify_error", spec=spec, error=str(exc))
            return False