"""
Tests for Phase 12 persistent memory.
"""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager
from app.memory.database import Database
from app.memory.memory import MemoryStore
from app.memory.conversation_memory import ConversationMemory
from app.memory.user_memory import UserMemory
from app.memory.knowledge_memory import KnowledgeMemory
from app.memory.skill_memory import SkillMemory
from app.memory.task_history import TaskHistory


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Give every test its own empty SQLite database."""
    db_file = tmp_path / "test_eva.db"
    ConfigManager.load()
    ConfigManager.set("memory.enabled", True, persist=False)
    ConfigManager.set("memory.database_path", str(db_file), persist=False)

    Database._initialized = False
    MemoryStore.reset()

    yield

    Database._initialized = False
    MemoryStore.reset()


def test_database_init_creates_tables():
    Database.init()
    rows = Database.fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )
    names = {r["name"] for r in rows}
    for expected in (
        "conversations", "messages", "preferences",
        "knowledge_entries", "skills", "tasks", "facts",
    ):
        assert expected in names, f"missing table: {expected}"


def test_conversation_append_and_read():
    cm = ConversationMemory()
    cm.append_user("hello")
    cm.append_assistant("hi there")
    recent = cm.recent(limit=10)
    assert len(recent) == 2
    assert recent[0].role == "user"
    assert recent[0].content == "hello"
    assert recent[1].role == "assistant"


def test_conversation_tool_call_roundtrip():
    cm = ConversationMemory()
    cm.append_tool(
        "open_application",
        {"application": "chrome"},
        {"success": True},
    )
    msgs = cm.recent()
    assert msgs[0].tool_name == "open_application"
    assert msgs[0].tool_arguments == {"application": "chrome"}
    assert msgs[0].tool_result == {"success": True}


def test_conversation_count():
    cm = ConversationMemory()
    cm.append_user("a")
    cm.append_user("b")
    cm.append_user("c")
    assert cm.count() == 3


def test_conversation_recent_limit():
    cm = ConversationMemory()
    for i in range(10):
        cm.append_user(f"msg{i}")
    recent = cm.recent(limit=3)
    assert len(recent) == 3
    assert recent[-1].content == "msg9"


def test_user_set_and_get():
    um = UserMemory()
    um.set("preferred_name", "Rizvi")
    assert um.get("preferred_name") == "Rizvi"


def test_user_update():
    um = UserMemory()
    um.set("preferred_name", "Rizvi")
    um.set("preferred_name", "Rizvi Ahmed")
    assert um.get("preferred_name") == "Rizvi Ahmed"


def test_user_rejects_sensitive_key():
    um = UserMemory()
    with pytest.raises(ValueError, match="sensitive"):
        um.set("api_key", "secret123")
    with pytest.raises(ValueError):
        um.set("password", "hunter2")


def test_user_delete():
    um = UserMemory()
    um.set("hobby", "coding")
    assert um.delete("hobby") is True
    assert um.get("hobby") is None


def test_user_helpers():
    um = UserMemory()
    um.set_preferred_name("Rizvi")
    assert um.get_preferred_name() == "Rizvi"


def test_knowledge_add_and_get():
    km = KnowledgeMemory()
    entry = km.add("GTA 6 Release", "November 19, 2026", source_type="web")
    assert entry.id is not None
    fetched = km.get(entry.id)
    assert fetched.title == "GTA 6 Release"


def test_knowledge_search_text():
    km = KnowledgeMemory()
    km.add("Python basics", "Variables and functions", tags=["python"])
    km.add("JavaScript basics", "Variables and functions", tags=["javascript"])
    results = km.search_text("Python")
    assert len(results) == 1
    assert results[0].title == "Python basics"


def test_knowledge_count():
    km = KnowledgeMemory()
    km.add("a", "x")
    km.add("b", "y")
    assert km.count() == 2


def test_skills_add_and_get():
    sm = SkillMemory()
    skill = sm.add(
        "capcut_cut_video",
        description="Cut a video in CapCut",
        steps=[{"tool": "open_application", "args": {"application": "capcut"}}],
        required_tools=["open_application"],
    )
    assert skill.name == "capcut_cut_video"
    fetched = sm.get("capcut_cut_video")
    assert fetched is not None
    assert fetched.steps[0]["tool"] == "open_application"
    assert "open_application" in fetched.required_tools


def test_skills_update():
    sm = SkillMemory()
    sm.add("skill1", version="1.0.0")
    sm.add("skill1", version="1.1.0")
    fetched = sm.get("skill1")
    assert fetched.version == "1.1.0"


def test_task_lifecycle():
    th = TaskHistory()
    task = th.start("open chrome")
    assert task.status == "running"
    assert th.finish(task.id, "completed", result="ok") is True
    fetched = th.get(task.id)
    assert fetched.status == "completed"
    assert fetched.result == "ok"


def test_task_failed():
    th = TaskHistory()
    t = th.start("something")
    th.finish(t.id, "failed", result="boom")
    assert th.get(t.id).status == "failed"


def test_task_invalid_status():
    th = TaskHistory()
    t = th.start("x")
    with pytest.raises(ValueError):
        th.finish(t.id, "weird")


def test_memory_store_init_and_use():
    MemoryStore.init()
    cm = MemoryStore.conversation()
    cm.append_user("hi")

    MemoryStore.user.set("language", "en")
    assert MemoryStore.user.get("language") == "en"

    MemoryStore.knowledge.add("t", "c")
    assert MemoryStore.knowledge.count() == 1

    MemoryStore.skills.add("s")
    assert MemoryStore.skills.count() == 1

    MemoryStore.tasks.start("test task")
    assert MemoryStore.tasks.count() == 1