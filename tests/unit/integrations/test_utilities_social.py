"""
Tests for utilities and social_media integration groups.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.base import RiskLevel
from app.tools.permissions import PermissionManager
from app.tools.registry import ToolRegistry
from app.tools.integrations.utilities.git_tools import (
    GitCloneTool,
    GitStatusTool,
    GitCommitTool,
    GitPushTool,
    GitPullTool,
)
from app.tools.integrations.utilities.docker_tools import (
    DockerListContainersTool,
    DockerStartContainerTool,
    DockerStopContainerTool,
    DockerComposeUpTool,
    DockerComposeDownTool,
)
from app.tools.integrations.utilities.archive_tools import (
    ArchiveCompressTool,
    ArchiveExtractTool,
    ArchiveListTool,
)
from app.tools.integrations.social_media.spotify_tools import (
    SpotifyPlayPauseTool,
    SpotifyNextTool,
    SpotifyPreviousTool,
    SpotifyPlayTrackTool,
)
from app.tools.integrations.social_media.youtube_music_tools import (
    YouTubeMusicSearchTool,
    YouTubeMusicPlayTool,
)
from app.tools.integrations.social_media.telegram_tools import (
    TelegramOpenChatTool,
    TelegramSendMessageTool,
)
from app.tools.integrations.social_media.discord_tools import (
    DiscordOpenChannelTool,
    DiscordSendMessageTool,
)
from app.tools.integrations.social_media.zoom_tools import (
    ZoomStartMeetingTool,
    ZoomJoinMeetingTool,
)
from app.tools.integrations.social_media.whatsapp_tools import (
    WhatsAppOpenChatTool,
    WhatsAppSendMessageTool,
)
from app.tools.integrations.social_media.facebook_tools import (
    FacebookOpenMessengerTool,
    FacebookSendMessageTool,
)
from app.tools.integrations.social_media.instagram_tools import (
    InstagramOpenTool,
    InstagramOpenProfileTool,
)


# ---------------------------------------------------------------------- #
# Auto-confirm HIGH risk actions during tests
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def auto_approve_permissions():
    async def approve(title, message, risk):
        return True

    PermissionManager.set_confirmer(approve)
    yield
    PermissionManager.reset_confirmer()


def test_utilities_social_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        # Git
        "git_clone", "git_status", "git_commit", "git_push", "git_pull",
        # Docker
        "docker_list_containers", "docker_start_container",
        "docker_stop_container", "docker_compose_up", "docker_compose_down",
        # Archive
        "archive_compress", "archive_extract", "archive_list",
        # Spotify
        "spotify_play_pause", "spotify_next", "spotify_previous",
        "spotify_play_track",
        # YouTube Music
        "youtube_music_search", "youtube_music_play",
        # Telegram
        "telegram_open_chat", "telegram_send_message",
        # Discord
        "discord_open_channel", "discord_send_message",
        # Zoom
        "zoom_start_meeting", "zoom_join_meeting",
        # WhatsApp
        "whatsapp_open_chat", "whatsapp_send_message",
        # Facebook
        "facebook_open_messenger", "facebook_send_message",
        # Instagram
        "instagram_open", "instagram_open_profile",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# Git
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_git_clone_missing_url():
    r = await GitCloneTool().run(repo_url="", target_dir="/tmp/x")
    assert r.success is False


@pytest.mark.asyncio
async def test_git_status_missing_repo(tmp_path):
    r = await GitStatusTool().run(repo_dir=str(tmp_path / "nonexistent"))
    assert r.success is False


@pytest.mark.asyncio
async def test_git_commit_missing_args():
    r = await GitCommitTool().run(repo_dir=".", message="")
    assert r.success is False


@pytest.mark.asyncio
async def test_git_push_missing_repo(tmp_path):
    r = await GitPushTool().run(repo_dir=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_git_pull_missing_repo(tmp_path):
    r = await GitPullTool().run(repo_dir=str(tmp_path / "no"))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Docker
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_docker_list_offline():
    with patch("subprocess.run", side_effect=Exception("no docker")):
        r = await DockerListContainersTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_docker_start_missing_container():
    r = await DockerStartContainerTool().run(container="")
    assert r.success is False


@pytest.mark.asyncio
async def test_docker_stop_missing_container():
    r = await DockerStopContainerTool().run(container="")
    assert r.success is False


@pytest.mark.asyncio
async def test_docker_compose_up_missing_project(tmp_path):
    r = await DockerComposeUpTool().run(
        project_dir=str(tmp_path / "no"))
    assert r.success is False


@pytest.mark.asyncio
async def test_docker_compose_down_missing_project(tmp_path):
    r = await DockerComposeDownTool().run(
        project_dir=str(tmp_path / "no"))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Archive
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_archive_compress_zip(tmp_path):
    src = tmp_path / "data.txt"
    src.write_text("hello world")
    out = tmp_path / "out.zip"
    r = await ArchiveCompressTool().run(
        source=str(src), output=str(out), format="zip")
    assert r.success is True
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        assert "data.txt" in zf.namelist()


@pytest.mark.asyncio
async def test_archive_compress_missing_source(tmp_path):
    r = await ArchiveCompressTool().run(
        source=str(tmp_path / "no.txt"),
        output=str(tmp_path / "out.zip"),
    )
    assert r.success is False


@pytest.mark.asyncio
async def test_archive_extract_zip(tmp_path):
    src = tmp_path / "s"
    src.mkdir()
    (src / "a.txt").write_text("x")
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(src / "a.txt", "a.txt")

    dest = tmp_path / "out"
    r = await ArchiveExtractTool().run(
        archive_path=str(archive), output_dir=str(dest))
    assert r.success is True
    assert (dest / "a.txt").exists()


@pytest.mark.asyncio
async def test_archive_extract_missing(tmp_path):
    r = await ArchiveExtractTool().run(
        archive_path=str(tmp_path / "no.zip"),
        output_dir=str(tmp_path / "out"),
    )
    assert r.success is False


@pytest.mark.asyncio
async def test_archive_list_zip(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("f1.txt", "x")
        zf.writestr("f2.txt", "y")
    r = await ArchiveListTool().run(archive_path=str(archive))
    assert r.success is True
    assert r.data["count"] == 2


# ---------------------------------------------------------------------- #
# Spotify
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_spotify_play_pause_success():
    with patch("app.tools.integrations.social_media.spotify_tools._press_media_key"):
        r = await SpotifyPlayPauseTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_spotify_next_success():
    with patch("app.tools.integrations.social_media.spotify_tools._press_media_key"):
        r = await SpotifyNextTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_spotify_previous_success():
    with patch("app.tools.integrations.social_media.spotify_tools._press_media_key"):
        r = await SpotifyPreviousTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_spotify_play_track_missing_query():
    r = await SpotifyPlayTrackTool().run(query="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# YouTube Music
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_youtube_music_search_missing_query():
    r = await YouTubeMusicSearchTool().run(query="")
    assert r.success is False


@pytest.mark.asyncio
async def test_youtube_music_play_missing_query():
    r = await YouTubeMusicPlayTool().run(query="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Telegram
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_telegram_open_chat_success():
    with patch("subprocess.Popen"):
        r = await TelegramOpenChatTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_telegram_send_message_missing_text():
    r = await TelegramSendMessageTool().run(text="")
    assert r.success is False


@pytest.mark.asyncio
async def test_telegram_send_message_no_token_opens_app(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with patch("subprocess.Popen"), patch("time.sleep"):
        r = await TelegramSendMessageTool().run(text="hello")
    assert r.success is True
    assert r.data["via"] == "desktop_app"


# ---------------------------------------------------------------------- #
# Discord
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_discord_open_channel_success():
    with patch("subprocess.Popen"):
        r = await DiscordOpenChannelTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_discord_send_message_missing_text():
    r = await DiscordSendMessageTool().run(text="")
    assert r.success is False


@pytest.mark.asyncio
async def test_discord_send_message_no_webhook(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    r = await DiscordSendMessageTool().run(text="hello")
    assert r.success is False
    assert r.error["code"] == "NO_WEBHOOK"


# ---------------------------------------------------------------------- #
# Zoom
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_zoom_start_meeting():
    with patch("subprocess.Popen"), patch("time.sleep"):
        r = await ZoomStartMeetingTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_zoom_join_meeting_missing_id():
    r = await ZoomJoinMeetingTool().run(meeting_id="")
    assert r.success is False


@pytest.mark.asyncio
async def test_zoom_join_meeting_success():
    with patch("subprocess.Popen"), patch("time.sleep"):
        r = await ZoomJoinMeetingTool().run(meeting_id="1234567890")
    assert r.success is True


# ---------------------------------------------------------------------- #
# WhatsApp
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_whatsapp_open_chat():
    from app.tools.registry import ToolRegistry as TR
    fake = MagicMock()
    fake.success = True
    fake.error = None
    with patch.object(TR, "execute", return_value=fake):
        r = await WhatsAppOpenChatTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_whatsapp_send_message_missing_args():
    r = await WhatsAppSendMessageTool().run(phone="", message="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Facebook
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_facebook_open_messenger():
    from app.tools.registry import ToolRegistry as TR
    fake = MagicMock()
    fake.success = True
    fake.error = None
    with patch.object(TR, "execute", return_value=fake):
        r = await FacebookOpenMessengerTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_facebook_send_message_missing_text():
    r = await FacebookSendMessageTool().run(message="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# Instagram
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_instagram_open():
    from app.tools.registry import ToolRegistry as TR
    fake = MagicMock()
    fake.success = True
    fake.error = None
    with patch.object(TR, "execute", return_value=fake):
        r = await InstagramOpenTool().run()
    assert r.success is True


@pytest.mark.asyncio
async def test_instagram_open_profile_missing():
    r = await InstagramOpenProfileTool().run(username="")
    assert r.success is False