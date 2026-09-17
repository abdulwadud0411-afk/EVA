"""
First-run setup wizard (Phase 22).

A polished, professional setup dialog shown the first time EVA runs.

Design:
    - Large 720x620 card layout
    - EVA logo + welcome header
    - Provider dropdown (ALL providers from catalog)
    - Model dropdown (auto-updates per provider)
    - API key field (masked)
    - "Test Connection" button
    - "Save & Launch" primary button
    - Live status area

Public API:
    wizard = SetupWizard()
    if wizard.exec() == QDialog.Accepted:
        # proceed
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.core.paths import get_app_root, get_user_env_path, get_data_dir
from app.settings.provider_catalog import ProviderCatalog

logger = get_logger(__name__)


# ====================================================================== #
# Color tokens (matches main GUI theme)
# ====================================================================== #
BG_DEEP = "#0f0b1e"
BG_PANEL = "#1a1530"
BG_INPUT = "#241b3d"
BORDER = "#3b2f5c"
BORDER_FOCUS = "#8b5cf6"
FG_PRIMARY = "#f0ecff"
FG_SECONDARY = "#b8aed4"
FG_MUTED = "#7a6f96"
ACCENT = "#8b5cf6"
ACCENT_HOVER = "#a78bfa"
ACCENT_PRESSED = "#7c3aed"
SUCCESS = "#10b981"
WARNING = "#f59e0b"
ERROR = "#ef4444"


class SetupWizard(QDialog):
    """First-run setup dialog — professional redesign."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EVA — Welcome")
        self.setMinimumSize(720, 620)
        self.setStyleSheet(self._global_stylesheet())
        self._build_ui()
        self._populate_providers()

    # ------------------------------------------------------------------ #
    # Stylesheet
    # ------------------------------------------------------------------ #
    @staticmethod
    def _global_stylesheet() -> str:
        return f"""
        QDialog {{
            background-color: {BG_DEEP};
        }}
        QLabel {{
            color: {FG_PRIMARY};
            background: transparent;
        }}
        QLabel#EvaTitle {{
            color: {FG_PRIMARY};
            font-size: 28px;
            font-weight: 700;
        }}
        QLabel#EvaSubtitle {{
            color: {FG_SECONDARY};
            font-size: 13px;
        }}
        QLabel#SectionLabel {{
            color: {FG_SECONDARY};
            font-size: 11px;
            font-weight: 600;
        }}
        QLabel#FieldLabel {{
            color: {FG_SECONDARY};
            font-size: 12px;
            font-weight: 600;
        }}
        QLabel#HintText {{
            color: {FG_MUTED};
            font-size: 11px;
        }}
        QLabel#StatusText {{
            color: {FG_SECONDARY};
            font-size: 12px;
        }}

        QFrame#Card {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        QComboBox, QLineEdit {{
            background-color: {BG_INPUT};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13px;
            min-height: 20px;
        }}
        QComboBox:hover, QLineEdit:hover {{
            border: 1px solid {BORDER_FOCUS};
        }}
        QComboBox:focus, QLineEdit:focus {{
            border: 1px solid {BORDER_FOCUS};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {FG_SECONDARY};
            margin-right: 10px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {BG_PANEL};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            selection-background-color: {ACCENT};
            selection-color: white;
            padding: 4px;
            outline: none;
        }}

        QPushButton#SecondaryButton {{
            background-color: {BG_INPUT};
            color: {FG_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 12px 22px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#SecondaryButton:hover {{
            background-color: {BG_PANEL};
            border: 1px solid {BORDER_FOCUS};
        }}

        QPushButton#PrimaryButton {{
            background-color: {ACCENT};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 26px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#PrimaryButton:hover {{
            background-color: {ACCENT_HOVER};
        }}
        QPushButton#PrimaryButton:pressed {{
            background-color: {ACCENT_PRESSED};
        }}
        QPushButton#PrimaryButton:disabled {{
            background-color: {BORDER};
            color: {FG_MUTED};
        }}
        """

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # ---- Header (logo + welcome) ---- #
        header = QHBoxLayout()
        header.setSpacing(16)

        logo = self._make_logo(64)
        header.addWidget(logo, 0, Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Welcome to EVA")
        title.setObjectName("EvaTitle")
        subtitle = QLabel(
            "Configure your AI brain in 30 seconds. "
            "You can change everything later in Settings."
        )
        subtitle.setObjectName("EvaSubtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)

        root.addLayout(header)

        # ---- Card: provider + model + API key ---- #
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        # Section header
        sec = QLabel("AI PROVIDER")
        sec.setObjectName("SectionLabel")
        card_layout.addWidget(sec)

        # Provider
        card_layout.addWidget(self._field_label("Provider"))
        self._provider = QComboBox()
        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        card_layout.addWidget(self._provider)

        # Model
        card_layout.addWidget(self._field_label("Model"))
        self._model = QComboBox()
        self._model.setEditable(True)
        card_layout.addWidget(self._model)

        # API key
        self._api_key_label = self._field_label("API Key")
        card_layout.addWidget(self._api_key_label)
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("Paste your key here")
        card_layout.addWidget(self._api_key)

        # Hint
        self._hint = QLabel("")
        self._hint.setObjectName("HintText")
        self._hint.setWordWrap(True)
        card_layout.addWidget(self._hint)

        root.addWidget(card)

        # ---- Status ---- #
        self._status = QLabel("")
        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)
        self._status.setMinimumHeight(28)
        root.addWidget(self._status)

        root.addStretch(1)

        # ---- Buttons ---- #
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setObjectName("SecondaryButton")
        self._test_btn.setCursor(Qt.PointingHandCursor)
        self._test_btn.clicked.connect(self._on_test)
        btn_row.addWidget(self._test_btn)

        self._save_btn = QPushButton("Save & Launch  →")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("FieldLabel")
        return lbl

    @staticmethod
    def _make_logo(size: int) -> QLabel:
        logo = QLabel()
        logo.setFixedSize(size, size)
        logo.setAlignment(Qt.AlignCenter)
        logo_path = get_app_root() / "assets" / "logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                pix = pix.scaled(
                    size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                logo.setPixmap(pix)
                return logo
        # Fallback text
        logo.setText("EVA")
        logo.setStyleSheet(
            f"color: {ACCENT};"
            f"font-size: {int(size * 0.36)}px;"
            f"font-weight: 700;"
            f"background-color: rgba(139, 92, 246, 40);"
            f"border-radius: {size // 2}px;"
        )
        return logo

    # ------------------------------------------------------------------ #
    # Provider list
    # ------------------------------------------------------------------ #
    def _populate_providers(self) -> None:
        self._provider.blockSignals(True)
        self._provider.clear()
        # Display ALL providers from catalog in a friendly order
        for key in ProviderCatalog.list_providers():
            info = ProviderCatalog.get(key)
            if info is None:
                continue
            label = info.display_name
            # Add a hint for local providers
            if key == "ollama":
                label += "  (free, local)"
            elif key == "deepseek":
                label += "  (recommended)"
            self._provider.addItem(label, key)
        self._provider.blockSignals(False)
        self._on_provider_changed()

    # ------------------------------------------------------------------ #
    # Provider change
    # ------------------------------------------------------------------ #
    def _on_provider_changed(self) -> None:
        key = self._provider.currentData()
        if not key:
            return
        info = ProviderCatalog.get(key)
        if info is None:
            return

        self._model.clear()
        if info.models:
            self._model.addItems(info.models)
        else:
            self._model.setEditable(True)
            self._model.setCurrentText("")

        # API key enable/disable
        if info.requires_api_key:
            self._api_key.setEnabled(True)
            self._api_key.setPlaceholderText("Paste your API key here")
            self._api_key_label.setStyleSheet(
                f"color: {FG_SECONDARY};"
            )
        else:
            self._api_key.setEnabled(False)
            self._api_key.clear()
            self._api_key.setPlaceholderText("(no key needed)")
            self._api_key_label.setStyleSheet(
                f"color: {FG_MUTED};"
            )

        # Hint text per provider
        if key == "deepseek":
            hint = (
                "Get a free API key from "
                "<span style='color:#a78bfa'>platform.deepseek.com</span>. "
                "New accounts receive free credits."
            )
        elif key == "openai":
            hint = (
                "Get your key from "
                "<span style='color:#a78bfa'>platform.openai.com</span>."
            )
        elif key == "anthropic":
            hint = (
                "Get your key from "
                "<span style='color:#a78bfa'>console.anthropic.com</span>."
            )
        elif key == "gemini":
            hint = (
                "Get your key from "
                "<span style='color:#a78bfa'>ai.google.dev</span>. "
                "Free tier available."
            )
        elif key == "grok":
            hint = (
                "Get your key from "
                "<span style='color:#a78bfa'>x.ai</span>."
            )
        elif key == "openrouter":
            hint = (
                "Get your key from "
                "<span style='color:#a78bfa'>openrouter.ai</span>. "
                "Access many models with one key."
            )
        elif key == "ollama":
            hint = (
                "Ollama runs on your PC — no key needed. "
                "Install from <span style='color:#a78bfa'>ollama.com</span>, "
                "then run: <code style='color:#a78bfa'>ollama pull qwen2.5:3b</code>"
            )
        else:
            hint = info.notes or ""
        self._hint.setText(hint)

    # ------------------------------------------------------------------ #
    # Test
    # ------------------------------------------------------------------ #
    def _on_test(self) -> None:
        provider = self._provider.currentData()
        api_key = self._api_key.text().strip() or None
        model = self._model.currentText().strip() or None

        self._set_status("Testing connection…", WARNING)
        self._test_btn.setEnabled(False)

        def _worker() -> None:
            try:
                from app.settings.test_connection import check_provider
                result = asyncio.run(
                    check_provider(provider, api_key=api_key, model=model)
                )
                if result.success:
                    self._set_status(
                        f"✓ Connected to {provider} — {result.message}",
                        SUCCESS,
                    )
                else:
                    self._set_status(
                        f"✗ {result.message}",
                        ERROR,
                    )
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"✗ {exc}", ERROR)
            self._test_btn.setEnabled(True)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _on_save(self) -> None:
        provider = self._provider.currentData()
        api_key = self._api_key.text().strip()
        model = self._model.currentText().strip()

        if not provider:
            self._set_status("Please choose a provider.", ERROR)
            return

        info = ProviderCatalog.get(provider)
        if info and info.requires_api_key and not api_key:
            self._set_status(
                f"API key is required for {info.display_name}.", ERROR
            )
            return

        # 1. Persist provider selection
        try:
            ConfigManager.set("ai.provider", provider, persist=False)
            if model:
                ConfigManager.set(
                    f"ai.{provider}.primary_model", model, persist=False,
                )
            ConfigManager._persist_user_config()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Config save failed: {exc}", ERROR)
            return

        # 2. Persist API key to .env (portable, user-editable)
        if api_key and info and info.requires_api_key:
            try:
                self._write_env_key(provider, api_key)
                env_var = info.env_key or f"{provider.upper()}_API_KEY"
                os.environ[env_var] = api_key
            except Exception as exc:  # noqa: BLE001
                self._set_status(f".env write failed: {exc}", ERROR)
                return

            # 3. Also store in vault
            try:
                from app.security.api_vault import APIVault
                APIVault.set(provider, api_key)
            except Exception:  # noqa: BLE001
                pass

        # 4. Mark done so wizard doesn't show again
        try:
            mark_setup_done()
        except Exception:  # noqa: BLE001
            pass

        logger.info("setup_wizard_saved", provider=provider, model=model)
        self.accept()

    @staticmethod
    def _write_env_key(provider: str, api_key: str) -> None:
        env_path = get_user_env_path()
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_var = f"{provider.upper()}_API_KEY"

        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{env_var}="):
                new_lines.append(f"{env_var}={api_key}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{env_var}={api_key}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def _set_status(self, text: str, color: str = FG_SECONDARY) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 500;"
        )


