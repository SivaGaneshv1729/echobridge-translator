"""Automated tests for EchoBridge end-to-end translation pipeline."""
import os
import sys
import pytest
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audio.vad import SileroVAD, UtteranceSegmenter
from engines.translation import TranslatorEngine
from engines.text_to_speech import TTSEngine
from pipeline.translator import TranslationPipeline

@pytest.fixture(scope="module")
def pipeline():
    return TranslationPipeline(
        source_lang="en",
        target_lang="ja",
        models_dir="models_cache",
        stt_size="base",
        auto_playback=False # Do not play to speaker during automated test
    )

def test_vad_silence(pipeline):
    """Test VAD returns low probability on digital silence."""
    silence = np.zeros(512, dtype=np.float32)
    prob = pipeline.vad.is_speech(silence)
    assert prob < 0.2, f"Expected silence prob < 0.2, got {prob}"

def test_translation_engine():
    """Test MT engine directly for both directions."""
    translator = TranslatorEngine("models_cache/translation")
    
    # EN -> JA
    ja_out, latency1 = translator.translate("Where is the station?", "en", "ja")
    assert len(ja_out) > 0
    assert latency1 > 0
    assert "駅" in ja_out or "どこ" in ja_out

    # JA -> EN
    en_out, latency2 = translator.translate("こんにちは", "ja", "en")
    assert len(en_out) > 0
    assert latency2 > 0
    assert "hello" in en_out.lower() or "hi" in en_out.lower()

def test_tts_engine():
    """Test TTS synthesis for both English and Japanese."""
    tts = TTSEngine("models_cache/tts")
    
    # English synthesis
    pcm_en, sr_en, lat_en = tts.synthesize("Hello world", "en")
    assert len(pcm_en) > 1000
    assert sr_en in [16000, 22050]
    assert lat_en > 0

    # Japanese synthesis
    pcm_ja, sr_ja, lat_ja = tts.synthesize("こんにちは", "ja")
    assert len(pcm_ja) > 1000
    assert sr_ja in [16000, 22050]
    assert lat_ja > 0

def test_end_to_end_pipeline_en_to_ja(pipeline):
    """Test complete pipeline from audio to translated speech (EN -> JA)."""
    # Generate realistic audio by synthesizing English text with Piper first
    tts = TTSEngine("models_cache/tts")
    pcm_en, sr_en, _ = tts.synthesize("Hello, how are you today?", "en")
    audio_float32 = (np.frombuffer(pcm_en, dtype=np.int16).astype(np.float32) / 32768.0)

    # Process through pipeline
    metrics = pipeline.process_utterance(audio_float32)
    assert metrics is not None
    assert "hello" in metrics["original_text"].lower()
    assert len(metrics["translated_text"]) > 0
    assert metrics["stt_latency_ms"] > 0
    assert metrics["mt_latency_ms"] > 0
    assert metrics["tts_latency_ms"] > 0
    assert metrics["total_e2e_latency_ms"] > 0
    print(f"\nE2E EN->JA Test Succeeded: {metrics}")

def test_language_swapping(pipeline):
    """Test switching and swapping languages."""
    assert pipeline.source_lang == "en"
    assert pipeline.target_lang == "ja"

    pipeline.swap_languages()
    assert pipeline.source_lang == "ja"
    assert pipeline.target_lang == "en"

    pipeline.swap_languages()
    assert pipeline.source_lang == "en"
    assert pipeline.target_lang == "ja"
