"""
EVA Learning System (Phase 14).

Turns YouTube URLs, local videos, and demonstrations into reusable
knowledge / skills.

Pipeline:
    URL/File → Transcript (captions or STT) → Frames (ffmpeg)
             → Analysis (AI + Vision) → Workflow → Knowledge/Skill
"""
from app.knowledge.learning.video_learner import VideoLearner, LearningError  # noqa: F401