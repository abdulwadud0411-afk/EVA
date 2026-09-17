"""Tests for Phase 21 GlowingSphere / ParticleField / VoiceOrb.

Rendering is not directly testable, but the pure logic is.
"""
from __future__ import annotations

import math

import pytest

from app.gui.gui_state import GUIStatus


# ---------------------------------------------------------------------- #
# Fibonacci sphere distribution (pure math, no Qt)
# ---------------------------------------------------------------------- #
def test_fibonacci_sphere_returns_requested_count():
    from app.gui.widgets.glowing_sphere import _fibonacci_sphere
    pts = _fibonacci_sphere(50)
    assert len(pts) == 50


def test_fibonacci_sphere_points_are_unit_vectors():
    from app.gui.widgets.glowing_sphere import _fibonacci_sphere
    pts = _fibonacci_sphere(80)
    for p in pts:
        r = math.sqrt(p.x**2 + p.y**2 + p.z**2)
        assert abs(r - 1.0) < 0.01


def test_fibonacci_sphere_zero_points():
    from app.gui.widgets.glowing_sphere import _fibonacci_sphere
    assert _fibonacci_sphere(0) == []


def test_fibonacci_sphere_points_are_distinct():
    from app.gui.widgets.glowing_sphere import _fibonacci_sphere
    pts = _fibonacci_sphere(30)
    coords = {(round(p.x, 4), round(p.y, 4), round(p.z, 4)) for p in pts}
    # No duplicates
    assert len(coords) == len(pts)


# ---------------------------------------------------------------------- #
# Qt-dependent tests (skipped if no QApplication can be created)
# ---------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_glowing_sphere_initial_status(qapp):
    from app.gui.widgets.glowing_sphere import GlowingSphere
    s = GlowingSphere(num_points=20)
    assert s._status == GUIStatus.IDLE


def test_glowing_sphere_set_status(qapp):
    from app.gui.widgets.glowing_sphere import GlowingSphere
    s = GlowingSphere(num_points=20)
    s.set_status(GUIStatus.LISTENING)
    assert s._status == GUIStatus.LISTENING
    s.set_status(GUIStatus.SPEAKING)
    assert s._status == GUIStatus.SPEAKING


def test_glowing_sphere_intensity_clamps(qapp):
    from app.gui.widgets.glowing_sphere import GlowingSphere
    s = GlowingSphere(num_points=20)
    s.set_intensity(1.5)
    assert s._intensity == 1.0
    s.set_intensity(-0.4)
    assert s._intensity == 0.0


def test_glowing_sphere_rotation_speed_varies(qapp):
    from app.gui.widgets.glowing_sphere import GlowingSphere
    s = GlowingSphere(num_points=20)
    s.set_status(GUIStatus.IDLE)
    idle_speed = s._rotation_speed()
    s.set_status(GUIStatus.LISTENING)
    listen_speed = s._rotation_speed()
    assert listen_speed > idle_speed


def test_voice_orb_label_changes(qapp):
    from app.gui.widgets.voice_orb import VoiceOrb
    orb = VoiceOrb()
    orb.set_status(GUIStatus.IDLE)
    assert orb._status_label.text() == "Ready"
    orb.set_status(GUIStatus.LISTENING)
    assert "Listening" in orb._status_label.text()
    orb.set_status(GUIStatus.THINKING)
    assert "Thinking" in orb._status_label.text()
    orb.set_status(GUIStatus.SPEAKING)
    assert "Speaking" in orb._status_label.text()


def test_voice_orb_intensity_clamps(qapp):
    from app.gui.widgets.voice_orb import VoiceOrb
    orb = VoiceOrb()
    orb.set_intensity(2.0)
    assert orb._target_intensity == 1.0
    orb.set_intensity(-1.0)
    assert orb._target_intensity == 0.0


def test_particle_field_initial_state(qapp):
    from app.gui.widgets.particle_field import ParticleField
    pf = ParticleField(count=10)
    pf.set_status(GUIStatus.LISTENING)
    assert pf._status == GUIStatus.LISTENING