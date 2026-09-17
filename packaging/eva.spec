# -*- mode: python ; coding: utf-8 -*-
"""
EVA — PyInstaller spec (Phase 22 Batch 4).

Builds a one-folder Windows application:
    dist/EVA/EVA.exe
    dist/EVA/_internal/
    dist/EVA/config/
    dist/EVA/prompts/
    dist/EVA/assets/

Usage:
    pyinstaller packaging/eva.spec --clean --noconfirm
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

# Project root (this file lives in packaging/)
ROOT = Path(SPECPATH).parent

hiddenimports = [
    "app",
    "app.main",
    # Providers (dynamic registration)
    "app.brain.providers.deepseek_provider",
    "app.brain.providers.ollama_provider",
    # Voice providers
    "app.voice.stt_providers.faster_whisper_stt",
    "app.voice.tts_providers.edge_tts",
    "app.voice.tts_providers.piper_tts",
    "app.voice.wakeword_providers.openwakeword_provider",
    "app.voice.wakeword_providers.stt_verify_provider",
    # Tools
    "app.tools",
    "app.tools.app_tools",
    "app.tools.window_tools",
    "app.tools.keyboard_tools",
    "app.tools.mouse_tools",
    "app.tools.screen_tools",
    "app.tools.clipboard_tools",
    "app.tools.media_tools",
    "app.tools.vision_tools",
    "app.tools.browser_tools",
    "app.tools.file_tools",
    "app.tools.system_tools",
    "app.tools.terminal_tools",
    "app.tools.integrations",
    # Licensing / security
    "app.licensing",
    "app.security",
    # GUI
    "app.gui",
    "app.gui.main_window",
    "app.gui.widgets",
    "app.gui.dialogs",
    # Third-party
    "psutil",
    "cryptography",
    "yaml",
    "dotenv",
    "httpx",
    "pydantic",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "sounddevice",
    "soundfile",
    "numpy",
    "faster_whisper",
    "edge_tts",
    "pyperclip",
]

datas = [
    (str(ROOT / "config" / "config.yaml"), "config"),
    (str(ROOT / "config" / "user_config.yaml"), "config"),
    (str(ROOT / "config" / "permissions.yaml"), "config"),
    (str(ROOT / "config" / "network_whitelist.yaml"), "config"),
    (str(ROOT / "config" / "license_public_key.pem"), "config"),
    (str(ROOT / "prompts"), "prompts"),
    (str(ROOT / "assets"), "assets"),
]

datas += collect_data_files("app", includes=["**/*.qss", "**/*.yaml", "**/*.json"])

excludes = [
    "tests", "pytest", "tkinter", "matplotlib",
    "notebook", "IPython", "jupyter",
]

block_cipher = None

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EVA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,      
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icon.ico") if (ROOT / "assets" / "icon.ico").exists() else None,
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EVA",
)