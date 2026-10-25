"""Export and prepare offline INT8 neural models for EchoBridge Mobile Android APK."""
import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mobile_exporter")

MODELS_DIR = "models_cache"
MOBILE_OUTPUT_DIR = "mobile/assets/models"

def verify_and_prepare_mobile_models():
    """Verify presence of models and prepare manifest for Android packaging."""
    os.makedirs(MOBILE_OUTPUT_DIR, exist_ok=True)
    manifest = {
        "app": "EchoBridge Mobile",
        "version": "1.0.0",
        "models": {}
    }

    # 1. Silero VAD
    vad_path = os.path.join(MODELS_DIR, "vad", "silero_vad.onnx")
    if os.path.exists(vad_path):
        size_mb = os.path.getsize(vad_path) / (1024 * 1024)
        logger.info(f"✓ Silero VAD ONNX verified ({size_mb:.2f} MB)")
        manifest["models"]["vad"] = {
            "name": "silero_vad.onnx",
            "size_mb": round(size_mb, 2),
            "status": "ready"
        }
    else:
        logger.warning("Silero VAD model missing in models_cache/vad")

    # 2. Piper TTS
    tts_dir = os.path.join(MODELS_DIR, "tts")
    if os.path.exists(tts_dir):
        for f in os.listdir(tts_dir):
            if f.endswith(".onnx"):
                p = os.path.join(tts_dir, f)
                size_mb = os.path.getsize(p) / (1024 * 1024)
                logger.info(f"✓ Piper TTS Model: {f} ({size_mb:.2f} MB)")
                manifest["models"][f] = {
                    "size_mb": round(size_mb, 2),
                    "status": "ready"
                }

    # 3. Sherpa-ONNX Whisper Specs
    manifest["models"]["whisper_stt"] = {
        "engine": "sherpa-onnx-whisper-tiny-int8",
        "encoder": "tiny-encoder.int8.onnx (~24 MB)",
        "decoder": "tiny-decoder.int8.onnx (~15 MB)",
        "tokens": "tokens.txt",
        "status": "configured_for_download_or_bundle"
    }

    # 4. Save manifest
    manifest_path = os.path.join(MOBILE_OUTPUT_DIR, "model_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Mobile model manifest saved to {manifest_path}")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    verify_and_prepare_mobile_models()
