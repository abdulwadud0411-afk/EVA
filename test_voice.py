"""Quick voice test — speaks a random passage."""
import asyncio
import traceback


def fix_pronunciation(text: str) -> str:
    return (
        text
        .replace("EVA", "Ee-vah")
        .replace("Eva", "Ee-vah")
    )


PASSAGE = (
    "Hello Rizvi. I am Ee-vah, your personal AI assistant. "
    "I can control your computer, search the web, play videos, "
    "and answer your questions in Bangla, English, or Banglish. "
    "My voice is warm, calm, and slightly futuristic. "
    "I live on your Windows PC, and I am here to help you every day. "
    "What would you like me to do today?"
)


async def main():
    print("[1] Loading config...")
    from app.core.config_manager import ConfigManager
    ConfigManager.load()
    print(f"     voice.tts.provider = {ConfigManager.get('voice.tts.provider')}")

    print("[2] Registering TTS providers...")
    import app.voice.tts_providers  # noqa: F401
    from app.voice.tts_registry import TTSRegistry
    print(f"     Registered: {TTSRegistry.list_providers()}")

    print("[3] Getting active provider...")
    provider = TTSRegistry.get_active_provider()
    print(f"     Active: {provider.name}")

    print("[4] Wrapping in SpeakController...")
    from app.voice.tts import SpeakController
    controller = SpeakController(provider=provider)

    print("[5] Warm-up...")
    try:
        ok = await controller.warm_up()
    except Exception as exc:
        print(f"[FAIL] warm_up raised: {exc}")
        traceback.print_exc()
        return
    if not ok:
        print("[FAIL] warm_up returned False")
        return
    print("     Warm-up OK")

    print("[6] Speaking passage in chunks...")
    text = fix_pronunciation(PASSAGE)
    chunks = [text[i:i+180] for i in range(0, len(text), 180)]
    for i, chunk in enumerate(chunks, 1):
        print(f"     Chunk {i}/{len(chunks)}: {chunk[:50]}...")
        try:
            ok = await controller.speak(chunk)
            if not ok:
                print(f"[FAIL] speak() returned False on chunk {i}")
        except Exception as exc:
            print(f"[FAIL] speak() raised: {exc}")
            traceback.print_exc()
            return
    print("[DONE]")


if __name__ == "__main__":
    asyncio.run(main())