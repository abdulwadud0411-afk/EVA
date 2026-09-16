import json

from app.core.config_manager import ConfigManager
from app.core.logger import JSONLLogger, get_logger


def test_logger_writes_jsonl(tmp_path):
    ConfigManager.load()
    logger = get_logger("test")
    logger.info("hello_world", count=1)

    log_file = logger.log_file
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last["message"] == "hello_world"
    assert last["level"] == "INFO"
    assert last["fields"]["count"] == 1


def test_logger_redacts_secrets():
    ConfigManager.load()
    logger = get_logger("test")
    logger.info("attempt", api_key="SHOULD-NOT-APPEAR", token="ALSO-SECRET")

    log_file = logger.log_file
    content = log_file.read_text(encoding="utf-8")
    assert "SHOULD-NOT-APPEAR" not in content
    assert "ALSO-SECRET" not in content
    assert "***REDACTED***" in content