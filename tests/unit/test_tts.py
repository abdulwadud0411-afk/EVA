"""
Tests for Phase 9 voice output (TTS).

All heavy dependencies (edge_tts, piper) are mocked.
Playback is mocked so nothing plays during tests.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.voice.tts_base import TTSProvider, TTSError
from app.voice.tts_registry import TTSRegistry
from app.core.config_manager import ConfigManager, ConfigurationError


class _DummyTTS(TTSProvider):
    def __init__(self, config):
        self.config = config or {}
        self.synth_calls = []

    async def synthesize(self, text, output_path, language=None, **kwargs):
        Path(output_path).write_bytes(b"FAKEAUDIO")
        self.synth_calls.append({"text": text, "language": language})
        return output_path

    @property
    def capabilities(self):
        return {"supports_offline": True}

    async def warm_up(self):
        return True


# ---------------------------------------------------------------------- #
# Registry
# ---------------------------------------------------------------------- #
def test_registry_register_and_list():
    TTSRegistry.register("dummy", _DummyTTS)
    assert "dummy" in TTSRegistry.list_providers()


def test_registry_get_active():
    TTSRegistry.register("dummy", _DummyTTS)
    ConfigManager.load()
    ConfigManager.set("voice.tts.provider", "dummy", persist=False)
    provider = TTSRegistry.get_active_provider()
    assert isinstance(provider, _DummyTTS)


def test_registry_unknown_provider():
    ConfigManager.load()
    ConfigManager.set("voice.tts.provider", "not-real", persist=False)
    with pytest.raises(ConfigurationError, match="not registered"):
        TTSRegistry.get_active_provider()


# ---------------------------------------------------------------------- #
# SpeakController
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_speak_controller_success(tmp_path, monkeypatch):
    """SpeakController should call the provider and try to play audio."""
    import app.voice.tts as tts_mod

    # Config: speak_responses True, speak_only_in_voice_mode False
    ConfigManager.load()
    ConfigManager.set("voice.speak_responses", True, persist=False)
    ConfigManager.set("voice.speak_only_in_voice_mode", False, persist=False)

    # Redirect cache dir to tmp
    monkeypatch.setattr(tts_mod, "_cache_dir", lambda: tmp_path)

    dummy = _DummyTTS({})

    with patch.object(tts_mod, "_play_audio", return_value=None) as mock_play:
        controller = tts_mod.SpeakController(provider=dummy)
        ok = await controller.speak("Hello world")
    assert ok is True
    assert mock_play.called
    assert dummy.synth_calls and dummy.synth_calls[0]["text"] == "Hello world"


@pytest.mark.asyncio
async def test_speak_controller_empty_text():
    import app.voice.tts as tts_mod
    dummy = _DummyTTS({})
    controller = tts_mod.SpeakController(provider=dummy)
    ok = await controller.speak("")
    assert ok is False


@pytest.mark.asyncio
async def test_speak_controller_synth_error():
    import app.voice.tts as tts_mod

    class _Fail(_DummyTTS):
        async def synthesize(self, *a, **kw):
            raise TTSError("boom")

    controller = tts_mod.SpeakController(provider=_Fail({}))
    ok = await controller.speak("test")
    assert ok is False


# ---------------------------------------------------------------------- #
# Edge TTS adapter
# ---------------------------------------------------------------------- #
@pytest.fixture
def mock_edge(monkeypatch):
    import app.voice.tts_providers.edge_tts as et

    monkeypatch.setattr(et, "_EDGE_AVAILABLE", True)

    fake_comm = MagicMock()
    fake_comm.save = AsyncMock()

    class _FakeCommunicate:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        async def save(self, path):
            Path(path).write_bytes(b"MP3")

    fake_edge = MagicMock()
    fake_edge.Communicate = _FakeCommunicate
    fake_edge.list_voices = AsyncMock(return_value=[{"Name": "en-US-AvaNeural"}])

    monkeypatch.setattr(et, "edge_tts", fake_edge)
    return et, fake_edge


@pytest.mark.asyncio
async def test_edge_warm_up(mock_edge):
    et, _ = mock_edge
    provider = et.EdgeTTS({})
    assert await provider.warm_up() is True


@pytest.mark.asyncio
async def test_edge_synthesize_english(mock_edge, tmp_path):
    et, _ = mock_edge
    provider = et.EdgeTTS({"en_voice": "en-US-AvaNeural"})
    out = tmp_path / "out.mp3"
    result = await provider.synthesize("Hello there", str(out))
    assert Path(result).exists()


@pytest.mark.asyncio
async def test_edge_synthesize_bangla(mock_edge, tmp_path):
    et, _ = mock_edge
    provider = et.EdgeTTS({"bn_voice": "bn-BD-NabanitaNeural"})
    out = tmp_path / "out.mp3"
    result = await provider.synthesize("হ্যালো EVA", str(out), language="bn")
    assert Path(result).exists()


# ---------------------------------------------------------------------- #
# Language detection helper
# ---------------------------------------------------------------------- #
def test_detect_language_helper():
    from app.voice.tts_providers.edge_tts import _detect_language
    assert _detect_language("Hello world") == "en"
    assert _detect_language("হ্যালো") == "bn"
    assert _detect_language("Hello, কেমন আছো?") == "bn"