"""
Settings dialog (Phase 17).

Tkinter-based dialog for managing AI provider settings:
    - Provider dropdown
    - Model dropdown
    - API key entry (masked)
    - Base URL entry
    - Test Connection button
    - Save button

Launched via:
    python -m app.gui
    python -m app.main --settings
    scripts/open_settings.bat
"""
from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from app.core.logger import get_logger
from app.settings.provider_catalog import ProviderCatalog
from app.settings.settings_manager import SettingsManager, SettingsError
from app.settings.test_connection import check_provider

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Color palette
# ---------------------------------------------------------------------- #
BG = "#1e1e2e"
BG_INPUT = "#2a2a3e"
FG = "#e0e0f0"
FG_DIM = "#a0a0b8"
ACCENT = "#7c3aed"        # purple
ACCENT_HOVER = "#8b5cf6"
SUCCESS = "#10b981"
ERROR = "#ef4444"
WARNING = "#f59e0b"


# ---------------------------------------------------------------------- #
# Dialog
# ---------------------------------------------------------------------- #
class SettingsDialog:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("EVA — AI Provider Settings")
        self.root.geometry("640x560")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # State
        self._provider_var = tk.StringVar()
        self._model_var = tk.StringVar()
        self._api_key_var = tk.StringVar()
        self._base_url_var = tk.StringVar()
        self._status_var = tk.StringVar(value="Ready.")
        self._status_label: Optional[tk.Label] = None

        self._build_ui()
        self._load_current_settings()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(
            header, text="AI Provider Settings",
            font=("Segoe UI", 18, "bold"), bg=BG, fg=FG,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Change your AI brain without touching code.",
            font=("Segoe UI", 10), bg=BG, fg=FG_DIM,
        ).pack(anchor="w")

        # Separator
        tk.Frame(self.root, height=1, bg=BG_INPUT).pack(fill="x", padx=24, pady=12)

        # Form
        form = tk.Frame(self.root, bg=BG)
        form.pack(fill="x", padx=24)

        self._label(form, "Provider")
        self._provider_combo = ttk.Combobox(
            form, textvariable=self._provider_var,
            values=[ProviderCatalog.display_names()[k] for k in ProviderCatalog.list_providers()],
            state="readonly", width=44,
        )
        self._provider_combo.pack(fill="x", pady=(0, 12))
        self._provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        self._label(form, "Model")
        self._model_combo = ttk.Combobox(
            form, textvariable=self._model_var, state="normal", width=44,
        )
        self._model_combo.pack(fill="x", pady=(0, 12))

        self._label(form, "API Key")
        self._api_key_entry = tk.Entry(
            form, textvariable=self._api_key_var, show="•",
            bg=BG_INPUT, fg=FG, insertbackground=FG,
            relief="flat", font=("Consolas", 10), width=48,
        )
        self._api_key_entry.pack(fill="x", ipady=6, pady=(0, 4))
        self._api_key_hint = tk.Label(
            form, text="Stored in .env (never in source or config.yaml).",
            font=("Segoe UI", 8), bg=BG, fg=FG_DIM,
        )
        self._api_key_hint.pack(anchor="w", pady=(0, 12))

        self._label(form, "Base URL")
        self._base_url_entry = tk.Entry(
            form, textvariable=self._base_url_var,
            bg=BG_INPUT, fg=FG, insertbackground=FG,
            relief="flat", font=("Consolas", 10), width=48,
        )
        self._base_url_entry.pack(fill="x", ipady=6, pady=(0, 12))

        # Buttons
        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(16, 8))

        self._test_btn = self._make_button(
            btn_row, "Test Connection", self._on_test, color=ACCENT,
        )
        self._test_btn.pack(side="left")

        self._save_btn = self._make_button(
            btn_row, "Save", self._on_save, color=SUCCESS,
        )
        self._save_btn.pack(side="right", padx=(8, 0))

        self._cancel_btn = self._make_button(
            btn_row, "Cancel", self._on_cancel, color=BG_INPUT,
        )
        self._cancel_btn.pack(side="right")

        # Status bar
        status_frame = tk.Frame(self.root, bg=BG)
        status_frame.pack(fill="x", padx=24, pady=(16, 20), side="bottom")

        self._status_label = tk.Label(
            status_frame, textvariable=self._status_var,
            font=("Segoe UI", 9), bg=BG, fg=FG_DIM,
            anchor="w", justify="left", wraplength=580,
        )
        self._status_label.pack(fill="x")

    def _label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent, text=text, font=("Segoe UI", 10, "bold"),
            bg=BG, fg=FG, anchor="w",
        ).pack(anchor="w", pady=(4, 4))

    def _make_button(
        self, parent: tk.Widget, text: str, command, color: str = ACCENT,
    ) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            bg=color, fg="white",
            activebackground=ACCENT_HOVER, activeforeground="white",
            relief="flat", font=("Segoe UI", 10, "bold"),
            padx=18, pady=8, cursor="hand2",
            borderwidth=0,
        )
        return btn

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    def _load_current_settings(self) -> None:
        try:
            snapshot = SettingsManager.get_ai_settings()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed to load settings: {exc}", "error")
            return

        active = snapshot["provider"]
        display_name = snapshot["display_names"].get(active, active)
        self._provider_var.set(display_name)
        self._apply_provider(active)

        # API key (mask it)
        key = SettingsManager.get_api_key(active)
        self._api_key_var.set(key or "")

        self._set_status(
            f"Active provider: {display_name}"
            + (" (API key set)" if key else " (API key missing)")
        )

    def _apply_provider(self, key: str) -> None:
        """Populate model list + base URL when the provider changes."""
        models = ProviderCatalog.models_for(key)
        self._model_combo["values"] = models

        snapshot = SettingsManager.get_ai_settings()
        self._model_var.set(snapshot.get("model") or (models[0] if models else ""))
        self._base_url_var.set(
            snapshot.get("base_url") or ProviderCatalog.default_base_url(key)
        )

        # Disable API key field for providers that don't need it (e.g. ollama)
        if not ProviderCatalog.requires_api_key(key):
            self._api_key_entry.configure(state="disabled")
            self._api_key_hint.configure(text="No API key needed for this provider.")
        else:
            self._api_key_entry.configure(state="normal")
            self._api_key_hint.configure(
                text="Stored in .env (never in source or config.yaml)."
            )

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def _on_provider_change(self, _event=None) -> None:
        display = self._provider_var.get()
        mapping = {v: k for k, v in ProviderCatalog.display_names().items()}
        key = mapping.get(display, "deepseek")
        self._apply_provider(key)
        self._api_key_var.set(SettingsManager.get_api_key(key) or "")
        self._set_status(f"Selected {display}. Click Save or Test Connection.")

    def _on_test(self) -> None:
        provider_key = self._current_provider_key()
        api_key = self._api_key_var.get().strip() or None
        base_url = self._base_url_var.get().strip() or None
        model = self._model_var.get().strip() or None

        self._set_status(f"Testing {provider_key}...", "info")
        self._test_btn.configure(state="disabled", text="Testing...")

        def _worker() -> None:
            try:
                result = asyncio.run(check_provider(
                    provider_key, api_key=api_key,
                    base_url=base_url, model=model,
                ))
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: self._on_test_done(
                    False, f"Test failed: {exc}", 0,
                ))
                return
            self.root.after(0, lambda: self._on_test_done(
                result.success, result.message, result.latency_ms,
            ))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_test_done(self, success: bool, message: str, latency_ms: int) -> None:
        self._test_btn.configure(state="normal", text="Test Connection")
        prefix = "✅ " if success else "❌ "
        self._set_status(prefix + message, "success" if success else "error")

    def _on_save(self) -> None:
        provider_key = self._current_provider_key()
        try:
            SettingsManager.set_provider_config(
                provider_key,
                api_key=self._api_key_var.get().strip() or None,
                base_url=self._base_url_var.get().strip() or None,
                model=self._model_var.get().strip() or None,
            )
            SettingsManager.set_active_provider(provider_key)
        except SettingsError as exc:
            messagebox.showerror("Save failed", str(exc))
            self._set_status(f"Save failed: {exc}", "error")
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", str(exc))
            self._set_status(f"Save failed: {exc}", "error")
            return

        self._set_status(
            f"✅ Saved. EVA will use {provider_key} on next request.",
            "success",
        )
        messagebox.showinfo(
            "Saved",
            "Settings saved to user_config.yaml.\n"
            "API key saved to .env.\n\n"
            "Restart EVA if it is currently running.",
        )

    def _on_cancel(self) -> None:
        self.root.destroy()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _current_provider_key(self) -> str:
        display = self._provider_var.get()
        mapping = {v: k for k, v in ProviderCatalog.display_names().items()}
        return mapping.get(display, "deepseek")

    def _set_status(self, text: str, level: str = "info") -> None:
        colors = {
            "info": FG_DIM,
            "success": SUCCESS,
            "error": ERROR,
            "warning": WARNING,
        }
        if self._status_label is not None:
            self._status_label.configure(fg=colors.get(level, FG_DIM))
        self._status_var.set(text)

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        self.root.mainloop()


def open_settings() -> None:
    """Open the settings dialog (blocking)."""
    dialog = SettingsDialog()
    dialog.run()