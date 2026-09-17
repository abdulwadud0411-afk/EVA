"""
EVA entry point (Phase 10 — wake word + voice + panic).

Usage:
    python -m app.main                # text CLI
    python -m app.main --voice        # push-to-talk voice mode
    python -m app.main --always-on    # wake word + continuous voice
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config_manager import ConfigManager, ConfigurationError
from app.core.logger import get_logger
from app.core.events import EventBus, Event
from app.agent.agent import AgentLoop

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Shared helpers
# ---------------------------------------------------------------------- #
async def _run_agent_turn(
    agent: AgentLoop, event_bus: EventBus, text: str, voice_turn: bool,
) -> str:
    event_bus.publish(Event("THINKING_STARTED", {"input": text}))
    try:
        response = await agent.run(text, voice_turn=voice_turn)
    except Exception as exc:  # noqa: BLE001
        logger.error("agent_run_failed", error=str(exc))
        event_bus.publish(Event("ERROR", {"message": str(exc)}))
        return f"[EVA] Error: {exc}"
    event_bus.publish(Event("RESPONSE_READY", {"response": response}))
    return response


# ---------------------------------------------------------------------- #
# Text CLI
# ---------------------------------------------------------------------- #
async def _run_text_cli(agent: AgentLoop, event_bus: EventBus) -> int:
    print(" Mode: text — type your message. 'exit' or 'quit' to stop.")
    while True:
        try:
            user_input = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[EVA] Goodbye.")
            return 0
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("[EVA] Goodbye.")
            return 0
        response = await _run_agent_turn(agent, event_bus, user_input, voice_turn=False)
        print(f"\nEVA: {response}")


# ---------------------------------------------------------------------- #
# Push-to-talk voice mode
# ---------------------------------------------------------------------- #
async def _run_voice_cli(agent: AgentLoop, event_bus: EventBus) -> int:
    from app.voice import microphone
    from app.voice.stt_registry import STTRegistry
    from app.voice.stt_providers import __init__ as _stt_providers  # noqa: F401
    from app.voice.tts_providers import __init__ as _tts_providers  # noqa: F401
    from app.voice.tts_registry import TTSRegistry

    if not microphone.is_available():
        print("[EVA] Microphone libraries missing. Install:")
        print("       pip install sounddevice soundfile numpy")
        return 1

    try:
        stt = STTRegistry.get_active_provider()
    except Exception as exc:  # noqa: BLE001
        print(f"[EVA] STT provider error: {exc}")
        return 1

    print(" Loading STT model (first run may take a while)...")
    if not await stt.warm_up():
        print("[EVA] Failed to load STT model.")
        return 1

    try:
        tts = TTSRegistry.get_active_provider()
        print(f" Loading TTS provider: {tts.name}...")
        if not await tts.warm_up():
            print("[EVA] TTS warm-up failed — EVA will reply with text only.")
    except Exception as exc:  # noqa: BLE001
        print(f"[EVA] TTS unavailable: {exc}")

    print(" Mode: voice — speak your command. Ctrl+C to exit.")
    print(" Press Enter to start listening.\n")

    while True:
        try:
            input("[EVA] Press Enter to start listening...")
        except (EOFError, KeyboardInterrupt):
            print("\n[EVA] Goodbye.")
            return 0

        try:
            path = microphone.record_until_silence()
        except Exception as exc:  # noqa: BLE001
            print(f"[EVA] Recording error: {exc}")
            continue

        try:
            result = await stt.transcribe(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[EVA] Transcription error: {exc}")
            continue

        if result.is_empty:
            print("[EVA] I didn't catch that. Try again.")
            continue

        print(f"[EVA] Heard: {result.text}")
        response = await _run_agent_turn(agent, event_bus, result.text, voice_turn=True)
        print(f"\nEVA: {response}\n")


# ---------------------------------------------------------------------- #
# Always-on mode (wake word + continuous voice + panic button)
# ---------------------------------------------------------------------- #
async def _run_always_on(agent: AgentLoop, event_bus: EventBus) -> int:
    from app.voice import microphone
    from app.voice.stt_registry import STTRegistry
    from app.voice.stt_providers import __init__ as _stt_providers  # noqa: F401
    from app.voice.tts_providers import __init__ as _tts_providers  # noqa: F401
    from app.voice.tts_registry import TTSRegistry
    from app.voice.wakeword import WakeWordDetector
    from app.voice.wakeword_providers import __init__ as _ww_providers  # noqa: F401
    from app.voice.interruption import InterruptionHandler
    from app.voice.panic import PanicButton

    if not microphone.is_available():
        print("[EVA] Microphone libraries missing.")
        return 1

    # --- Warm up STT + TTS ------------------------------------------- #
    try:
        stt = STTRegistry.get_active_provider()
    except Exception as exc:  # noqa: BLE001
        print(f"[EVA] STT provider error: {exc}")
        return 1
    print(" Loading STT model...")
    if not await stt.warm_up():
        print("[EVA] Failed to load STT model.")
        return 1

    try:
        tts = TTSRegistry.get_active_provider()
        print(f" Loading TTS provider: {tts.name}...")
        if not await tts.warm_up():
            print("[EVA] TTS warm-up failed — EVA will reply with text only.")
    except Exception as exc:  # noqa: BLE001
        print(f"[EVA] TTS unavailable: {exc}")

    # --- State ------------------------------------------------------ #
    state = {
        "active": False,       # is the wake word armed?
        "processing": False,   # is the agent currently working?
        "shutdown": False,
    }
    state_lock = asyncio.Lock()
    queue: asyncio.Queue = asyncio.Queue()

    # --- Wake word -------------------------------------------------- #
    def on_wake(det) -> None:
        # Called from background thread; put into async queue
        try:
            queue.put_nowait(("wake", det))
        except Exception:
            pass

    detector = WakeWordDetector(event_bus=event_bus, on_detected=on_wake)
    if not await detector.start():
        print("[EVA] Wake word detector failed to start.")
        return 1
    print(f"[EVA] Wake word active (mode: {detector.mode}).")

    # --- Interruption handler --------------------------------------- #
    interruption = InterruptionHandler(event_bus=event_bus)
    await interruption.start()

    # --- Panic button ---------------------------------------------- #
    def on_panic() -> None:
        logger.warning("panic_button_pressed")
        state["active"] = False
        try:
            queue.put_nowait(("panic", None))
        except Exception:
            pass

    panic = PanicButton(on_panic=on_panic)
    panic.start()

    # --- Event hooks ------------------------------------------------ #
    event_bus.subscribe(lambda e: logger.info("EVENT", type=e.type))

    # --- Print help ------------------------------------------------- #
    print("=" * 60)
    print(" EVA is running in always-on mode.")
    print(" Say: 'Hey EVA' / 'Hello EVA' / 'Wake up EVA'")
    print(f" Press {panic.hotkey} to panic-stop.")
    print(" Ctrl+C to exit.")
    print("=" * 60)

    async def _listen_and_run() -> None:
        """Wait for wake word → record → transcribe → agent → speak."""
        if state["processing"]:
            return
        state["processing"] = True
        try:
            # Beep / acknowledge
            try:
                await tts.speak("Yes?")
            except Exception:  # noqa: BLE001
                pass

            # Record
            try:
                path = await asyncio.get_event_loop().run_in_executor(
                    None, microphone.record_until_silence,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("record_failed", error=str(exc))
                return

            # Transcribe
            try:
                result = await stt.transcribe(path)
            except Exception as exc:  # noqa: BLE001
                logger.error("transcribe_failed", error=str(exc))
                return
            if result.is_empty:
                return

            print(f"[EVA] Heard: {result.text}")
            response = await _run_agent_turn(
                agent, event_bus, result.text, voice_turn=True,
            )
            print(f"EVA: {response}\n")
        finally:
            state["processing"] = False

    # --- Main loop -------------------------------------------------- #
    try:
        while not state["shutdown"]:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if kind == "wake":
                logger.info("wake_event_received")
                asyncio.create_task(_listen_and_run())
            elif kind == "panic":
                logger.warning("panic_received")
                try:
                    from app.voice.tts import SpeakController
                    pass  # TTS stop is a no-op for now; agent loop exits on next check
                except Exception:
                    pass
                # Cancel any pending processing task by draining the queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except Exception:
                        break
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[EVA] Shutting down...")
        await detector.stop()
        await interruption.stop()
        panic.stop()
        print("[EVA] Goodbye.")
    return 0


# ---------------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------------- #
async def main_async(mode: str) -> int:
    try:
        ConfigManager.load()
    except ConfigurationError as exc:
        print(f"[EVA] Configuration error: {exc}")
        return 1
    except FileNotFoundError as exc:
        print(f"[EVA] Missing config file: {exc}")
        return 1

    event_bus = EventBus()
    event_bus.subscribe(lambda e: logger.info("EVENT", type=e.type, data=e.data))

    provider_name = ConfigManager.get("ai.provider", "deepseek")
    model_name = ConfigManager.get(f"ai.{provider_name}.primary_model", "n/a")

    print("=" * 60)
    print(f" EVA {ConfigManager.get('app.version', '0.1.0')}")
    print(f" Provider: {provider_name}")
    print(f" Model   : {model_name}")
    print("=" * 60)

    agent = AgentLoop(event_bus=event_bus)

    if mode == "text":
        return await _run_text_cli(agent, event_bus)
    if mode == "voice":
        return await _run_voice_cli(agent, event_bus)
    if mode == "always_on":
        return await _run_always_on(agent, event_bus)
    return 1


def _run_gui() -> int:
    """Launch the PySide6 dashboard (Phase 21/22)."""
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        from app.gui.main_window import MainWindow
        from app.gui.tray import TrayController
        from app.core.paths import get_app_root
    except Exception as exc:  # noqa: BLE001
        print(f"[EVA] GUI unavailable: {exc}")
        print("[EVA] Install PySide6:  pip install PySide6")
        return 1

    # Phase 22 — startup security checks (non-blocking)
    try:
        from app.security import anti_debug_check, anti_tamper_check, anti_tamper_should_block
        dbg = anti_debug_check()
        if dbg.get("debugger"):
            logger.warning("startup_debugger_detected", **dbg)
        tamper = anti_tamper_check()
        if not tamper.get("files_intact", True):
            logger.warning(
                "startup_files_modified",
                modified=len(tamper.get("modified_files", [])),
                missing=len(tamper.get("missing_files", [])),
            )
        if anti_tamper_should_block():
            logger.error("startup_blocked_tamper")
            print("[EVA] Startup blocked: tamper detected.")
            return 2
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup_security_checks_failed", error=str(exc))

    app = QApplication.instance() or QApplication([])

    # Load dark theme FIRST (applies to wizard too)
    qss_path = get_app_root() / "app" / "gui" / "styles" / "dark.qss"
    if qss_path.exists():
        try:
            app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("qss_load_failed", error=str(exc))

    # ---- First-run setup wizard (Phase 22) ---- #
    try:
        from app.gui.dialogs.setup_wizard import SetupWizard, needs_setup
        if needs_setup(force_if_no_marker=True):
            wizard = SetupWizard()
            result = wizard.exec()
            if result != QDialog.Accepted:
                logger.info("setup_wizard_cancelled")
                return 0
            # Reload config after wizard saved
            ConfigManager.reset()
            ConfigManager.load()
    except Exception as exc:  # noqa: BLE001
        logger.warning("setup_wizard_failed", error=str(exc))

    # ---- Main window ---- #
    window = MainWindow()
    tray = TrayController(window)
    tray.show()

    window.show()

    try:
        return app.exec()
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EVA desktop assistant")
    parser.add_argument("--gui", action="store_true",
                        help="Open the full GUI dashboard (Phase 21).")
    parser.add_argument("--voice", action="store_true",
                        help="Push-to-talk voice mode.")
    parser.add_argument("--always-on", action="store_true",
                        help="Wake word + continuous voice + panic button.")
    parser.add_argument("--settings", action="store_true",
                        help="Open the AI Provider Settings dialog.")
    args = parser.parse_args()

    # Default: GUI mode (Phase 21). Use --voice / --always-on for CLI.
    if args.gui or (not args.voice and not args.always_on and not args.settings):
        try:
            ConfigManager.load()
        except Exception as exc:  # noqa: BLE001
            print(f"[EVA] Config error: {exc}")
            return 1
        return _run_gui()

    if args.settings:
        try:
            from app.gui.settings_dialog import open_settings
            open_settings()
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"[EVA] Could not open settings: {exc}")
            return 1

    if args.always_on:
        mode = "always_on"
    elif args.voice:
        mode = "voice"
    else:
        mode = "text"

    try:
        return asyncio.run(main_async(mode))
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    raise SystemExit(main())