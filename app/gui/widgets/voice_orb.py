"""
Voice Orb (Phase 21).

The visual centerpiece — combines:
    - ParticleField (background, original ambient-dot design)
    - GlowingSphere (foreground)
    - Status label ("Listening…", "Thinking…", etc.)
    - Voice intensity hook (0.0 – 1.0)

The orb IS the primary visual feedback for what EVA is doing.

IMPORTANT: this is the widget that keeps the background turning
together with the sphere. Every tick it measures how much the
sphere's rotation_y changed since the last tick, and feeds just that
DELTA into the particle field's `set_rotation_delta()`. The particle
field's own look (drifting dots, faint constellation lines) is
untouched — it just gets an extra whole-field spin layered on top.
If you instantiate GlowingSphere / ParticleField separately anywhere
else instead of using VoiceOrb, this sync will NOT happen.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.gui.gui_state import GUIStatus
from app.gui.theme import FONTS, PALETTE
from app.gui.widgets.glowing_sphere import GlowingSphere
from app.gui.widgets.particle_field import ParticleField


class VoiceOrb(QWidget):
    """Sphere + particles + status label."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._status = GUIStatus.IDLE
        self._intensity = 0.0
        self._target_intensity = 0.0
        self._last_sphere_rot_y = 0.0

        self.setMinimumSize(340, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # Background particles (absolutely positioned via manual layout below)
        self.particles = ParticleField(count=55, parent=self)

        # Sphere — created AFTER particles so it stacks on top and
        # receives mouse events for dragging.
        self.sphere = GlowingSphere(num_points=380, parent=self)

        # Status label
        self._status_label = QLabel("Idle")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            f"color: {PALETTE.fg_secondary};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_sm}px;"
            "background: transparent;"
        )
        layout.addWidget(self._status_label)

        self._last_sphere_rot_y = self.sphere.rotation_y

        # Smooth intensity easing (also drives the rotation sync below).
        # Runs at 60fps now — matches the sphere's tick rate, so the
        # background rotation stays perfectly smooth alongside it.
        self._ease_timer = QTimer(self)
        self._ease_timer.timeout.connect(self._ease_intensity)
        self._ease_timer.start(16)

    # ------------------------------------------------------------------ #
    # Layout — overlay particles behind sphere
    # ------------------------------------------------------------------ #
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.particles.setGeometry(0, 0, w, h)
        self.sphere.setGeometry(0, 0, w, h)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def set_status(self, status: GUIStatus) -> None:
        self._status = status
        self.sphere.set_status(status)
        self.particles.set_status(status)
        self._status_label.setText(self._label_for(status))
        self._status_label.setStyleSheet(
            f"color: {self._label_color(status)};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_sm}px;"
            "background: transparent;"
        )

    def set_intensity(self, intensity: float) -> None:
        """Set target voice amplitude (eased)."""
        self._target_intensity = max(0.0, min(1.0, float(intensity)))

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _ease_intensity(self) -> None:
        # Simple exponential smoothing
        delta = self._target_intensity - self._intensity
        if abs(delta) < 0.005:
            self._intensity = self._target_intensity
        else:
            self._intensity += delta * 0.09
        self.sphere.set_intensity(self._intensity)

        # Feed only the CHANGE in rotation into the particle field, so
        # the background spins along with the sphere (auto-rotation AND
        # manual drag) without altering the particles' own design.
        current_rot_y = self.sphere.rotation_y
        dtheta = current_rot_y - self._last_sphere_rot_y
        self._last_sphere_rot_y = current_rot_y
        self.particles.set_rotation_delta(dtheta)

    def _label_for(self, status: GUIStatus) -> str:
        return {
            GUIStatus.IDLE: "Ready",
            GUIStatus.LISTENING: "Listening…",
            GUIStatus.THINKING: "Thinking…",
            GUIStatus.SPEAKING: "Speaking…",
            GUIStatus.ERROR: "Error",
        }.get(status, "Ready")

    def _label_color(self, status: GUIStatus) -> str:
        return {
            GUIStatus.IDLE: PALETTE.fg_muted,
            GUIStatus.LISTENING: PALETTE.listening,
            GUIStatus.THINKING: PALETTE.thinking,
            GUIStatus.SPEAKING: PALETTE.speaking,
            GUIStatus.ERROR: PALETTE.error,
        }.get(status, PALETTE.fg_muted)