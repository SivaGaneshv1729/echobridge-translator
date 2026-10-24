import os
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import pytest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.conversation import ConversationManager
from engines.text_to_speech import TTSEngine

@pytest.fixture(scope="module")
def conversation_manager():
    mgr = ConversationManager(
        lang_a="en",
        lang_b="ja",
        models_dir="models_cache",
        stt_size="base",
        auto_playback=False
    )
    return mgr

def test_bidirectional_turn_taking(conversation_manager):
    """Test sequential turns in both directions."""
    tts = TTSEngine("models_cache/tts")

    # Turn 1: English Speaker says "Good morning, how can I help you?"
    conversation_manager.set_active_speaker_lang("en")
    pcm_en, _, _ = tts.synthesize("Good morning, how can I help you?", "en")
    audio_en = np.frombuffer(pcm_en, dtype=np.int16).astype(np.float32) / 32768.0

    metrics_1 = conversation_manager.pipeline.process_utterance(audio_en)
    assert metrics_1 is not None
    assert metrics_1["source_language"] == "en"
    assert metrics_1["target_language"] == "ja"
    assert "morning" in metrics_1["original_text"].lower() or "good" in metrics_1["original_text"].lower()
    assert len(metrics_1["translated_text"]) > 0

    # Turn 2: Japanese Speaker responds
    conversation_manager.set_active_speaker_lang("ja")
    pcm_ja, sr_ja, _ = tts.synthesize("こんにちは、駅に行きたいです。", "ja")
    audio_ja = np.frombuffer(pcm_ja, dtype=np.int16).astype(np.float32) / 32768.0
    
    # Resample from TTS sample rate (22050 Hz) to Whisper expected sample rate (16000 Hz)
    if sr_ja != 16000:
        import scipy.signal
        num_16k_samples = int(len(audio_ja) * 16000 / sr_ja)
        audio_ja = scipy.signal.resample(audio_ja, num_16k_samples).astype(np.float32)

    metrics_2 = conversation_manager.pipeline.process_utterance(audio_ja)
    assert metrics_2 is not None
    assert metrics_2["source_language"] == "ja"
    assert metrics_2["target_language"] == "en"
    assert len(metrics_2["translated_text"]) > 0

    # Verify history
    history = conversation_manager.get_history_as_dicts()
    assert len(history) >= 2
    assert history[-2]["speaker_lang"] == "en"
    assert history[-1]["speaker_lang"] == "ja"
    print(f"\nTurn 1 (EN->JA): {history[-2]['original_text']} -> {history[-2]['translated_text']}")
    print(f"Turn 2 (JA->EN): {history[-1]['original_text']} -> {history[-1]['translated_text']}")

def test_toggle_direction(conversation_manager):
    """Test direction toggling."""
    conversation_manager.set_active_speaker_lang("en")
    assert conversation_manager.pipeline.source_lang == "en"
    assert conversation_manager.pipeline.target_lang == "ja"

    conversation_manager.toggle_direction()
    assert conversation_manager.pipeline.source_lang == "ja"
    assert conversation_manager.pipeline.target_lang == "en"

    conversation_manager.toggle_direction()
    assert conversation_manager.pipeline.source_lang == "en"
    assert conversation_manager.pipeline.target_lang == "ja"

def test_automatic_vice_versa_translation(conversation_manager):
    """Test automatic bidirectional translation without clicking swap language."""
    tts = TTSEngine("models_cache/tts")
    conversation_manager.set_active_speaker_lang("auto")
    assert conversation_manager.pipeline.source_lang == "auto"

    # Turn 1: English utterance without specifying language
    pcm_en, _, _ = tts.synthesize("Where is the station?", "en")
    audio_en = np.frombuffer(pcm_en, dtype=np.int16).astype(np.float32) / 32768.0
    m_en = conversation_manager.pipeline.process_utterance(audio_en)
    assert m_en is not None
    assert m_en["source_language"] == "en"
    assert m_en["target_language"] == "ja"
    assert len(m_en["translated_text"]) > 0

    # Turn 2: Japanese utterance immediately following without swapping
    pcm_ja, sr_ja, _ = tts.synthesize("駅はあそこにあります。", "ja")
    audio_ja = np.frombuffer(pcm_ja, dtype=np.int16).astype(np.float32) / 32768.0
    if sr_ja != 16000:
        import scipy.signal
        audio_ja = scipy.signal.resample(audio_ja, int(len(audio_ja) * 16000 / sr_ja)).astype(np.float32)
    m_ja = conversation_manager.pipeline.process_utterance(audio_ja)
    assert m_ja is not None
    assert m_ja["source_language"] == "ja"
    assert m_ja["target_language"] == "en"
    assert len(m_ja["translated_text"]) > 0
