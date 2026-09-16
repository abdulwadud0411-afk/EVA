"""
Tests for Phase 8 voice/STT system.

All heavy dependencies (sounddevice, faster_whisper) are mocked.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.voice.base import STTProvider, STTError
from app.voice.interface import TranscriptionResult
from app.voice.stt_registry import STTRegistry
from app.core.config_manager import ConfigManager, ConfigurationError


# ---------------------------------------------------------------------- #
# Dummy provider for registry tests
# ---------------------------------------------------------------------- #
class _DummySTT(STTProvider):
    def __init__(self, config):
        self.config = config

    async def transcribe(self, audio_path, language=None, **kwargs):
        return TranscriptionResult(text="hello world", language="en", confidence=0.95)

    @property
    def capabilities(self):
        return {"supports_offline": True}

    async def warm_up(self):
        return True


# ---------------------------------------------------------------------- #
# Interface tests
# ---------------------------------------------------------------------- #
def test_transcription_result_empty():
    r = TranscriptionResult(text="")
    assert r.is_empty is True
    r2 = TranscriptionResult(text="hi")
    assert r2.is_empty is False


def test_transcription_result_fields():
    r = TranscriptionResult(text="hello", language="bn", confidence=0.9, duration_seconds=2.5)
    assert r.text == "hello"
    assert r.language == "bn"
    assert r.confidence == 0.9
    assert r.duration_seconds == 2.5


# ---------------------------------------------------------------------- #
# Registry tests
# ---------------------------------------------------------------------- #
def test_registry_register_and_list():
    STTRegistry.register("dummy", _DummySTT)
    assert "dummy" in STTRegistry.list_providers()


def test_registry_get_active():
    STTRegistry.register("dummy", _DummySTT)
    ConfigManager.load()
    ConfigManager.set("voice.stt.provider", "dummy", persist=False)
    provider = STTRegistry.get_active_provider()
    assert isinstance(provider, _DummySTT)


def test_registry_unknown_provider():
    ConfigManager.load()
    ConfigManager.set("voice.stt.provider", "nope", persist=False)
    with pytest.raises(ConfigurationError, match="not registered"):
        STTRegistry.get_active_provider()


# ---------------------------------------------------------------------- #
# FasterWhisper adapter tests (mocked)
# ---------------------------------------------------------------------- #
@pytest.fixture
def mock_whisper(monkeypatch):
    import app.voice.stt_providers.faster_whisper_stt as fw

    fake_model = MagicMock()

    def _segments(**kw):
        class _Seg:
            def __init__(self, text):
                self.text = text
        return iter([_Seg("Hello "), _Seg("world")])

    fake_model.transcribe.return_value = (
        _segments(),
        MagicMock(language="en", language_probability=0.93, duration=2.2),
    )

    monkeypatch.setattr(fw, "_WHISPER_AVAILABLE", True)
    monkeypatch.setattr(fw, "WhisperModel", MagicMock(return_value=fake_model))
    return fw, fake_model


@pytest.mark.asyncio
async def test_faster_whisper_warm_up(mock_whisper):
    fw, _ = mock_whisper
    provider = fw.FasterWhisperSTT({"model": "small", "device": "cpu", "compute_type": "int8"})
    ok = await provider.warm_up()
    assert ok is True


@pytest.mark.asyncio
async def test_faster_whisper_transcribe(mock_whisper, tmp_path):
    fw, _ = mock_whisper
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    provider = fw.FasterWhisperSTT({"model": "small"})
    result = await provider.transcribe(str(audio))
    assert isinstance(result, TranscriptionResult)
    assert "Hello" in result.text
    assert result.language == "en"
    assert result.confidence == pytest.approx(0.93)


@pytest.mark.asyncio
async def test_faster_whisper_missing_file(mock_whisper):
    fw, _ = mock_whisper
    provider = fw.FasterWhisperSTT({})
    with pytest.raises(STTError, match="not found"):
        await provider.transcribe("/nonexistent/file.wav")


# ---------------------------------------------------------------------- #
# Microphone module tests
# ---------------------------------------------------------------------- #
def test_microphone_availability_flag():
    from app.voice import microphone
    assert isinstance(microphone.is_available(), bool)


def test_microphone_recording_dir(tmp_path, monkeypatch):
    from app.voice import microphone
    monkeypatch.setattr(microphone.ConfigManager, "get_data_dir", classmethod(lambda cls: tmp_path))
    d = microphone._recordings_dir()
    assert d.exists()
    assert d.name == "recordings"