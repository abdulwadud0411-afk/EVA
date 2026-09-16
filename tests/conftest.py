"""
Global pytest fixtures for Phase 1-12.
Ensures ConfigManager uses a temporary isolated config tree + fresh DB per test.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.core.logger import JSONLLogger


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a fresh config tree + reset ConfigManager + DB before each test."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "eva.db"

    (config_dir / "config.yaml").write_text(
        textwrap.dedent(
            f"""
            app:
              name: "EVA"
              version: "0.1.0"
              debug: false
              data_dir: "{data_dir.as_posix()}"

            ai:
              provider: "deepseek"
              history_limit: 4
              deepseek:
                base_url: "https://api.deepseek.com"
                primary_model: "deepseek-v4-flash"
                temperature: 0.2
                max_tokens: 128
                timeout_seconds: 5

            memory:
              enabled: true
              database_path: "{db_path.as_posix()}"

            voice:
              speak_responses: false
              speak_only_in_voice_mode: false
            """
        ).strip(),
        encoding="utf-8",
    )

    (config_dir / "user_config.yaml").write_text("{}", encoding="utf-8")

    for key in (
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "ELEVENLABS_API_KEY",
        "EVA_DEBUG",
        "EVA_DATA_DIR",
    ):
        monkeypatch.delenv(key, raising=False)

    ConfigManager.configure(
        project_root=tmp_path,
        config_file=config_dir / "config.yaml",
        user_config_file=config_dir / "user_config.yaml",
        env_file=tmp_path / ".env",
    )
    ConfigManager.reset()

    # Reset logger singleton
    JSONLLogger._instance = None

    # Reset memory singletons (so each test gets a fresh DB)
    try:
        from app.memory.database import Database
        Database._initialized = False
    except Exception:
        pass
    try:
        from app.memory.memory import MemoryStore
        MemoryStore.reset()
    except Exception:
        pass

    yield

    ConfigManager.reset()
    JSONLLogger._instance = None
    try:
        from app.memory.database import Database
        Database._initialized = False
    except Exception:
        pass
    try:
        from app.memory.memory import MemoryStore
        MemoryStore.reset()
    except Exception:
        pass