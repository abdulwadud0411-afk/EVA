"""
Tests for Phase 10 wake word + interruption + panic.
"""
from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config_manager import ConfigManager
from app.core.events import EventBus
from app.voice.wakeword_base import (
    WakeWordDetection,
    WakeWordProvider,
    WakeWordError,
)
from app.voice.wakeword_registry import WakeWordRegistry


# ---------------------------------------------------------------------- #
# Dummy provider for tests
# ---------------------------------------------------------------------- #
class _DummyWW(WakeWordProvider):
    def __init__(self, config=None):
        self.config = config or {}
        self._trigger_next = False

    async def warm_up(self):
        return True

    async def process_chunk(self, audio_chunk):
        if self._trigger_next:
            self._trigger_next = False
            return WakeWordDetection(triggered=True, phrase="hey eva", confidence=0.9)
        return WakeWordDetection(triggered=False)

    def reset(self):
        pass

    @property
    def capabilities(self):
        return {"supports_streaming": True}


# ---------------------------------------------------------------------- #
# WakeWordRegistry
# ---------------------------------------------------------------------- #
def test_registry_register_and_list():
    WakeWordRegistry.register("dummy_ww", _DummyWW)
    assert "dummy_ww" in WakeWordRegistry.list_providers()


def test_registry_get_provider():
    WakeWordRegistry.register("dummy_ww", _DummyWW)
    provider = WakeWordRegistry.get_provider("dummy_ww")
    assert isinstance(provider, _DummyWW)


def test_registry_unknown_provider():
    from app.core.config_manager import ConfigurationError
    with pytest.raises(ConfigurationError, match="not registered"):
        WakeWordRegistry.get_provider("does_not_exist")


def test_registry_active_provider_hybrid():
    ConfigManager.load()
    ConfigManager.set("voice.wake_word.mode", "hybrid", persist=False)
    import app.voice.wakeword_providers  # noqa: F401
    try:
        p = WakeWordRegistry.get_active_provider()
        assert p.name in ("OpenWakeWordProvider", "OpenWakeWord")
    except Exception as exc:  # noqa: BLE001
        assert "not registered" in str(exc) or "openwakeword" in str(exc).lower()


# ---------------------------------------------------------------------- #
# Interruption handler
# ---------------------------------------------------------------------- #
def test_interruption_phrases_loaded():
    ConfigManager.load()
    ConfigManager.set("voice.interruption.enabled", True, persist=False)
    ConfigManager.set(
        "voice.interruption.phrases",
        ["stop", "eva stop", "be quiet"],
        persist=False,
    )
    from app.voice.interruption import InterruptionHandler
    h = InterruptionHandler()
    assert isinstance(h.phrases, list)
    joined = " ".join(h.phrases)
    assert "stop" in joined


def test_interruption_phrases_default_when_config_missing():
    """If config has no phrases, handler falls back to defaults."""
    ConfigManager.load()
    # Explicitly remove the section to test fallback
    ConfigManager._config.setdefault("voice", {}).pop("interruption", None)
    from app.voice.interruption import InterruptionHandler
    h = InterruptionHandler()
    assert "stop" in h.phrases


def test_interruption_normalize():
    from app.voice.interruption import _normalize
    assert _normalize("Hey, EVA!") == "hey eva"
    assert _normalize("  Stop!  ") == "stop"
    assert _normalize("EVA  stop.") == "eva stop"


def test_interruption_matches_phrase():
    """The matcher should trigger on a stop phrase."""
    ConfigManager.load()
    ConfigManager.set("voice.interruption.enabled", True, persist=False)
    ConfigManager.set(
        "voice.interruption.phrases",
        ["stop", "eva stop"],
        persist=False,
    )
    from app.voice.interruption import InterruptionHandler

    bus = EventBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e))

    handler = InterruptionHandler(event_bus=bus)
    handler._stt = MagicMock()

    # Bypass the file-I/O layer — mock _transcribe directly
    handler._transcribe = lambda chunk: "eva stop please"

    chunk = np.random.randint(-1000, 1000, 16000).astype(np.int16)
    handler._process_blocking(chunk)

    fired = [e for e in seen if e.type == "INTERRUPT_REQUESTED"]
    assert len(fired) == 1
    assert "stop" in fired[0].data["phrase"]


