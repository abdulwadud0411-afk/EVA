"""
Tests for app.tools.integrations.common.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.common.media_processing_tools import (
    FfmpegConvertTool,
    FfmpegExtractAudioTool,
    FfmpegTrimTool,
    FfmpegConcatTool,
    FfmpegThumbnailTool,
)
from app.tools.integrations.common.export_tools import (
    BatchConvertTool,
    VerifyOutputTool,
)
from app.tools.integrations.common.project_tools import (
    CreateProjectFolderTool,
    DuplicateAsTemplateTool,
)


def test_common_tools_registered():
    names = set(ToolRegistry.list_tools())
    for t in ("ffmpeg_convert", "ffmpeg_extract_audio", "ffmpeg_trim",
              "ffmpeg_concat", "ffmpeg_thumbnail",
              "batch_convert", "verify_output",
              "create_project_folder", "duplicate_as_template"):
        assert t in names, f"missing {t}"


# ---------------------------------------------------------------------- #
# ffmpeg_convert
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ffmpeg_convert_missing_input(tmp_path):
    tool = FfmpegConvertTool()
    r = await tool.run(input_path=str(tmp_path / "no.mp4"),
                       output_path=str(tmp_path / "out.mp4"))
    assert r.success is False


@pytest.mark.asyncio
async def test_ffmpeg_convert_success(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    dst = tmp_path / "out.mp4"

    def fake_run(*args, **kw):
        dst.write_bytes(b"converted")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=fake_run), \
         patch("app.tools.integrations.common.media_processing_tools._ffmpeg_path",
               return_value="ffmpeg"):
        r = await FfmpegConvertTool().run(
            input_path=str(src), output_path=str(dst),
        )
    assert r.success is True
    assert dst.exists()


@pytest.mark.asyncio
async def test_ffmpeg_convert_no_ffmpeg(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    dst = tmp_path / "out.mp4"
    with patch("app.tools.integrations.common.media_processing_tools._ffmpeg_path",
               return_value=None):
        r = await FfmpegConvertTool().run(
            input_path=str(src), output_path=str(dst),
        )
    assert r.success is False


# ---------------------------------------------------------------------- #
# ffmpeg_trim
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ffmpeg_trim_missing_end(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    r = await FfmpegTrimTool().run(
        input_path=str(src), output_path=str(tmp_path / "o.mp4"),
        start="0", end="",
    )
    assert r.success is False


# ---------------------------------------------------------------------- #
# ffmpeg_concat
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ffmpeg_concat_too_few_inputs(tmp_path):
    r = await FfmpegConcatTool().run(
        input_paths=[str(tmp_path / "a.mp4")],
        output_path=str(tmp_path / "out.mp4"),
    )
    assert r.success is False


# ---------------------------------------------------------------------- #
# ffmpeg_thumbnail
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ffmpeg_thumbnail_missing_input(tmp_path):
    r = await FfmpegThumbnailTool().run(
        input_path=str(tmp_path / "no.mp4"),
        output_path=str(tmp_path / "thumb.png"),
    )
    assert r.success is False


# ---------------------------------------------------------------------- #
# verify_output
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_verify_output_missing(tmp_path):
    r = await VerifyOutputTool().run(path=str(tmp_path / "no.txt"))
    assert r.success is False


@pytest.mark.asyncio
async def test_verify_output_exists(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    with patch("app.tools.integrations.common.export_tools.media_file_valid",
               return_value={"verified": True}):
        r = await VerifyOutputTool().run(path=str(f))
    assert r.success is True


# ---------------------------------------------------------------------- #
# create_project_folder
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_project_folder(tmp_path):
    r = await CreateProjectFolderTool().run(
        base_dir=str(tmp_path),
        project_name="MyProj",
        subfolders=["src", "docs", "build"],
    )
    assert r.success is True
    assert (tmp_path / "MyProj" / "src").exists()
    assert (tmp_path / "MyProj" / "docs").exists()
    assert (tmp_path / "MyProj" / "build").exists()


@pytest.mark.asyncio
async def test_create_project_folder_missing_name(tmp_path):
    r = await CreateProjectFolderTool().run(
        base_dir=str(tmp_path), project_name="",
    )
    assert r.success is False


# ---------------------------------------------------------------------- #
# duplicate_as_template
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_duplicate_as_template(tmp_path):
    tpl = tmp_path / "template"
    tpl.mkdir()
    (tpl / "file.txt").write_text("data")

    dst = tmp_path / "newproj"
    r = await DuplicateAsTemplateTool().run(
        template_dir=str(tpl), target_dir=str(dst),
    )
    assert r.success is True
    assert (dst / "file.txt").exists()


@pytest.mark.asyncio
async def test_duplicate_as_template_missing(tmp_path):
    r = await DuplicateAsTemplateTool().run(
        template_dir=str(tmp_path / "no"),
        target_dir=str(tmp_path / "dst"),
    )
    assert r.success is False


@pytest.mark.asyncio
async def test_duplicate_as_template_target_exists(tmp_path):
    src = tmp_path / "s"
    dst = tmp_path / "d"
    src.mkdir()
    dst.mkdir()
    r = await DuplicateAsTemplateTool().run(
        template_dir=str(src), target_dir=str(dst),
    )
    assert r.success is False