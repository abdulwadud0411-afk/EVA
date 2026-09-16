"""Tests for local intent matcher (Optimization Patch)."""
from __future__ import annotations

import pytest

from app.agent.local_intent import match_local


def test_open_youtube():
    r = match_local("open youtube")
    assert r.matched is True
    assert r.tool_name == "open_url"
    assert "youtube.com" in r.arguments["url"]


def test_open_notepad():
    r = match_local("open notepad")
    assert r.matched is True
    assert r.tool_name == "open_application"
    assert r.arguments["application"] == "notepad"


def test_open_chrome_with_prefix():
    r = match_local("EVA, open Chrome")
    assert r.matched is True
    assert r.tool_name == "open_application"
    assert r.arguments["application"] == "chrome"


def test_open_direct_url():
    r = match_local("go to https://example.com")
    assert r.matched is True
    assert r.tool_name == "open_url"
    assert r.arguments["url"] == "https://example.com"


def test_volume_up():
    r = match_local("volume up")
    assert r.matched is True
    assert r.tool_name == "volume_up"


def test_volume_down():
    r = match_local("decrease volume")
    assert r.matched is True
    assert r.tool_name == "volume_down"


def test_mute_toggle():
    r = match_local("mute")
    assert r.matched is True
    assert r.tool_name == "mute"


def test_screenshot():
    r = match_local("take a screenshot")
    assert r.matched is True
    assert r.tool_name == "take_screenshot"


def test_media_play_pause():
    r = match_local("play")
    assert r.matched is True
    assert r.tool_name == "media_control"
    assert r.arguments["action"] == "play_pause"


def test_media_next():
    r = match_local("next track")
    assert r.matched is True
    assert r.arguments["action"] == "next"


def test_minimize_window():
    r = match_local("minimize notepad")
    assert r.matched is True
    assert r.tool_name == "minimize_window"
    assert r.arguments["title"] == "notepad"


def test_maximize_window():
    r = match_local("maximize chrome")
    assert r.matched is True
    assert r.tool_name == "maximize_window"


def test_get_active_window():
    r = match_local("what window is active?")
    assert r.matched is True
    assert r.tool_name == "get_active_window"


def test_get_clipboard():
    r = match_local("what's in my clipboard")
    assert r.matched is True
    assert r.tool_name == "get_clipboard_text"


def test_greeting():
    r = match_local("hello")
    assert r.matched is True
    assert r.direct_response is not None
    assert "hello" in r.direct_response.lower()


def test_how_are_you():
    r = match_local("how are you?")
    assert r.matched is True
    assert r.direct_response is not None


def test_bangla_greeting():
    r = match_local("হ্যালো")
    assert r.matched is True


def test_complex_command_not_matched():
    r = match_local("design a Python calculator and save it to desktop")
    assert r.matched is False


def test_empty_input():
    r = match_local("")
    assert r.matched is False


def test_unknown_command_not_matched():
    r = match_local("what is the capital of France?")
    assert r.matched is False