def test_interruption_no_match():
    """Phrase not present -> no event."""
    ConfigManager.load()
    ConfigManager.set("voice.interruption.enabled", True, persist=False)
    ConfigManager.set("voice.interruption.phrases", ["stop"], persist=False)
    from app.voice.interruption import InterruptionHandler

    bus = EventBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e))

    handler = InterruptionHandler(event_bus=bus)
    handler._stt = MagicMock()
    handler._transcribe = lambda chunk: "hello how are you"

    chunk = np.random.randint(-1000, 1000, 16000).astype(np.int16)
    handler._process_blocking(chunk)

    fired = [e for e in seen if e.type == "INTERRUPT_REQUESTED"]
    assert len(fired) == 0

# ---------------------------------------------------------------------- #
# Panic button
# ---------------------------------------------------------------------- #
def test_panic_hotkey_parse():
    ConfigManager.load()
    from app.voice.panic import PanicButton
    p = PanicButton()
    mods, vk = p._parse_hotkey()
    assert mods & 0x0002
    assert mods & 0x0004
    assert vk == ord("Q")


def test_panic_disabled():
    ConfigManager.load()
    ConfigManager.set("voice.panic.enabled", False, persist=False)
    from app.voice.panic import PanicButton
    p = PanicButton()
    assert p.start() is False
    assert p._running is False


def test_panic_fire_calls_callback():
    ConfigManager.load()
    fired = {"count": 0}

    def on_panic():
        fired["count"] += 1

    from app.voice.panic import PanicButton
    p = PanicButton(on_panic=on_panic)
    p._fire()
    assert fired["count"] == 1


# ---------------------------------------------------------------------- #
# WakeWordDetector
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_detector_start_stop():
    """Verify start() sets up providers and toggles is_running."""
    ConfigManager.load()
    ConfigManager.set("voice.wake_word.enabled", True, persist=False)
    ConfigManager.set("voice.wake_word.mode", "offline", persist=False)

    from app.voice.wakeword import WakeWordDetector

    # Patch the background thread's target so it doesn't spin
    with patch.object(WakeWordDetector, "_listen_loop", return_value=None):
        with patch.object(WakeWordRegistry, "get_provider",
                          return_value=_DummyWW()):
            detector = WakeWordDetector(event_bus=EventBus())
            ok = await detector.start()
            assert ok is True
            assert detector.is_running is True
            await detector.stop()
            assert detector.is_running is False


@pytest.mark.asyncio
async def test_detector_disabled():
    ConfigManager.load()
    ConfigManager.set("voice.wake_word.enabled", False, persist=False)
    from app.voice.wakeword import WakeWordDetector
    detector = WakeWordDetector()
    ok = await detector.start()
    assert ok is False


@pytest.mark.asyncio
async def test_detector_no_provider_available():
    """If both providers fail warm-up, start() returns False."""
    ConfigManager.load()
    ConfigManager.set("voice.wake_word.enabled", True, persist=False)
    ConfigManager.set("voice.wake_word.mode", "offline", persist=False)

    class _BrokenWW(WakeWordProvider):
        async def warm_up(self):
            return False
        async def process_chunk(self, audio_chunk):
            return WakeWordDetection(triggered=False)
        def reset(self):
            pass
        @property
        def capabilities(self):
            return {}

    from app.voice.wakeword import WakeWordDetector
    with patch.object(WakeWordDetector, "_listen_loop", return_value=None):
        with patch.object(WakeWordRegistry, "get_provider",
                          return_value=_BrokenWW()):
            detector = WakeWordDetector(event_bus=EventBus())
            ok = await detector.start()
            assert ok is False