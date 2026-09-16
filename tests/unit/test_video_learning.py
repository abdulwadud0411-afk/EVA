"""
Tests for Phase 14 video learning.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config_manager import ConfigManager


# ---------------------------------------------------------------------- #
# YouTube transcript extractor
# ---------------------------------------------------------------------- #
def test_extract_video_id():
    from app.knowledge.learning.youtube_transcript_extractor import (
        YouTubeTranscriptExtractor,
    )
    e = YouTubeTranscriptExtractor()
    assert e.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert e.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert e.extract_video_id("https://example.com") is None


def test_extract_returns_none_when_api_missing():
    from app.knowledge.learning.youtube_transcript_extractor import (
        YouTubeTranscriptExtractor,
    )
    e = YouTubeTranscriptExtractor()
    with patch.dict("sys.modules", {"youtube_transcript_api": None}):
        result = e.extract("https://youtu.be/dQw4w9WgXcQ")
    assert result is None


# ---------------------------------------------------------------------- #
# Video processor (mocked ffmpeg)
# ---------------------------------------------------------------------- #
def test_video_processor_ffmpeg_missing(tmp_path, monkeypatch):
    from app.knowledge.learning import video_processor
    monkeypatch.setattr(video_processor, "_ffmpeg_path", lambda: None)
    vp = video_processor.VideoProcessor()
    fake = tmp_path / "x.mp4"
    fake.write_bytes(b"x")
    with pytest.raises(video_processor.VideoProcessError):
        vp.extract_audio(fake)


# ---------------------------------------------------------------------- #
# Frame analyzer
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_frame_analyzer_empty():
    from app.knowledge.learning.frame_analyzer import FrameAnalyzer
    fa = FrameAnalyzer(max_frames_to_analyze=3)
    assert await fa.analyze([]) == []


def test_frame_analyzer_select_evenly():
    from app.knowledge.learning.frame_analyzer import FrameAnalyzer
    frames = [Path(f"f{i}.png") for i in range(20)]
    picked = FrameAnalyzer._select(frames, 5)
    assert len(picked) == 5
    assert picked[0].name == "f0.png"


# ---------------------------------------------------------------------- #
# Workflow extractor
# ---------------------------------------------------------------------- #
def test_parse_json_direct():
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    text = '{"title": "X", "steps": [], "required_tools": []}'
    assert WorkflowExtractor._parse_json(text)["title"] == "X"


def test_parse_json_with_code_fence():
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    text = '```json\n{"title": "X", "steps": []}\n```'
    assert WorkflowExtractor._parse_json(text)["title"] == "X"


def test_parse_json_with_prose():
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    text = 'Here you go: {"title": "X", "steps": []} — end.'
    assert WorkflowExtractor._parse_json(text)["title"] == "X"


def test_parse_json_invalid():
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    assert WorkflowExtractor._parse_json("not json") is None
    assert WorkflowExtractor._parse_json("") is None


@pytest.mark.asyncio
async def test_workflow_extract_requires_min_steps(monkeypatch):
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    from app.brain.provider_registry import ProviderRegistry

    fake_provider = MagicMock()
    fake_response = MagicMock()
    fake_response.text = '{"title": "X", "steps": [{"index": 1, "action": "one"}], "required_tools": []}'
    fake_provider.generate = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: fake_provider))

    ConfigManager.load()
    ConfigManager.set("learning.workflow.min_steps", 2, persist=False)

    result = await WorkflowExtractor().extract("T", "transcript", [])
    assert result is None   # only 1 step, min is 2


@pytest.mark.asyncio
async def test_workflow_extract_success(monkeypatch):
    from app.knowledge.learning.workflow_extractor import WorkflowExtractor
    from app.brain.provider_registry import ProviderRegistry

    fake_provider = MagicMock()
    fake_response = MagicMock()
    fake_response.text = (
        '{"title": "Reset device", '
        '"summary": "Press button 5 seconds.", '
        '"steps": ['
        '{"index": 1, "action": "Press reset button", "tool_hint": ""},'
        '{"index": 2, "action": "Wait for LED green", "tool_hint": ""}'
        '], "required_tools": []}'
    )
    fake_provider.generate = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: fake_provider))

    ConfigManager.load()
    ConfigManager.set("learning.workflow.min_steps", 2, persist=False)

    result = await WorkflowExtractor().extract("T", "transcript", [])
    assert result is not None
    assert result["title"] == "Reset device"
    assert len(result["steps"]) == 2


# ---------------------------------------------------------------------- #
# VideoLearner orchestrator
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_learner_disabled(monkeypatch):
    from app.knowledge.learning.video_learner import VideoLearner, LearningError
    ConfigManager.load()
    ConfigManager.set("learning.enabled", False, persist=False)
    with pytest.raises(LearningError, match="disabled"):
        await VideoLearner().learn_from_url("https://youtu.be/dQw4w9WgXcQ")


@pytest.mark.asyncio
async def test_learner_missing_file():
    from app.knowledge.learning.video_learner import VideoLearner, LearningError
    ConfigManager.load()
    ConfigManager.set("learning.enabled", True, persist=False)
    with pytest.raises(LearningError, match="not found"):
        await VideoLearner().learn_from_file(Path("C:/nonexistent.mp4"))


@pytest.mark.asyncio
async def test_learner_steps_to_text():
    from app.knowledge.learning.video_learner import VideoLearner
    text = VideoLearner._steps_to_text({
        "steps": [
            {"index": 1, "action": "Open app", "tool_hint": "capcut"},
            {"index": 2, "action": "Click import", "details": "top left"},
        ]
    })
    assert "1. Open app" in text
    assert "[capcut]" in text
    assert "2. Click import" in text
    assert "top left" in text