"""
EVA GUI module (Phase 21).

Full PySide6 desktop dashboard. This package provides:
    - GUIState        : lightweight state machine (no Qt needed)
    - GUIController   : bridge between AgentLoop and the UI
    - theme           : color/font constants
    - widgets/*       : reusable visual components
    - dialogs/*       : settings, confirmation
    - main_window.py  : the QMainWindow shell

The GUI imports PySide6 lazily so headless / CLI mode still works.
"""
__all__ = ["__version__"]

__version__ = "0.1.0"