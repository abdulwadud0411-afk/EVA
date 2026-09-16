"""
Built-in system skills (Phase 15).

Register a small set of safe, universally useful skills.
They are only saved the first time EVA boots (idempotent).
"""
from __future__ import annotations

from app.core.logger import get_logger
from app.skills.base import Skill, SkillStep
from app.skills.registry import SkillRegistry

logger = get_logger(__name__)


def _open_notepad_and_type() -> Skill:
    return Skill(
        name="open_notepad_and_type",
        description="Open Notepad and type the given text into it.",
        version="1.0.0",
        source="builtin",
        tags=["builtin", "text"],
        required_tools=["open_application", "type_text"],
        steps=[
            SkillStep(
                index=1,
                action="Open Notepad",
                tool_name="open_application",
                arguments={"application": "notepad"},
            ),
            SkillStep(
                index=2,
                action="Type the provided text",
                tool_name="type_text",
                arguments={"text": "Hello from EVA"},
                optional=False,
            ),
        ],
    )


def _open_url_and_screenshot() -> Skill:
    return Skill(
        name="open_url_and_screenshot",
        description="Open a URL in the browser, then take a screenshot.",
        version="1.0.0",
        source="builtin",
        tags=["builtin", "browser", "screenshot"],
        required_tools=["open_url", "take_screenshot"],
        steps=[
            SkillStep(
                index=1,
                action="Open the URL",
                tool_name="open_url",
                arguments={"url": "https://example.com"},
            ),
            SkillStep(
                index=2,
                action="Take a screenshot",
                tool_name="take_screenshot",
                arguments={},
            ),
        ],
    )


def _open_app_and_focus() -> Skill:
    return Skill(
        name="open_app_and_focus",
        description="Open an application, then bring its window to the foreground.",
        version="1.0.0",
        source="builtin",
        tags=["builtin", "window"],
        required_tools=["open_application", "focus_window"],
        steps=[
            SkillStep(
                index=1,
                action="Open the application",
                tool_name="open_application",
                arguments={"application": "notepad"},
            ),
            SkillStep(
                index=2,
                action="Focus its window",
                tool_name="focus_window",
                arguments={"title": "Notepad"},
                optional=True,
            ),
        ],
    )


def register_builtin_skills(force: bool = False) -> int:
    """
    Register the built-in skills if they do not already exist.

    Returns the number of newly registered skills.
    """
    candidates = [
        _open_notepad_and_type(),
        _open_url_and_screenshot(),
        _open_app_and_focus(),
    ]
    registered = 0
    existing = set(SkillRegistry.list_skills())

    for skill in candidates:
        if not force and skill.name in existing:
            continue
        try:
            SkillRegistry.save_skill(skill)
            registered += 1
            logger.info("builtin_skill_registered", name=skill.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("builtin_skill_register_failed", name=skill.name, error=str(exc))

    return registered