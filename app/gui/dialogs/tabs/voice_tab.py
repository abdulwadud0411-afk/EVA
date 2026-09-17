"""
Voice tab (Phase 21 Batch 3).

STT/TTS provider, voice model, language, speed.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.core.config_manager import ConfigManager


class VoiceTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Voice")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # STT
        self._stt_provider = QComboBox()
        self._stt_provider.addItems(["faster-whisper", "openai"])
        form.addRow("STT Provider:", self._stt_provider)

        self._stt_model = QComboBox()
        self._stt_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        form.addRow("STT Model:", self._stt_model)

        # TTS
        self._tts_provider = QComboBox()
        self._tts_provider.addItems(["edge", "piper", "openai", "elevenlabs"])
        form.addRow("TTS Provider:", self._tts_provider)

        self._voice_id = QLineEdit()
        self._voice_id.setPlaceholderText("e.g. en-US-AvaNeural / bn-BD-NabanitaNeural")
        form.addRow("Voice ID/Model:", self._voice_id)

        # Language
        self._language = QComboBox()
        self._language.addItems(["auto", "en", "bn", "hi"])
        form.addRow("Language:", self._language)

        # Speed
        self._speed = QSlider(Qt.Horizontal)
        self._speed.setRange(50, 200)
        self._speed.setValue(100)
        self._speed_label = QLabel("1.00x")
        self._speed.valueChanged.connect(
            lambda v: self._speed_label.setText(f"{v / 100.0:.2f}x")
        )
        speed_row = QHBoxLayout()
        speed_row.addWidget(self._speed, 1)
        speed_row.addWidget(self._speed_label)
        form.addRow("Speed:", speed_row)

        layout.addLayout(form)

        row = QHBoxLayout()
        self._test_btn = QPushButton("Test Voice")
        row.addWidget(self._test_btn)
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.clicked.connect(self._on_save)
        row.addWidget(self._save_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        layout.addWidget(self._status)
        layout.addStretch(1)

    def _load_current(self) -> None:
        try:
            stt_p = ConfigManager.get("voice.stt.provider", "faster-whisper")
            idx = self._stt_provider.findText(stt_p)
            if idx >= 0:
                self._stt_provider.setCurrentIndex(idx)

            stt_m = ConfigManager.get(
                "voice.stt.faster_whisper.model",
                ConfigManager.get("voice.stt.model", "small"),
            )
            idx = self._stt_model.findText(stt_m)
            if idx >= 0:
                self._stt_model.setCurrentIndex(idx)

            tts_p = ConfigManager.get("voice.tts.provider", "edge")
            idx = self._tts_provider.findText(tts_p)
            if idx >= 0:
                self._tts_provider.setCurrentIndex(idx)

            lang = ConfigManager.get("voice.tts.language", "auto")
            idx = self._language.findText(lang)
            if idx >= 0:
                self._language.setCurrentIndex(idx)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Load failed: {exc}")

    def _on_save(self) -> None:
        try:
            ConfigManager.set("voice.stt.provider", self._stt_provider.currentText())
            ConfigManager.set(
                "voice.stt.faster_whisper.model", self._stt_model.currentText(),
            )
            ConfigManager.set("voice.tts.provider", self._tts_provider.currentText())
            ConfigManager.set("voice.tts.language", self._language.currentText())
            ConfigManager.set("voice.tts.speed", self._speed.value() / 100.0)
            self._status.setText("✅ Voice settings saved.")
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ Save failed: {exc}")