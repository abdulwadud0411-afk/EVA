"""Debug TTS warm-up failure."""
import asyncio
import traceback


async def main():
    # 1. Check edge-tts package
    try:
        import edge_tts
        print("[OK] edge_tts imported:", edge_tts.__file__)
    except Exception as exc:
        print("[FAIL] edge_tts import:", exc)
        traceback.print_exc()
        return

    # 2. Check if edge_tts has list_voices
    try:
        voices = await edge_tts.list_voices()
        print(f"[OK] list_voices returned {len(voices)} voices")
    except Exception as exc:
        print("[FAIL] list_voices:", exc)
        traceback.print_exc()
        return

    # 3. Try EdgeTTS adapter directly
    try:
        from app.voice.tts_providers.edge_tts import EdgeTTS
        provider = EdgeTTS({"en_voice": "en-US-AvaNeural"})
        ok = await provider.warm_up()
        print(f"[{'OK' if ok else 'FAIL'}] EdgeTTS.warm_up() -> {ok}")
    except Exception as exc:
        print("[FAIL] EdgeTTS.warm_up:", exc)
        traceback.print_exc()
        return

    # 4. Try synthesizing text
    try:
        out = await provider.synthesize("Hello Rizvi, this is EVA.", "test_tts_output.mp3")
        print(f"[OK] synthesized to {out}")
    except Exception as exc:
        print("[FAIL] synthesize:", exc)
        traceback.print_exc()
        return

    # 5. Try playing
    try:
        from app.voice.tts import _play_audio
        _play_audio("test_tts_output.mp3")
        print("[OK] played audio")
    except Exception as exc:
        print("[FAIL] _play_audio:", exc)
        traceback.print_exc()
        return

    print("[DONE] All TTS checks passed.")


if __name__ == "__main__":
    asyncio.run(main())