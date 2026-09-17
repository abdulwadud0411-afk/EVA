"""
GUI theme constants (Phase 21).

Pure data — no Qt imports. Used by QSS generation and widget styling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------- #
# Colors — dark futuristic purple/blue palette
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Palette:
    # Backgrounds
    bg_deep: str = "#0f0b1e"
    bg_primary: str = "#1a1530"
    bg_secondary: str = "#241b3d"
    bg_tertiary: str = "#2e2347"
    bg_input: str = "#1e1735"

    # Foregrounds
    fg_primary: str = "#f0ecff"
    fg_secondary: str = "#b8aed4"
    fg_muted: str = "#7a6f96"
    fg_inverse: str = "#0f0b1e"

    # Accents — purple → blue gradient endpoints
    accent: str = "#8b5cf6"
    accent_alt: str = "#6366f1"
    accent_hover: str = "#a78bfa"
    accent_pressed: str = "#7c3aed"

    # Status
    success: str = "#10b981"
    warning: str = "#f59e0b"
    error: str = "#ef4444"
    info: str = "#3b82f6"

    # Voice indicators
    listening: str = "#22d3ee"
    thinking: str = "#a78bfa"
    speaking: str = "#f472b6"
    idle: str = "#6b7280"

    # Border
    border: str = "#3b2f5c"
    border_focus: str = "#8b5cf6"


PALETTE = Palette()


# ---------------------------------------------------------------------- #
# Fonts
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fonts:
    family_ui: str = "Segoe UI"
    family_mono: str = "Cascadia Code"
    size_xs: int = 10
    size_sm: int = 11
    size_md: int = 12
    size_lg: int = 14
    size_xl: int = 18
    size_title: int = 22
    weight_normal: int = 400
    weight_medium: int = 500
    weight_bold: int = 700


FONTS = Fonts()


# ---------------------------------------------------------------------- #
# Spacing & radius
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Metrics:
    radius_sm: int = 6
    radius_md: int = 12
    radius_lg: int = 18
    radius_pill: int = 999
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 20
    spacing_xl: int = 32


METRICS = Metrics()


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def as_dict() -> Dict[str, str]:
    """Return the palette as a plain dict (for QSS templating)."""
    return {f.__name__: getattr(PALETTE, f.name) for f in PALETTE.__dataclass_fields__.values()}