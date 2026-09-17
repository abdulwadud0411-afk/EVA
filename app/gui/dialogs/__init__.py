"""GUI dialogs package (Phase 21 + 22)."""
from app.gui.dialogs.settings_dialog import SettingsDialog, open_settings  # noqa: F401
from app.gui.dialogs.confirmation_dialog import (  # noqa: F401
    ConfirmationDialog,
    ask_confirmation,
)
from app.gui.dialogs.setup_wizard import SetupWizard, needs_setup  # noqa: F401

__all__ = [
    "SettingsDialog", "open_settings",
    "ConfirmationDialog", "ask_confirmation",
    "SetupWizard", "needs_setup",
]