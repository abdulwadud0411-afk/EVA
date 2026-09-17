"""Tests for Phase 20 NetworkWhitelist."""
from __future__ import annotations

import pytest
import yaml

from app.security.network_whitelist import NetworkWhitelist, WhitelistDecision


@pytest.fixture(autouse=True)
def isolated_whitelist(tmp_path):
    cfg = tmp_path / "network_whitelist.yaml"
    cfg.write_text(
        yaml.safe_dump({
            "network": {
                "whitelist_enabled": True,
                "allow_subdomains": True,
                "block_all_others": True,
                "allowed_domains": [
                    "api.deepseek.com",
                    "api.openai.com",
                    "localhost",
                    "127.0.0.1",
                ],
                "denied_domains": ["evil.example.com"],
            }
        }),
        encoding="utf-8",
    )
    NetworkWhitelist.configure(cfg)
    NetworkWhitelist.reload()
    yield
    NetworkWhitelist.reload()


def test_allowed_exact_match():
    d = NetworkWhitelist.check("https://api.deepseek.com/v1/chat")
    assert d.allow is True
    assert d.matched_rule == "allowed"


def test_allowed_subdomain():
    d = NetworkWhitelist.check("https://stream.api.deepseek.com/v1")
    assert d.allow is True


def test_disallowed_host():
    d = NetworkWhitelist.check("https://evil.com/steal")
    assert d.allow is False
    assert d.matched_rule == "unlisted"


def test_explicitly_denied_overrides_allowed():
    # Even if allowed, denied list wins
    d = NetworkWhitelist.check("https://evil.example.com/x")
    assert d.allow is False
    assert d.matched_rule == "denied"


def test_localhost_allowed():
    assert NetworkWhitelist.check("http://localhost:8080/api").allow is True


def test_ip_address_allowed():
    assert NetworkWhitelist.check("http://127.0.0.1:11434/api").allow is True


def test_invalid_url_rejected():
    d = NetworkWhitelist.check("not a url with spaces")
    assert d.allow is False
    assert d.matched_rule in ("invalid_url", "unlisted")


def test_bare_hostname_without_scheme():
    d = NetworkWhitelist.check("api.deepseek.com")
    assert d.allow is True


def test_disabled_whitelist():
    NetworkWhitelist.configure(None)  # not effective
    NetworkWhitelist.reload()
    # Override config to disable
    import app.security.network_whitelist as nw
    original = NetworkWhitelist._load()
    original["whitelist_enabled"] = False
    NetworkWhitelist._config = original
    d = NetworkWhitelist.check("https://anything.example.com")
    assert d.allow is True
    assert d.matched_rule == "disabled"


def test_is_allowed_helper():
    assert NetworkWhitelist.is_allowed("https://api.openai.com/v1") is True
    assert NetworkWhitelist.is_allowed("https://random.com/x") is False


def test_describe_shape():
    info = NetworkWhitelist.describe()
    assert "allowed_domains" in info
    assert "api.deepseek.com" in info["allowed_domains"]


def test_decision_to_dict():
    d = WhitelistDecision(allow=True, host="api.deepseek.com", reason="ok")
    as_dict = d.to_dict()
    assert as_dict["allow"] is True
    assert as_dict["host"] == "api.deepseek.com"