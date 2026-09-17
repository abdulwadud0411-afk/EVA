"""
Redactor (Phase 20).

Detects and redacts sensitive data from logs, tool results, prompts:
    - Passwords / API keys / tokens (key-based)
    - Credit card numbers
    - SSNs
    - OpenAI / Anthropic / generic bearer tokens

Public API:
    from app.security.redactor import Redactor, REDACTED
    safe = Redactor.redact({"password": "hunter2"})
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Pattern

from app.core.logger import get_logger

logger = get_logger(__name__)


_DEFAULT_SENSITIVE_KEYS = {
    "password", "passwd", "pwd",
    "secret", "token", "apikey", "api_key", "api-key",
    "auth", "authorization", "bearer",
    "creditcard", "credit_card", "cardnumber", "card_number",
    "cvv", "cvc", "ssn", "social_security",
    "private_key", "privatekey", "passphrase",
}

_DEFAULT_TEXT_PATTERNS: List[Pattern] = [
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),                     # credit card
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                        # SSN
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),                      # OpenAI
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),               # Anthropic
    re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),  # JWT
]


REDACTED = "***REDACTED***"


class Redactor:
    """Strip sensitive data from dicts and strings."""

    _sensitive_keys: set = set(_DEFAULT_SENSITIVE_KEYS)
    _text_patterns: List[Pattern] = list(_DEFAULT_TEXT_PATTERNS)

    @classmethod
    def configure(
        cls,
        sensitive_keys: List[str] = None,
        text_patterns: List[str] = None,
    ) -> None:
        if sensitive_keys is not None:
            cls._sensitive_keys = {k.lower() for k in sensitive_keys if k}
        if text_patterns is not None:
            compiled = []
            for pat in text_patterns:
                try:
                    compiled.append(re.compile(pat))
                except re.error as exc:
                    logger.warning("redactor_pattern_invalid", pattern=pat, error=str(exc))
            cls._text_patterns = compiled

    @classmethod
    def reset(cls) -> None:
        cls._sensitive_keys = set(_DEFAULT_SENSITIVE_KEYS)
        cls._text_patterns = list(_DEFAULT_TEXT_PATTERNS)

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        if not isinstance(key, str):
            return False
        k = key.lower()
        return any(s in k for s in cls._sensitive_keys)

    @classmethod
    def redact(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            out: Dict[Any, Any] = {}
            for k, v in obj.items():
                if cls._is_sensitive_key(str(k)):
                    out[k] = REDACTED
                else:
                    out[k] = cls.redact(v)
            return out
        if isinstance(obj, (list, tuple)):
            return [cls.redact(v) for v in obj]
        if isinstance(obj, str):
            return cls.redact_text(obj)
        return obj

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not isinstance(text, str) or not text:
            return text
        result = text
        for pat in cls._text_patterns:
            try:
                result = pat.sub(REDACTED, result)
            except Exception:  # noqa: BLE001
                continue
        return result

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        return {
            "sensitive_keys": sorted(cls._sensitive_keys),
            "text_patterns": [p.pattern for p in cls._text_patterns],
        }