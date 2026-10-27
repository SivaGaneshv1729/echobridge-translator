"""Unit tests for Practice Deck and Flashcard system."""
import pytest
import os
import tempfile
from pipeline.deck import PracticeDeck, DeckCard
from pipeline.conversation import ConversationTurn

def test_deck_add_and_deduplicate():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "deck.json")
        deck = PracticeDeck(storage_path=path)
        # default cards seeded
        init_len = len(deck.cards)
        assert init_len >= 5

        # Add new card
        c1 = deck.add_card("テスト文章", "テスト文章です。", "Polite note", ["テスト"], "丁寧語", "cafe")
        assert len(deck.cards) == init_len + 1
        assert c1.original_text == "テスト文章"
        assert c1.suggested_correction == "テスト文章です。"

        # Add duplicate
        c2 = deck.add_card("テスト文章", "テスト文章です。", "New note", ["追加単語"], "丁寧語", "cafe")
        assert len(deck.cards) == init_len + 1
        assert c2.id == c1.id
        assert "追加単語" in c2.vocabulary_tips

def test_deck_mark_mastered():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "deck.json")
        deck = PracticeDeck(storage_path=path)
        first_card = deck.cards[0]
        assert first_card.mastered is False
        assert first_card.review_count == 0

        assert deck.mark_mastered(first_card.id, True) is True
        assert first_card.mastered is True
        assert first_card.review_count == 1
        assert first_card.last_reviewed_at is not None

        unmastered = deck.get_review_cards(unmastered_only=True)
        assert first_card not in unmastered

def test_deck_add_from_turn():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "deck.json")
        deck = PracticeDeck(storage_path=path)
        turn = ConversationTurn(
            id=10, timestamp=12345.0, speaker_lang="ja", target_lang="ja",
            original_text="これいくら？", translated_text="500円です。",
            stt_latency_ms=100, mt_latency_ms=100, tts_latency_ms=100, total_latency_ms=300,
            is_coach_turn=True, suggested_correction="これはおいくらですか？",
            grammar_notes="Use おいくらですか with service staff.",
            vocabulary_tips=["おいくら (How much - polite)"],
            politeness_level="丁寧語 (Polite)",
            scenario_id="cafe"
        )
        card = deck.add_from_turn(turn)
        assert card.original_text == "これいくら？"
        assert card.suggested_correction == "これはおいくらですか？"
        assert card.scenario_id == "cafe"
        assert "おいくら (How much - polite)" in card.vocabulary_tips

def test_deck_remove_card():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "deck.json")
        deck = PracticeDeck(storage_path=path)
        card = deck.add_card("削除テスト", "削除テストです。")
        cid = card.id
        assert any(c.id == cid for c in deck.cards)

        assert deck.remove_card(cid) is True
        assert not any(c.id == cid for c in deck.cards)
        assert deck.remove_card("invalid_id") is False
