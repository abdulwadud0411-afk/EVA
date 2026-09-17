"""
EVA Settings module (Phase 17).

Provides:
    - Provider catalog (known AI providers + their models)
    - Settings manager (read/write provider config)
    - Connection check (validate API key + endpoint)

Public API:
    from app.settings import ProviderCatalog, SettingsManager, check_provider
"""
from app.settings.provider_catalog import ProviderCatalog, ProviderInfo  # noqa: F401
from app.settings.settings_manager import SettingsManager, SettingsError  # noqa: F401
from app.settings.test_connection import check_provider, ConnectionResult  # noqa: F401

__all__ = [
    "ProviderCatalog",
    "ProviderInfo",
    "SettingsManager",
    "SettingsError",
    "check_provider",
    "ConnectionResult",
]