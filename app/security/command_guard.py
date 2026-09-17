"""
Command Guard (Phase 19).

Classifies shell commands into:
    - ALLOWED     : safe, no confirmation needed
    - CONFIRM     : potentially destructive, needs user confirmation
    - BLOCKED     : hard-blocked (format, diskpart, ...)

Usage:
    decision = CommandGuard.check("python script.py")
    if not decision.allowed:
        raise CommandBlocked(decision.reason)
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class CommandBlocked(Exception):
    """Raised when a command is hard-blocked."""


@dataclass
class CommandDecision:
    allowed: bool                # can run without further confirmation
    requires_confirmation: bool  # can run only with user confirmation
    reason: str = ""
    matched_rule: str = ""

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "matched_rule": self.matched_rule,
        }


# ---------------------------------------------------------------------- #
# Default rules
# ---------------------------------------------------------------------- #
_DEFAULT_ALLOWLIST: List[str] = [
    "python", "python3", "pip", "pip3",
    "git",
    "dir", "ls", "cd", "mkdir", "md", "type", "cat",
    "where", "which", "whoami", "echo", "pwd",
    "copy", "cp", "move", "mv",
    "node", "npm", "npx",
    "ffmpeg", "ffprobe",
    "blender",
]

_DEFAULT_BLOCKLIST_PATTERNS: List[str] = [
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\brestart-computer\b",
    r"\breg\s+delete\b",
    r"\btakeown\b",
    r"\bicacls\b",
    r"\bcipher\b",
    r"\bdel\s+/s\b",
    r"\brmdir\s+/s\b",
    r"\brm\s+-rf\b",
    r"\bwmic\b",
    r"\bbcdedit\b",
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",
    r"\bpowershell\s+-enc\b",
    r"\bpowershell\s+-e\s+b",
    r"\biex\b",
    r"\binvoke-expression\b",
    r"\bcurl.*\|\s*(bash|sh|powershell)\b",
    r"\bwget.*\|\s*(bash|sh|powershell)\b",
]


class CommandGuard:
    _allowlist: Optional[List[str]] = None
    _blocklist: Optional[List[re.Pattern]] = None

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @classmethod
    def _load(cls) -> None:
        cfg_allow = ConfigManager.get("security.terminal.allowlist", None)
        if isinstance(cfg_allow, list) and cfg_allow:
            cls._allowlist = [str(x).lower().strip() for x in cfg_allow if str(x).strip()]
        else:
            cls._allowlist = list(_DEFAULT_ALLOWLIST)

        cfg_block = ConfigManager.get("security.terminal.blocklist", None)
        patterns: List[re.Pattern] = []
        if isinstance(cfg_block, list) and cfg_block:
            for raw in cfg_block:
                try:
                    patterns.append(re.compile(str(raw), re.IGNORECASE))
                except re.error:
                    continue
        else:
            for raw in _DEFAULT_BLOCKLIST_PATTERNS:
                try:
                    patterns.append(re.compile(raw, re.IGNORECASE))
                except re.error:
                    continue
        cls._blocklist = patterns

    @classmethod
    def reload(cls) -> None:
        cls._allowlist = None
        cls._blocklist = None

    @classmethod
    def allowlist(cls) -> List[str]:
        if cls._allowlist is None:
            cls._load()
        return list(cls._allowlist or [])

    @classmethod
    def blocklist_patterns(cls) -> List[str]:
        if cls._blocklist is None:
            cls._load()
        return [p.pattern for p in (cls._blocklist or [])]

    # ------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------ #
    @classmethod
    def check(cls, command: str) -> CommandDecision:
        """
        Classify a shell command.

        Order:
            1. If empty -> block.
            2. If blocklist pattern matches -> BLOCKED.
            3. If first word is allowlisted -> ALLOWED.
            4. Otherwise -> CONFIRM (requires user confirmation).
        """
        command = (command or "").strip()
        if not command:
            return CommandDecision(
                allowed=False,
                requires_confirmation=False,
                reason="Empty command",
                matched_rule="empty",
            )

        if cls._blocklist is None:
            cls._load()

        # Blocklist check
        for pat in cls._blocklist or []:
            if pat.search(command):
                logger.warning(
                    "command_blocked",
                    command=command[:200],
                    pattern=pat.pattern,
                )
                return CommandDecision(
                    allowed=False,
                    requires_confirmation=False,
                    reason=f"Command matches blocked pattern: {pat.pattern}",
                    matched_rule="blocklist",
                )

        # First-word allowlist check
        first_word = cls._first_word(command)
        if first_word in (cls._allowlist or []):
            return CommandDecision(
                allowed=True,
                requires_confirmation=False,
                reason="Command allowlisted",
                matched_rule="allowlist",
            )

        # Default: requires user confirmation
        return CommandDecision(
            allowed=False,
            requires_confirmation=True,
            reason=(
                f"Command '{first_word}' is not on the allowlist. "
                f"User confirmation required."
            ),
            matched_rule="unlisted",
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _first_word(command: str) -> str:
        try:
            parts = shlex.split(command, posix=False)
        except ValueError:
            parts = command.split()
        if not parts:
            return ""
        raw = parts[0].strip().strip('"').strip("'")

        # If the first token is a path (e.g. C:\Python\python.exe),
        # take only the last component (python.exe) before further
        # processing. Handles both / and \ separators.
        raw = raw.replace("/", "\\")
        if "\\" in raw:
            raw = raw.rsplit("\\", 1)[-1]

        # Strip Windows executable extensions
        for ext in (".exe", ".bat", ".cmd", ".ps1"):
            if raw.lower().endswith(ext):
                raw = raw[: -len(ext)]
                break
        return raw.lower()

    # ------------------------------------------------------------------ #
    # Description
    # ------------------------------------------------------------------ #
    @classmethod
    def describe(cls) -> dict:
        return {
            "allowlist": cls.allowlist(),
            "blocklist_patterns": cls.blocklist_patterns(),
        }