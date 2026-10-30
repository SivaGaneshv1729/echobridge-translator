"""Integration and Unit Tests for Multi-Key LLM Pools and Rotation in EchoBridge."""
import pytest
from engines.language_coach import LanguageCoachEngine, CoachingResult

def test_key_pool_loading():
    """Verify that all 5 Groq and 5 Gemini keys load correctly from config/api_keys.json."""
    engine = LanguageCoachEngine(provider="groq")
    status = engine.get_key_pool_status()
    assert status["groq_keys_count"] == 5
    assert status["gemini_keys_count"] == 5
    assert status["provider"] == "groq"
    assert status["groq_model"] == "qwen/qwen3.8-27b"
    assert status["gemini_model"] == "gemini-2.5-flash"

def test_key_rotation_advances_on_exhaustion():
    """Verify that key indices rotate modulo key list length."""
    engine = LanguageCoachEngine(provider="groq", groq_keys=["key1", "key2", "key3"])
    assert engine.groq_key_index == 0
    # Simulate failed queries that trigger rotation
    engine.groq_key_index = (engine.groq_key_index + 1) % len(engine.groq_keys)
    assert engine.groq_key_index == 1
    engine.groq_key_index = (engine.groq_key_index + 1) % len(engine.groq_keys)
    assert engine.groq_key_index == 2
    engine.groq_key_index = (engine.groq_key_index + 1) % len(engine.groq_keys)
    assert engine.groq_key_index == 0

def test_groq_live_query():
    """Test live conversational reply and grammar coaching from Groq pool."""
    engine = LanguageCoachEngine(provider="groq")
    result = engine.evaluate_and_reply("こんにちは！おすすめのメニューは何ですか？", practice_lang="ja")
    assert isinstance(result, CoachingResult)
    assert len(result.reply_text) > 5
    assert result.reply_lang == "ja"
    assert result.is_natural is True
    assert len(result.grammar_notes) > 5

def test_gemini_live_query():
    """Test live conversational reply and grammar coaching from Gemini pool."""
    engine = LanguageCoachEngine(provider="gemini")
    result = engine.evaluate_and_reply("京都の金閣寺へはどうやって行きますか？", practice_lang="ja")
    assert isinstance(result, CoachingResult)
    assert len(result.reply_text) > 5
    assert result.reply_lang == "ja"
    assert len(result.grammar_notes) > 0

def test_offline_fallback_when_keys_invalid():
    """Test that engine gracefully falls back to builtin heuristics when given bad keys."""
    engine = LanguageCoachEngine(
        provider="groq",
        groq_keys=["invalid_key_abc"],
        gemini_keys=["invalid_key_xyz"],
        fallback_to_offline=True
    )
    result = engine.evaluate_and_reply("電車を乗る", practice_lang="ja")
    assert isinstance(result, CoachingResult)
    assert result.is_natural is False
    assert "電車に乗る" in result.suggested_correction
