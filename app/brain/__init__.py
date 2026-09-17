"""Brain: AI provider abstraction, adapters, router, and fallback."""
from app.brain.vision import VisionClient, VisionError  # noqa: F401
from app.brain.routing_rules import (  # noqa: F401
    RoutingRule,
    RoutingContext,
    RuleMatch,
    default_rules,
)
from app.brain.ai_router import AIRouter, RoutingDecision  # noqa: F401
from app.brain.fallback import FallbackProvider  # noqa: F401

__all__ = [
    "VisionClient",
    "VisionError",
    "RoutingRule",
    "RoutingContext",
    "RuleMatch",
    "default_rules",
    "AIRouter",
    "RoutingDecision",
    "FallbackProvider",
]