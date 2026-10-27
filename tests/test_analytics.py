"""Unit tests for Learning & Fluency Analytics Engine."""
import pytest
import os
import tempfile
from pipeline.conversation import ConversationTurn
from pipeline.analytics import AnalyticsEngine, FluencyStats

def test_politeness_classification():
    engine = AnalyticsEngine()
    assert engine.classify_politeness_key("丁寧語 (Polite)") == "polite"
    assert engine.classify_politeness_key("謙譲語 (Humble)") == "humble"
    assert engine.classify_politeness_key("尊敬語 (Respectful)") == "respectful"
    assert engine.classify_politeness_key("タメ口 / カジュアル") == "casual"
    assert engine.classify_politeness_key("") == "casual"

def test_compute_empty_turns():
    engine = AnalyticsEngine()
    stats = engine.compute_from_turns([])
    assert stats.total_turns == 0
    assert stats.coach_turns == 0
    assert stats.fluency_score == 100.0
    assert stats.vocabulary_collected == []

def test_compute_fluency_metrics():
    engine = AnalyticsEngine()
    turns = [
        ConversationTurn(
            id=1, timestamp=1000.0, speaker_lang="ja", target_lang="ja",
            original_text="これをお願いします。", translated_text="かしこまりました。",
            stt_latency_ms=200, mt_latency_ms=100, tts_latency_ms=200, total_latency_ms=1200,
            is_coach_turn=True, is_natural=True, politeness_level="丁寧語 (Polite)",
            scenario_id="cafe", vocabulary_tips=["ひとつ (One item)", "お願いします (Please)"]
        ),
        ConversationTurn(
            id=2, timestamp=1010.0, speaker_lang="ja", target_lang="ja",
            original_text="駅はどこ？", translated_text="駅はあちらです。",
            stt_latency_ms=200, mt_latency_ms=100, tts_latency_ms=200, total_latency_ms=1500,
            is_coach_turn=True, is_natural=False, politeness_level="カジュアル (Casual)",
            suggested_correction="駅はどこですか？", grammar_notes="Add ですか for politeness.",
            scenario_id="transit", vocabulary_tips=["駅 (Station)"]
        ),
        ConversationTurn(
            id=3, timestamp=1020.0, speaker_lang="ja", target_lang="ja",
            original_text="資料を拝見いたしました。", translated_text="ありがとうございます。",
            stt_latency_ms=200, mt_latency_ms=100, tts_latency_ms=200, total_latency_ms=1800,
            is_coach_turn=True, is_natural=True, politeness_level="謙譲語 (Humble)",
            scenario_id="business", vocabulary_tips=["拝見する (To see - humble)"]
        ),
        ConversationTurn(
            id=4, timestamp=1030.0, speaker_lang="en", target_lang="ja",
            original_text="Hello world", translated_text="こんにちは世界",
            stt_latency_ms=200, mt_latency_ms=100, tts_latency_ms=200, total_latency_ms=1000,
            is_coach_turn=False
        )
    ]

    stats = engine.compute_from_turns(turns)
    assert stats.total_turns == 4
    assert stats.coach_turns == 3
    assert stats.natural_turns == 2
    assert stats.needs_correction_turns == 1
    # 2 out of 3 = 66.7%
    assert abs(stats.fluency_score - 66.7) < 0.1
    assert stats.politeness_distribution["polite"] == 1
    assert stats.politeness_distribution["casual"] == 1
    assert stats.politeness_distribution["humble"] == 1
    assert stats.scenario_distribution["cafe"] == 1
    assert stats.scenario_distribution["transit"] == 1
    assert stats.scenario_distribution["business"] == 1
    assert len(stats.vocabulary_collected) == 4
    assert len(stats.recent_grammar_tips) == 1
    assert stats.recent_grammar_tips[0]["correction"] == "駅はどこですか？"

def test_save_and_load_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_analytics.json")
        engine = AnalyticsEngine(storage_path=path)

        orig_stats = FluencyStats(
            total_turns=10,
            coach_turns=6,
            natural_turns=5,
            needs_correction_turns=1,
            fluency_score=83.3,
            practice_seconds=45.5,
            vocabulary_collected=["コーヒー", "駅"],
            active_days=2
        )

        assert engine.save_stats(orig_stats) is True
        assert os.path.exists(path)

        loaded = engine.load_stats()
        assert loaded is not None
        assert loaded.total_turns == 10
        assert loaded.fluency_score == 83.3
        assert loaded.vocabulary_collected == ["コーヒー", "駅"]

def test_markdown_summary_generation():
    engine = AnalyticsEngine()
    stats = FluencyStats(
        total_turns=5,
        coach_turns=3,
        natural_turns=2,
        needs_correction_turns=1,
        fluency_score=66.7,
        practice_seconds=125.0,
        vocabulary_collected=["抹茶 (Matcha)"],
        recent_grammar_tips=[{
            "original": "行くの電車",
            "correction": "行く電車",
            "note": "Remove の particle.",
            "scenario": "transit"
        }]
    )

    report = engine.generate_markdown_summary(stats)
    assert "# 📊 EchoBridge Language Fluency & Learning Report" in report
    assert "Overall Fluency Score" in report
    assert "66.7%" in report
    assert "抹茶 (Matcha)" in report
    assert "Remove の particle." in report
