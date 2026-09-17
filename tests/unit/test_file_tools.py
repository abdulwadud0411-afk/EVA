"""Tests for Phase 19 file tools."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.security.path_guard import PathGuard
from app.tools.file_tools import (
    ReadFileTool, WriteFileTool, ListDirectoryTool,
    CreateFolderTool, MoveFileTool, CopyFileTool,
    DeleteFileTool, SearchFilesTool,
)


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """Point workspace to tmp_path so tests never touch real Desktop."""
    ConfigManager.load()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    ConfigManager.set("security.paths.allowed_roots", [str(tmp_path)], persist=False)
    ConfigManager.set("security.paths.blocked_roots", [], persist=False)
    PathGuard.reload()

    yield workspace_dir

    PathGuard.reload()


@pytest.mark.asyncio
async def test_write_then_read(workspace):
    target = workspace / "hello.txt"
    r1 = await WriteFileTool().run(path=str(target), content="hello world")
    assert r1.success is True
    assert r1.data["bytes_written"] == 11

    r2 = await ReadFileTool().run(path=str(target))
    assert r2.success is True
    assert r2.data["text"] == "hello world"


@pytest.mark.asyncio
async def test_write_no_overwrite(workspace):
    target = workspace / "exists.txt"
    await WriteFileTool().run(path=str(target), content="A")
    r = await WriteFileTool().run(path=str(target), content="B")
    assert r.success is False
    assert r.error["code"] == "FILE_EXISTS"


@pytest.mark.asyncio
async def test_write_overwrite_true(workspace):
    target = workspace / "over.txt"
    await WriteFileTool().run(path=str(target), content="A")
    r = await WriteFileTool().run(path=str(target), content="B", overwrite=True)
    assert r.success is True
    r2 = await ReadFileTool().run(path=str(target))
    assert r2.data["text"] == "B"


@pytest.mark.asyncio
async def test_write_outside_workspace_blocked(tmp_path):
    PathGuard.reload()
    r = await WriteFileTool().run(
        path="C:\\Windows\\System32\\evil.txt", content="x",
    )
    assert r.success is False
    assert r.error["code"] == "PATH_FORBIDDEN"


@pytest.mark.asyncio
async def test_read_missing(workspace):
    r = await ReadFileTool().run(path=str(workspace / "ghost.txt"))
    assert r.success is False
    assert r.error["code"] == "FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_directory(workspace):
    (workspace / "a.txt").write_text("a")
    (workspace / "b.txt").write_text("b")
    (workspace / "sub").mkdir()

    r = await ListDirectoryTool().run(path=str(workspace))
    assert r.success is True
    names = {i["name"] for i in r.data["items"]}
    assert "a.txt" in names
    assert "sub" in names


@pytest.mark.asyncio
async def test_list_directory_not_a_dir(workspace):
    f = workspace / "file.txt"
    f.write_text("x")
    r = await ListDirectoryTool().run(path=str(f))
    assert r.success is False
    assert r.error["code"] == "NOT_A_DIR"


@pytest.mark.asyncio
async def test_create_folder(workspace):
    target = workspace / "new" / "nested"
    r = await CreateFolderTool().run(path=str(target))
    assert r.success is True
    assert target.is_dir()


@pytest.mark.asyncio
async def test_move_file(workspace):
    src = workspace / "src.txt"
    src.write_text("data")
    dst = workspace / "moved.txt"
    r = await MoveFileTool().run(source=str(src), destination=str(dst))
    assert r.success is True
    assert dst.exists()
    assert not src.exists()


@pytest.mark.asyncio
async def test_copy_file(workspace):
    src = workspace / "src.txt"
    src.write_text("data")
    dst = workspace / "copy.txt"
    r = await CopyFileTool().run(source=str(src), destination=str(dst))
    assert r.success is True
    assert src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_delete_file(workspace):
    f = workspace / "bye.txt"
    f.write_text("x")
    r = await DeleteFileTool().run(path=str(f))
    assert r.success is True
    assert not f.exists()


@pytest.mark.asyncio
async def test_delete_folder(workspace):
    d = workspace / "folder"
    d.mkdir()
    (d / "x.txt").write_text("x")
    r = await DeleteFileTool().run(path=str(d))
    assert r.success is True
    assert not d.exists()


@pytest.mark.asyncio
async def test_search_files(workspace):
    (workspace / "one.py").write_text("x")
    (workspace / "two.py").write_text("y")
    (workspace / "readme.md").write_text("z")
    r = await SearchFilesTool().run(
        directory=str(workspace), pattern="*.py", recursive=True,
    )
    assert r.success is True
    assert r.data["count"] == 2