# ====================================================================== #
# Marker helpers
# ====================================================================== #
def _marker_path() -> Path:
    return get_data_dir() / ".setup_done"


def mark_setup_done() -> None:
    try:
        p = _marker_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("done", encoding="utf-8")
    except OSError:
        pass


def needs_setup(force_if_no_marker: bool = True) -> bool:
    """
    Return True if the wizard should be shown.

    Logic:
        1. If marker missing → always show (first run)
        2. Otherwise → show only if no working key is configured
    """
    marker = _marker_path()

    if force_if_no_marker and not marker.exists():
        return True

    provider = str(ConfigManager.get("ai.provider", "deepseek")).lower()

    info = ProviderCatalog.get(provider)
    if info is not None and not info.requires_api_key:
        return False  # ollama — no key needed

    # Any known env key present?
    try:
        from app.core.paths import find_env_file
        env_file = find_env_file()
        if env_file is not None:
            content = env_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                s = line.strip()
                if any(s.startswith(f"{k}=") for k in (
                    "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
                    "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                    "XAI_API_KEY", "OPENROUTER_API_KEY",
                )):
                    value = s.split("=", 1)[1].strip()
                    if value:
                        return False
    except Exception:  # noqa: BLE001
        pass

    # Vault
    try:
        from app.security.api_vault import APIVault
        if APIVault.get(provider):
            return False
    except Exception:  # noqa: BLE001
        pass

    if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return False

    return True