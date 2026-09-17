"""Tests for Phase 20 APIVault."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager
from app.security.api_vault import APIVault, VaultError


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    """Redirect vault paths into tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    ConfigManager.load()
    ConfigManager.set("app.data_dir", str(data_dir), persist=False)
    APIVault.reload()
    yield
    APIVault.reload()


def test_set_and_get():
    APIVault.set("deepseek", "sk-test-123")
    assert APIVault.get("deepseek") == "sk-test-123"


def test_overwrite():
    APIVault.set("deepseek", "old")
    APIVault.set("deepseek", "new")
    assert APIVault.get("deepseek") == "new"


def test_get_missing_returns_none():
    assert APIVault.get("nonexistent") is None


def test_delete():
    APIVault.set("openai", "sk-abc")
    assert APIVault.delete("openai") is True
    assert APIVault.get("openai") is None
    assert APIVault.delete("openai") is False


def test_list_providers():
    APIVault.set("deepseek", "a")
    APIVault.set("openai", "b")
    providers = APIVault.list_providers()
    assert "deepseek" in providers
    assert "openai" in providers


def test_persists_to_disk():
    APIVault.set("anthropic", "sk-ant-xyz")
    APIVault.reload()
    assert APIVault.get("anthropic") == "sk-ant-xyz"


def test_vault_file_is_encrypted():
    APIVault.set("deepseek", "PLAINTEXT_SECRET_12345")
    vault_file = APIVault._vault_path()
    content = vault_file.read_text(encoding="utf-8")
    # Plaintext must NOT appear in the file
    assert "PLAINTEXT_SECRET_12345" not in content
    # Encrypted token should be present
    assert "deepseek" in content


def test_empty_provider_raises():
    with pytest.raises(VaultError):
        APIVault.set("", "x")


def test_describe_shape():
    info = APIVault.describe()
    assert "available" in info
    assert "vault_path" in info
    assert "providers" in info


def test_special_chars_roundtrip():
    weird = "sk-!@#$%^&*()_+=[]{}|;':,.<>?/`~"
    APIVault.set("custom", weird)
    assert APIVault.get("custom") == weird