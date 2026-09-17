"""Tests for Phase 18 routing rules."""
from __future__ import annotations

from app.brain.routing_rules import (
    RoutingContext,
    RoutingRule,
    compile_keyword_regex,
    default_rules,
)


def test_rule_serialization_roundtrip():
    r = RoutingRule(
        name="test",
        provider="ollama",
        model="qwen2.5:3b",
        priority=5,
        match_keywords=["hi", "hello"],
        max_length=50,
        requires_no_tools=True,
        description="test rule",
    )
    d = r.to_dict()
    r2 = RoutingRule.from_dict(d)
    assert r2.name == "test"
    assert r2.provider == "ollama"
    assert r2.match_keywords == ["hi", "hello"]
    assert r2.requires_no_tools is True


def test_matches_simple_greeting():
    rule = RoutingRule(
        name="simple",
        provider="ollama",
        max_length=40,
        match_keywords=["hi", "hello"],
        requires_no_tools=True,
    )
    ctx = RoutingContext(text="hi", has_tools=False)
    assert rule.matches(ctx) is True


def test_rejects_long_text():
    rule = RoutingRule(
        name="simple",
        provider="ollama",
        max_length=10,
        match_keywords=["hi"],
    )
    ctx = RoutingContext(text="hi " * 50)
    assert rule.matches(ctx) is False


def test_rejects_missing_keyword():
    rule = RoutingRule(
        name="coding",
        provider="deepseek",
        match_keywords=["python", "function"],
    )
    ctx = RoutingContext(text="what is the weather today?")
    assert rule.matches(ctx) is False


def test_vision_rule_requires_image():
    rule = RoutingRule(
        name="vision",
        provider="deepseek",
        requires_vision=True,
    )
    ctx_no_img = RoutingContext(text="hello")
    ctx_img = RoutingContext(text="hello", has_image=True)
    assert rule.matches(ctx_no_img) is False
    assert rule.matches(ctx_img) is True


def test_requires_tools_rejects_when_no_tools():
    rule = RoutingRule(
        name="tool_use",
        provider="deepseek",
        requires_tools=True,
    )
    ctx = RoutingContext(text="hi", has_tools=False)
    assert rule.matches(ctx) is False


def test_requires_no_tools_rejects_when_tools_present():
    rule = RoutingRule(
        name="simple",
        provider="ollama",
        requires_no_tools=True,
    )
    ctx = RoutingContext(text="hi", has_tools=True)
    assert rule.matches(ctx) is False


def test_default_rules_have_priorities():
    rules = default_rules()
    assert len(rules) >= 5
    names = [r.name for r in rules]
    assert "default" in names
    assert "vision" in names
    assert "coding" in names
    # Priorities should be unique and ordered
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities)


def test_default_rules_contain_keywords():
    rules = default_rules()
    coding_rule = next(r for r in rules if r.name == "coding")
    assert "python" in coding_rule.match_keywords
    assert "code" in coding_rule.match_keywords


def test_compile_keyword_regex_handles_special_chars():
    regex = compile_keyword_regex(["c++", "c#"])
    assert regex is not None
    assert regex.search("I love c++") is not None


def test_compile_keyword_regex_empty():
    assert compile_keyword_regex([]) is None