"""
EVA Security module (Phase 19 + Phase 20).

Provides:
    Phase 19:
        - PathGuard         : restrict file operations to allowed roots
        - CommandGuard      : allowlist/blocklist for shell commands
    Phase 20:
        - PermissionManager : per-tool/category scope checks
        - ConfirmationGate  : user confirmation for HIGH/CRITICAL
        - Redactor          : strip sensitive data from logs/args
        - APIVault          : Fernet-encrypted API key store
        - AuditLog          : HMAC-signed JSONL audit trail
        - RateLimiter       : sliding window per-tool limits
        - NetworkWhitelist  : restrict outbound host access
        - Sandbox           : restrict HIGH-risk tools for unknown tasks

Public API:
    from app.security import (
        PathGuard, PathViolation,
        CommandGuard, CommandBlocked,
        PermissionManager, PermissionDecision,
        ConfirmationGate, ConfirmationRequest,
        Redactor, REDACTED,
        APIVault, VaultError,
        AuditLog,
        RateLimiter,
        NetworkWhitelist, WhitelistDecision, NetworkBlocked,
        Sandbox, SandboxViolation,
    )
"""
from app.security.path_guard import PathGuard, PathViolation  # noqa: F401
from app.security.command_guard import CommandGuard, CommandBlocked  # noqa: F401
from app.security.permissions import (  # noqa: F401
    PermissionManager,
    PermissionDecision,
)
from app.security.confirmation import (  # noqa: F401
    ConfirmationGate,
    ConfirmationRequest,
)
from app.security.redactor import Redactor, REDACTED  # noqa: F401
from app.security.api_vault import APIVault, VaultError  # noqa: F401
from app.security.audit_log import AuditLog  # noqa: F401
from app.security.rate_limiter import RateLimiter  # noqa: F401
from app.security.network_whitelist import (  # noqa: F401
    NetworkWhitelist,
    WhitelistDecision,
    NetworkBlocked,
)
from app.security.sandbox import (  # noqa: F401
    Sandbox,
    SandboxViolation,
    SandboxState,
)

# Phase 22 — Anti-tamper / anti-debug / integrity
from app.security.anti_debug import (  # noqa: F401
    is_debugger_present,
    check as anti_debug_check,
)
from app.security.integrity_check import (  # noqa: F401
    build_manifest,
    save_manifest,
    load_manifest,
    verify as verify_integrity,
)
from app.security.anti_tamper import (  # noqa: F401
    check_all as anti_tamper_check,
    should_block as anti_tamper_should_block,
)

__all__ = [
    "PathGuard", "PathViolation",
    "CommandGuard", "CommandBlocked",
    "PermissionManager", "PermissionDecision",
    "ConfirmationGate", "ConfirmationRequest",
    "Redactor", "REDACTED",
    "APIVault", "VaultError",
    "AuditLog",
    "RateLimiter",
    "NetworkWhitelist", "WhitelistDecision", "NetworkBlocked",
    "Sandbox", "SandboxViolation", "SandboxState",
    "is_debugger_present", "anti_debug_check",
    "build_manifest", "save_manifest", "load_manifest", "verify_integrity",
    "anti_tamper_check", "anti_tamper_should_block",
]