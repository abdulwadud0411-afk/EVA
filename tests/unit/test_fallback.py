"""Tests for Phase 18 fallback provider."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brain.fallback import FallbackProvider
from app.brain.response_models import AIResponse


class _StubProvider:
    def __init__(self, name="stub", behavior="ok"):
        self._name = name
        self._behavior = behavior
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self):
        return {"supports_tool_calling": True}

    async def validate_api_key(self):
        return True

    async def generate(self, *args, **kwargs):
        self.calls += 1
        if self._behavior == "ok":
            return AIResponse(text=f"from {self._name}", provider_name=self._name)
        if self._behavior == "rate_limit":
            raise RuntimeError("429 rate limit exceeded")
        if self._behavior == "timeout":
            raise RuntimeError("request timed out")
        if self._behavior == "network":
            raise RuntimeError("network connection error")
        if self._behavior == "server_error":
            raise RuntimeError("500 internal server error")
        if self._behavior == "bad_request":
            raise RuntimeError("400 bad request")
        if self._behavior == "auth_error":
            raise RuntimeError("401 unauthorized")
        raise RuntimeError(f"unknown behavior: {self._behavior}")


@pytest.mark.asyncio
async def test_primary_success_no_fallback():
    primary = _StubProvider(name="primary", behavior="ok")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    # Replace _get_fallback to return our stub
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    result = await fp.generate([{"role": "user", "content": "hi"}])
    assert "primary" in result.text
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_rate_limit_triggers_fallback():
    primary = _StubProvider(name="primary", behavior="rate_limit")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    result = await fp.generate([{"role": "user", "content": "hi"}])
    assert "fallback" in result.text
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_timeout_triggers_fallback():
    primary = _StubProvider(name="primary", behavior="timeout")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    result = await fp.generate([{"role": "user", "content": "hi"}])
    assert "fallback" in result.text


@pytest.mark.asyncio
async def test_network_error_triggers_fallback():
    primary = _StubProvider(name="primary", behavior="network")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    result = await fp.generate([{"role": "user", "content": "hi"}])
    assert "fallback" in result.text


@pytest.mark.asyncio
async def test_auth_error_does_not_trigger_fallback():
    """401 should NOT trigger fallback (invalid key on primary is a config error)."""
    primary = _StubProvider(name="primary", behavior="auth_error")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    with pytest.raises(RuntimeError, match="401"):
        await fp.generate([{"role": "user", "content": "hi"}])

    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_bad_request_does_not_trigger_fallback():
    primary = _StubProvider(name="primary", behavior="bad_request")
    fallback = _StubProvider(name="fallback", behavior="ok")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fallback"],
        primary_name="primary",
    )
    fp._get_fallback = lambda name: fallback if name == "fallback" else None

    with pytest.raises(RuntimeError, match="400"):
        await fp.generate([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_all_providers_fail():
    primary = _StubProvider(name="primary", behavior="rate_limit")
    fallback1 = _StubProvider(name="fb1", behavior="rate_limit")
    fallback2 = _StubProvider(name="fb2", behavior="rate_limit")

    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["fb1", "fb2"],
        primary_name="primary",
    )

    def _get(name):
        if name == "fb1": return fallback1
        if name == "fb2": return fallback2
        return None
    fp._get_fallback = _get

    with pytest.raises(RuntimeError, match="429"):
        await fp.generate([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_empty_fallback_chain():
    primary = _StubProvider(name="primary", behavior="rate_limit")
    fp = FallbackProvider(
        primary=primary,
        fallback_chain=[],
        primary_name="primary",
    )
    with pytest.raises(RuntimeError, match="429"):
        await fp.generate([{"role": "user", "content": "hi"}])


def test_fallback_skips_duplicate_primary():
    primary = _StubProvider(name="primary")
    fp = FallbackProvider(
        primary=primary,
        fallback_chain=["primary", "other"],
        primary_name="primary",
    )
    # Primary should be excluded from fallback list
    assert "primary" not in fp._fallback_names
    assert "other" in fp._fallback_names