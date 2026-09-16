"""
EVA Skill System (Phase 15).

A skill is a reusable, versioned procedure (a list of steps) that
EVA can execute later to reproduce a learned workflow.

Public API:
    from app.skills import SkillRegistry, SkillExecutor, SkillResult
    SkillRegistry.list_skills()
    await SkillExecutor().execute("capcut_trim_video")
"""
from app.skills.base import (  # noqa: F401
    Skill,
    SkillStep,
    SkillResult,
    SkillExecutionError,
    SkillDefinitionError,
)
from app.skills.registry import SkillRegistry  # noqa: F401
from app.skills.executor import SkillExecutor  # noqa: F401
from app.skills.verifier import SkillVerifier  # noqa: F401