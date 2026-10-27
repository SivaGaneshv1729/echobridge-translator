"""Unit test suite for the AI Language Coach and Conversational Tutor."""
import os
import pytest
from PySide6.QtWidgets import QApplication

from engines.language_coach import LanguageCoachEngine, CoachingResult
from pipeline.conversation import ConversationManager, ConversationTurn
from ui.conversation_view import CoachingBubble, ConversationView

@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_coach_engine_japanese_particle_correction():
    engine = LanguageCoachEngine(provider="builtin")
    # Missing direction particle へ / に
    res = engine.evaluate_and_reply("どこ行きますか？", practice_lang="ja")
    assert isinstance(res, CoachingResult)
    assert res.is_natural is False
    assert "へ" in res.suggested_correction or "に" in res.suggested_correction
    assert len(res.reply_text) > 0
    assert "Polite" in res.politeness_level or "丁寧語" in res.politeness_level
    assert "particle" in res.grammar_notes.lower() or "助詞" in res.grammar_notes

def test_coach_engine_japanese_fluent_sentence():
    engine = LanguageCoachEngine(provider="builtin")
    res = engine.evaluate_and_reply("駅はどこですか？", practice_lang="ja")
    assert res.is_natural is True
    assert "Polite" in res.politeness_level or "丁寧語" in res.politeness_level
    assert len(res.reply_text) > 0

def test_coach_engine_english_article_correction():
    engine = LanguageCoachEngine(provider="builtin")
    # Missing article "the"
    res = engine.evaluate_and_reply("where is station?", practice_lang="en")
    assert res.is_natural is False
    assert "where is the station" in res.suggested_correction.lower()
    assert "article" in res.grammar_notes.lower()
    assert len(res.reply_text) > 0

def test_coach_engine_english_fluent():
    engine = LanguageCoachEngine(provider="builtin")
    res = engine.evaluate_and_reply("Hello, how are you today?", practice_lang="en")
    assert res.is_natural is True
    assert len(res.reply_text) > 0

def test_coaching_bubble_widget(qapp):
    turn_data = {
        "speaker_lang": "ja",
        "target_lang": "ja",
        "original_text": "どこ行きますか？",
        "translated_text": "どこへ行きますか？案内しましょうか？",
        "is_coach_turn": True,
        "suggested_correction": "どこへ行きますか？",
        "is_natural": False,
        "politeness_level": "Polite (丁寧語)",
        "grammar_notes": "Added direction particle 'へ' for natural destination marking.",
        "vocabulary_tips": ["行く (iku) = to go", "案内 (annai) = guidance"],
        "total_latency_ms": 320.0,
        "stt_latency_ms": 200.0,
        "mt_latency_ms": 1.0,
        "tts_latency_ms": 119.0,
        "time_str": "12:00:00"
    }

    bubble = CoachingBubble(turn_data)
    assert bubble.orig_label.text() == "どこ行きますか？"
    assert bubble.reply_label.text() == "どこへ行きますか？案内しましょうか？"
    
    replayed = []
    bubble.replay_requested.connect(lambda text, lang: replayed.append((text, lang)))
    bubble.replay_btn.click()
    assert len(replayed) == 1
    assert replayed[0] == ("どこへ行きますか？案内しましょうか？", "ja")
    bubble.deleteLater()

def test_conversation_view_with_coach_and_export(qapp, tmp_path):
    cv = ConversationView()
    coach_turn = {
        "speaker_lang": "ja",
        "target_lang": "ja",
        "original_text": "どこ行きますか？",
        "translated_text": "どこへ行きますか？案内しましょうか？",
        "is_coach_turn": True,
        "suggested_correction": "どこへ行きますか？",
        "is_natural": False,
        "politeness_level": "Polite (丁寧語)",
        "grammar_notes": "Added direction particle 'へ'.",
        "vocabulary_tips": ["行く (iku) = to go"],
        "total_latency_ms": 250.0,
        "time_str": "12:05:00"
    }
    cv.add_turn(coach_turn)
    assert cv.empty_hero.isHidden()

    # Test export to file
    out_file = str(tmp_path / "coach_transcript.txt")
    cv.export_to_text(out_file, [coach_turn])
    assert os.path.exists(out_file)

    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "AI COACH - JA PRACTICE" in content
    assert "Student Said:       どこ行きますか？" in content
    assert "Suggested Phrasing: どこへ行きますか？" in content
    assert "Grammar Coaching:   Added direction particle 'へ'." in content
    cv.deleteLater()

def test_coach_multi_turn_memory():
    engine = LanguageCoachEngine(provider="builtin", scenario="free_talk")
    # Turn 1: Self-introduction with user name
    res1 = engine.evaluate_and_reply("私は田中健二です。よろしくお願いします。", practice_lang="ja")
    assert engine.memory_store["user_name"] == "田中健二"
    assert len(engine.conversation_history) == 2

    # Turn 2: Mention hobby
    res2 = engine.evaluate_and_reply("趣味は映画を見ることです。", practice_lang="ja")
    assert len(engine.conversation_history) == 4
    assert any("映画" in tip or "映画" in res2.reply_text for tip in (res2.vocabulary_tips or [res2.reply_text]))

    # Test clearing history
    engine.clear_history()
    assert len(engine.conversation_history) == 0
    assert engine.memory_store["user_name"] is None

def test_coach_scenario_state_progression():
    engine = LanguageCoachEngine(provider="builtin", scenario="cafe")
    # Stage 0 -> 1: Order item
    res1 = engine.evaluate_and_reply("アイスカフェラテをひとつお願いします。", practice_lang="ja")
    assert engine.memory_store["scenario_stage"] >= 2
    assert "サイズ" in res1.reply_text or "店内" in res1.reply_text

    # Stage 2 -> 3: Customization (M size, dine-in)
    res2 = engine.evaluate_and_reply("Mサイズで、店内でお願いします。", practice_lang="ja")
    assert engine.memory_store["scenario_stage"] >= 3
    assert "円" in res2.reply_text or "会計" in res2.reply_text

