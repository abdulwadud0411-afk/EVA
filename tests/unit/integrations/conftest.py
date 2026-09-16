"""
Shared fixtures for integration tests.

Ensures ConfigManager is loaded and tool registry is populated.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def ensure_config_and_tools():
    """Load config + ensure all tools are registered before each test."""
    from app.core.config_manager import ConfigManager
    from app.tools.registry import ToolRegistry

    try:
        ConfigManager.load()
    except Exception:
        pass

    # Import integrations to register everything
    import app.tools  # noqa: F401
    import app.tools.integrations  # noqa: F401

    yield