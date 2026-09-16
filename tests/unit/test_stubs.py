"""Ensure Phase-1 extension points import cleanly."""
from pathlib import Path

import yaml


def test_network_protocol_imports():
    from app.network.protocol import MessageType, Envelope
    env = Envelope(type=MessageType.PING, source_device="pc-01")
    assert env.version == "1.0"
    assert env.type is MessageType.PING
    assert env.timestamp


def test_storage_module_imports():
    import app.storage  # noqa: F401


def test_default_config_has_network_and_storage_sections():
    """Validate the real config file, independent of the isolated test one."""
    real = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    data = yaml.safe_load(real.read_text(encoding="utf-8"))
    assert "network" in data and data["network"]["enabled"] is False
    assert "storage" in data
    assert data["storage"]["dedup"]["enabled"] is True
    assert data["storage"]["retention"]["protect_knowledge"] is True