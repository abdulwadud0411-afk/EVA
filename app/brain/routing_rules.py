"""
Routing rules (Phase 18).

A rule decides which provider + model should handle a request.

Rules are matched in priority order. First match wins.

Built-in rule kinds:
    - "simple"    : short + greeting → cheap/local
    - "vision"    : has image → vision model
    - "coding"    : code keywords → reasoning model
    - "reasoning" : long + reasoning keywords → reasoning model
    - "default"   : catch-all

Add custom rules via config.yaml under ai.routing.rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RoutingContext:
    """Info about a request that rules can inspect."""
    text: str = ""
    has_tools: bool = False
    has_image: bool = False
    message_count: int = 0
    history_tokens: int = 0
    explicit_provider: Optional[str] = None  # user override
    explicit_model: Optional[str] = None


@dataclass
class RuleMatch:
    """A matched rule's target."""
    rule_name: str
    provider: str
    model: str = ""
    reasoning: str = ""


@dataclass
class RoutingRule:
    name: str
    provider: str
    model: str = ""
    priority: int = 100
    match_keywords: List[str] = field(default_factory=list)
    max_length: int = 0          # 0 = ignore
    min_length: int = 0          # 0 = ignore
    requires_tools: bool = False
    requires_vision: bool = False
    requires_no_tools: bool = False
    description: str = ""

    # ------------------------------------------------------------------ #
    # Matching
    # ------------------------------------------------------------------ #
    def matches(self, ctx: RoutingContext) -> bool:
        """Return True if this rule applies to the given context."""
        # Tool requirements
        if self.requires_tools and not ctx.has_tools:
            return False
        if self.requires_no_tools and ctx.has_tools:
            return False
        if self.requires_vision and not ctx.has_image:
            return False

        # Length checks
        text_len = len(ctx.text.strip())
        if self.max_length > 0 and text_len > self.max_length:
            return False
        if self.min_length > 0 and text_len < self.min_length:
            return False

        # Keyword check (any match)
        if self.match_keywords:
            low = ctx.text.lower()
            if not any(kw.lower() in low for kw in self.match_keywords):
                return False

        return True

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingRule":
        return cls(
            name=str(data.get("name", "unnamed")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            priority=int(data.get("priority", 100)),
            match_keywords=list(data.get("match_keywords") or []),
            max_length=int(data.get("max_length", 0) or 0),
            min_length=int(data.get("min_length", 0) or 0),
            requires_tools=bool(data.get("requires_tools", False)),
            requires_vision=bool(data.get("requires_vision", False)),
            requires_no_tools=bool(data.get("requires_no_tools", False)),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "priority": self.priority,
            "match_keywords": self.match_keywords,
            "max_length": self.max_length,
            "min_length": self.min_length,
            "requires_tools": self.requires_tools,
            "requires_vision": self.requires_vision,
            "requires_no_tools": self.requires_no_tools,
            "description": self.description,
        }


# ---------------------------------------------------------------------- #
# Built-in rule presets
# ---------------------------------------------------------------------- #
_GREETING_KEYWORDS = [
    "hi", "hello", "hey", "yo", "sup", "thanks", "thank you",
    "হ্যালো", "হাই", "নমস্কার",
]

_CODING_KEYWORDS = [
    "code", "function", "class", "bug", "debug", "error", "traceback",
    "python", "javascript", "java", "c++", "rust", "golang",
    "script", "algorithm", "compile", "syntax", "regex",
    "refactor", "implement", "api", "endpoint",
]

_REASONING_KEYWORDS = [
    "explain", "why", "how does", "analyze", "compare", "contrast",
    "evaluate", "reasoning", "step by step", "in detail", "in depth",
    "logic", "prove", "derive", "theorem", "philosophy",
]


def default_rules(
    primary_provider: str = "deepseek",
    primary_model: str = "deepseek-v4-flash",
    reasoning_model: str = "deepseek-v4-pro",
    vision_model: str = "deepseek-v4-flash-vision-exp",
    local_provider: str = "ollama",
    local_model: str = "qwen2.5:3b",
) -> List[RoutingRule]:
    """Return the default built-in rule set."""
    return [
        # Explicit override rule (highest priority)
        RoutingRule(
            name="explicit_override",
            provider="",   # filled at match-time from ctx.explicit_provider
            model="",
            priority=1,
            description="User-specified provider/model override.",
        ),
        # Vision
        RoutingRule(
            name="vision",
            provider=primary_provider,
            model=vision_model,
            priority=10,
            requires_vision=True,
            description="Requests containing an image / screenshot.",
        ),
        # Simple / greeting → local
        RoutingRule(
            name="simple",
            provider=local_provider,
            model=local_model,
            priority=20,
            max_length=40,
            match_keywords=_GREETING_KEYWORDS,
            requires_no_tools=True,
            description="Short greetings handled by local model.",
        ),
        # Coding → reasoning
        RoutingRule(
            name="coding",
            provider=primary_provider,
            model=reasoning_model,
            priority=30,
            match_keywords=_CODING_KEYWORDS,
            description="Coding questions handled by reasoning model.",
        ),
        # Reasoning → reasoning
        RoutingRule(
            name="reasoning",
            provider=primary_provider,
            model=reasoning_model,
            priority=40,
            match_keywords=_REASONING_KEYWORDS,
            description="Complex reasoning handled by reasoning model.",
        ),
        # Default
        RoutingRule(
            name="default",
            provider=primary_provider,
            model=primary_model,
            priority=1000,
            description="Fallback: use the default primary model.",
        ),
    ]


def compile_keyword_regex(keywords: List[str]) -> Optional[re.Pattern]:
    """
    Helper: build a single regex from a keyword list.

    - Pure alphanumeric keywords get word boundaries (`\\b`).
    - Keywords with special chars (c++, c#, .net) are matched as
      escaped substrings (word boundary would fail after '+').
    """
    if not keywords:
        return None

    parts: List[str] = []
    for kw in keywords:
        esc = re.escape(kw)
        if re.match(r"^[A-Za-z0-9_]+$", kw):
            parts.append(rf"\b{esc}\b")
        else:
            parts.append(esc)

    return re.compile("(?:" + "|".join(parts) + ")", re.IGNORECASE)