"""Interactive Command-Line Prototype for EchoBridge Speech-to-Speech Translation."""
import sys
import os
import time
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.translator import TranslationPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EchoBridge-CLI")

def run_cli():
    print("=" * 60)
    print("   EchoBridge: Zero-Cost Offline Real-Time Speech Translator")
    print("   Phase 2 Command-Line Prototype")
    print("=" * 60)
    print("Default Mode: English (en) -> Japanese (ja)")
    print("Commands:")
    print("  's' + Enter: Swap language direction (en <-> ja)")
    print("  'q' + Enter: Quit application")
    print("-" * 60)

    pipeline = TranslationPipeline(
        source_lang="en",
        target_lang="ja",
        models_dir="models_cache",
        stt_size="base",
        auto_playback=True
    )

    def on_transcribed(text, lang, lat):
        print(f"\n[Transcribed ({lang}) in {lat:.1f}ms]: {text}")

    def on_translated(text, lat):
        print(f"[Translated in {lat:.1f}ms]: {text}")

    def on_synthesized(audio, sr, lat):
        print(f"[Synthesized speech ({len(audio)} bytes) in {lat:.1f}ms] -> Playing to speakers...")

    def on_completed(metrics):
        print(f"[Pipeline Complete] End-to-End Latency: {metrics['total_e2e_latency_ms']:.1f}ms (STT: {metrics['stt_latency_ms']:.1f}ms, MT: {metrics['mt_latency_ms']:.1f}ms, TTS: {metrics['tts_latency_ms']:.1f}ms)\n")

    pipeline.on_transcription = on_transcribed
    pipeline.on_translation = on_translated
    pipeline.on_synthesis = on_synthesized
    pipeline.on_pipeline_done = on_completed

    print("\nStarting live microphone listener (speak into your microphone)...")
    pipeline.start_listening()

    try:
        while True:
            cmd = input().strip().lower()
            if cmd == "q":
                break
            elif cmd == "s":
                pipeline.swap_languages()
                print(f"\nSwapped language direction! Active: {pipeline.source_lang} -> {pipeline.target_lang}\n")
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping audio capture...")
        pipeline.stop_listening()
        print("EchoBridge CLI terminated.")

if __name__ == "__main__":
    run_cli()
