"""Practice Deck & Flashcard Manager for EchoBridge.

Enables learners to bookmark corrections, vocabulary tips, and role-play phrases,
and review them later using spaced repetition or flip-card study mode.
"""
import os
import json
import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class DeckCard:
    id: str
    original_text: str
    suggested_correction: str
    grammar_notes: str = ""
    vocabulary_tips: List[str] = field(default_factory=list)
    politeness_level: str = ""
    scenario_id: str = "free_talk"
    mastered: bool = False
    review_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_reviewed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeckCard":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            original_text=data.get("original_text", ""),
            suggested_correction=data.get("suggested_correction", ""),
            grammar_notes=data.get("grammar_notes", ""),
            vocabulary_tips=data.get("vocabulary_tips", []),
            politeness_level=data.get("politeness_level", ""),
            scenario_id=data.get("scenario_id", "free_talk"),
            mastered=data.get("mastered", False),
            review_count=data.get("review_count", 0),
            created_at=data.get("created_at", time.time()),
            last_reviewed_at=data.get("last_reviewed_at")
        )

class PracticeDeck:
    """Manages the collection of saved vocabulary and grammar review cards."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join("models_cache", "practice_deck.json")
        self.cards: List[DeckCard] = []
        self.load()

    def add_card(
        self,
        original_text: str,
        suggested_correction: str,
        grammar_notes: str = "",
        vocabulary_tips: Optional[List[str]] = None,
        politeness_level: str = "",
        scenario_id: str = "free_talk"
    ) -> DeckCard:
        """Adds a new flashcard to the practice deck or updates an existing identical entry."""
        # Check duplicate
        for c in self.cards:
            if c.original_text == original_text and c.suggested_correction == suggested_correction:
                c.grammar_notes = grammar_notes or c.grammar_notes
                if vocabulary_tips:
                    c.vocabulary_tips = list(set(c.vocabulary_tips + vocabulary_tips))
                self.save()
                return c

        card = DeckCard(
            id=str(uuid.uuid4())[:8],
            original_text=original_text,
            suggested_correction=suggested_correction,
            grammar_notes=grammar_notes,
            vocabulary_tips=vocabulary_tips or [],
            politeness_level=politeness_level,
            scenario_id=scenario_id,
            created_at=time.time()
        )
        self.cards.append(card)
        self.save()
        logger.info(f"Added new flashcard #{card.id}: '{original_text}' ➔ '{suggested_correction}'")
        return card

    def add_from_turn(self, turn: Any) -> DeckCard:
        """Constructs a card directly from a ConversationTurn object."""
        orig = getattr(turn, "original_text", "")
        corr = getattr(turn, "suggested_correction", "") or orig
        notes = getattr(turn, "grammar_notes", "")
        vocab = getattr(turn, "vocabulary_tips", [])
        polite = getattr(turn, "politeness_level", "")
        sc = getattr(turn, "scenario_id", "free_talk")
        return self.add_card(
            original_text=orig,
            suggested_correction=corr,
            grammar_notes=notes,
            vocabulary_tips=vocab,
            politeness_level=polite,
            scenario_id=sc
        )

    def remove_card(self, card_id: str) -> bool:
        """Deletes a card from the deck."""
        before = len(self.cards)
        self.cards = [c for c in self.cards if c.id != card_id]
        if len(self.cards) < before:
            self.save()
            return True
        return False

    def mark_mastered(self, card_id: str, mastered: bool = True) -> bool:
        """Toggles mastered status for a card."""
        for c in self.cards:
            if c.id == card_id:
                c.mastered = mastered
                c.review_count += 1
                c.last_reviewed_at = time.time()
                self.save()
                return True
        return False

    def get_review_cards(self, unmastered_only: bool = False) -> List[DeckCard]:
        """Returns cards ready for practice review."""
        if unmastered_only:
            return [c for c in self.cards if not c.mastered]
        return list(self.cards)

    @property
    def total_count(self) -> int:
        return len(self.cards)

    @property
    def mastered_count(self) -> int:
        return sum(1 for c in self.cards if c.mastered)

    def save(self) -> bool:
        """Saves practice deck to local JSON file."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self.cards], f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save practice deck: {e}")
            return False

    def load(self) -> bool:
        """Loads practice deck from local JSON file."""
        if not os.path.exists(self.storage_path):
            # Seed default starter cards for role-play situations
            self._seed_default_cards()
            return True
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cards = [DeckCard.from_dict(item) for item in data]
            return True
        except Exception as e:
            logger.error(f"Failed to load practice deck: {e}")
            return False

    def _seed_default_cards(self):
        """Seeds essential starter phrases across scenarios."""
        seeds = [
            ("アイスコーヒーをひとつ、お願い。", "アイスコーヒーをひとつ、お願いします。", "Use お願いします rather than bare お願い when speaking to staff.", ["ひとつ (One item)"], "丁寧語 (Polite)", "cafe"),
            ("東京駅に行くの電車はどこ？", "東京駅に行く電車はどこですか？", "Do not put の between verb 行く and noun 電車.", ["行く電車 (Train that goes)"], "丁寧語 (Polite)", "transit"),
            ("チェックインをしたいです。", "チェックインをお願いできますでしょうか。", "More sophisticated impression at hotel reception.", ["チェックイン (Check-in)"], "謙譲・丁寧 (Respectful)", "hotel"),
            ("今日の資料を見ました。", "本日の資料を拝見いたしました。", "Use 本日 and humble 拝見いたしました in business contexts.", ["拝見する (To see - humble)"], "謙譲語 (Humble)", "business"),
            ("昨日はとても楽しかったよ。", "昨日はとても楽しかったです！", "Polite and cheerful phrasing for daily conversation.", ["楽しかったです (Was fun!)"], "丁寧語 (Polite)", "free_talk")
        ]
        for orig, corr, notes, vocab, polite, sc in seeds:
            self.cards.append(DeckCard(
                id=str(uuid.uuid4())[:8],
                original_text=orig,
                suggested_correction=corr,
                grammar_notes=notes,
                vocabulary_tips=vocab,
                politeness_level=polite,
                scenario_id=sc
            ))
        self.save()
