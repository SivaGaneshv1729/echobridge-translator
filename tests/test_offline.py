"""Phase 6: Strict Offline Operation Tests.
Verifies that all models run with zero internet connectivity and no cloud fallback.
"""
import os
import sys
import socket
import pytest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audio.vad import SileroVAD
from engines.translation import TranslatorEngine
from engines.text_to_speech import TTSEngine
from engines.speech_recognition import SpeechRecognizer
from pipeline.translator import TranslationPipeline

# Network blocking fixture to simulate absolute offline environment
class NetworkAccessBlocked(Exception):
    pass

def block_network_calls():
    """Monkey-patch socket to forbid any external network traffic."""
    real_socket = socket.socket

    def forbidden_socket(*args, **kwargs):
        raise NetworkAccessBlocked("ILLEGAL NETWORK ACCESS DETECTED: EchoBridge must operate 100% offline!")

    socket.socket = forbidden_socket
    return real_socket

def restore_network_calls(real_socket):
    socket.socket = real_socket

def test_complete_offline_execution():
    """Verify entire pipeline functions with sockets completely blocked."""
    real_socket = block_network_calls()
    try:
        # 1. Initialize pipeline strictly offline
        pipeline = TranslationPipeline(
            source_lang="en",
            target_lang="ja",
            models_dir="models_cache",
            stt_size="base",
            auto_playback=False
        )

        # 2. Synthesize English speech offline
        tts = TTSEngine("models_cache/tts")
        pcm_en, _, _ = tts.synthesize("Hello, how are you today?", "en")
        audio_en = np.frombuffer(pcm_en, dtype=np.int16).astype(np.float32) / 32768.0

        # 3. Process utterance offline (STT -> MT -> TTS)
        metrics_en_ja = pipeline.process_utterance(audio_en)
        assert metrics_en_ja is not None
        assert len(metrics_en_ja["translated_text"]) > 0
        assert metrics_en_ja["source_language"] == "en"
        assert metrics_en_ja["target_language"] == "ja"

        # 4. Reverse direction offline (JA -> EN)
        pipeline.swap_languages()
        pcm_ja, sr_ja, _ = tts.synthesize("こんにちは、駅はどこですか？", "ja")
        audio_ja = np.frombuffer(pcm_ja, dtype=np.int16).astype(np.float32) / 32768.0
        if sr_ja != 16000:
            import scipy.signal
            audio_ja = scipy.signal.resample(audio_ja, int(len(audio_ja) * 16000 / sr_ja)).astype(np.float32)

        metrics_ja_en = pipeline.process_utterance(audio_ja)
        assert metrics_ja_en is not None
        assert len(metrics_ja_en["translated_text"]) > 0
        assert metrics_ja_en["source_language"] == "ja"
        assert metrics_ja_en["target_language"] == "en"

        print("\n[PASSED] 100% Offline execution verified: zero network calls made!")

    finally:
        restore_network_calls(real_socket)

def test_missing_model_error_handling():
    """Verify missing model produces clean local error and NEVER falls back to cloud."""
    with pytest.raises(FileNotFoundError) as exc_info:
        _ = TranslatorEngine("non_existent_models_dir")
        _ = _translators = TranslatorEngine("non_existent_models_dir").load_pair("en", "es")
    
    assert "not found" in str(exc_info.value).lower()
