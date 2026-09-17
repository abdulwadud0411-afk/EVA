"""Tests for Phase 20 RateLimiter."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.security.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def reset_limiter():
    RateLimiter.configure(enabled=True, default_per_minute=30, per_tool={})
    RateLimiter.reset()
    yield
    RateLimiter.reset()
    RateLimiter.configure(enabled=True, default_per_minute=30, per_tool={})


def test_allow_under_limit():
    for _ in range(5):
        assert RateLimiter.allow("test_tool") is True


def test_block_over_limit():
    RateLimiter.configure(enabled=True, default_per_minute=3, per_tool={})
    assert RateLimiter.allow("t") is True
    assert RateLimiter.allow("t") is True
    assert RateLimiter.allow("t") is True
    assert RateLimiter.allow("t") is False
    assert RateLimiter.allow("t") is False


def test_per_tool_override():
    RateLimiter.configure(
        enabled=True, default_per_minute=30,
        per_tool={"delete_file": 2},
    )
    assert RateLimiter.allow("delete_file") is True
    assert RateLimiter.allow("delete_file") is True
    assert RateLimiter.allow("delete_file") is False
    # Other tools still have higher limit
    assert RateLimiter.allow("write_file") is True


def test_disabled_allows_everything():
    RateLimiter.configure(enabled=False, default_per_minute=1, per_tool={})
    for _ in range(100):
        assert RateLimiter.allow("any") is True


def test_window_slides():
    RateLimiter.configure(enabled=True, default_per_minute=2, per_tool={})
    assert RateLimiter.allow("t") is True
    assert RateLimiter.allow("t") is True
    assert RateLimiter.allow("t") is False

    # Simulate old timestamps expired
    with RateLimiter._lock:
        old_time = time.time() - 120
        RateLimiter._windows["t"].clear()
        RateLimiter._windows["t"].append(old_time)

    assert RateLimiter.allow("t") is True


def test_separate_tools_have_separate_windows():
    RateLimiter.configure(enabled=True, default_per_minute=1, per_tool={})
    assert RateLimiter.allow("tool_a") is True
    assert RateLimiter.allow("tool_a") is False
    assert RateLimiter.allow("tool_b") is True
    assert RateLimiter.allow("tool_b") is False


def test_reset_specific_tool():
    RateLimiter.configure(enabled=True, default_per_minute=1, per_tool={})
    RateLimiter.allow("a")
    RateLimiter.allow("b")
    assert RateLimiter.allow("a") is False
    RateLimiter.reset("a")
    assert RateLimiter.allow("a") is True
    assert RateLimiter.allow("b") is False


def test_reset_all():
    RateLimiter.configure(enabled=True, default_per_minute=1, per_tool={})
    RateLimiter.allow("a")
    RateLimiter.allow("b")
    RateLimiter.reset()
    assert RateLimiter.allow("a") is True
    assert RateLimiter.allow("b") is True


def test_stats():
    RateLimiter.configure(enabled=True, default_per_minute=10, per_tool={})
    RateLimiter.allow("test_tool")
    RateLimiter.allow("test_tool")
    stats = RateLimiter.stats()
    assert "test_tool" in stats
    assert stats["test_tool"]["count"] == 2
    assert stats["test_tool"]["limit"] == 10