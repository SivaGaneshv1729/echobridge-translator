"""First-run setup script to download and verify all local offline models."""
import os
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.model_manager import ModelManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ModelSetup")

def setup_models():
    print("=" * 60)
    print("   EchoBridge: Offline Model Setup & Verification")
    print("=" * 60)
    manager = ModelManager("models_cache")

    # 1. Disk Space Check
    required_mb = 600.0
    if not manager.check_disk_space(required_mb):
        print(f"Error: Insufficient disk space. At least {required_mb} MB required.")
        sys.exit(1)
    print(f"✓ Disk space verified (> {required_mb} MB available)")

    # 2. Silero VAD
    print("\n[1/4] Checking Silero VAD (ONNX)...")
    if not manager.is_vad_ready():
        print("Downloading Silero VAD...")
        manager.download_vad()
    print("✓ Silero VAD ready.")

    # 3. Whisper STT
    print("\n[2/4] Checking Speech Recognition models...")
    for size in ["tiny", "base"]:
        print(f"Verifying Faster-Whisper ({size})...")
        from faster_whisper import download_model
        download_model(size)
    print("✓ Speech recognition models ready.")

    # 4. Translation Models (EN <-> JA)
    print("\n[3/4] Checking Translation packages (EN <-> JA)...")
    import scripts.test_direct_translation as dt
    import scripts.test_reverse_translation as rt
    dt.setup_and_test()
    rt.download_and_test_ja_en()
    print("✓ Translation models ready.")

    # 5. Piper Voices (EN & JA)
    print("\n[4/4] Checking Piper TTS Voices...")
    for voice in ["en_US-amy-low", "ja_JP-hi_fi_captain-medium"]:
        if not manager.is_tts_ready(voice):
            print(f"Downloading {voice}...")
            manager.download_tts_voice(voice)
    print("✓ Piper TTS voices ready.")

    print("\n" + "=" * 60)
    print("All models downloaded and verified offline! You can now run:")
    print("   python app.py")
    print("=" * 60)

if __name__ == "__main__":
    setup_models()
