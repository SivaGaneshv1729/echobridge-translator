"""Learning & Fluency Analytics Engine for EchoBridge.

Computes speaking fluency ratings, politeness distributions, scenario completions,
vocabulary acquisition metrics, and persists learning history locally.
"""
import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, date

logger = logging.getLogger(__name__)

@dataclass
class FluencyStats:
    total_turns: int = 0
    coach_turns: int = 0
    natural_turns: int = 0
    needs_correction_turns: int = 0
    fluency_score: float = 100.0  # Percentage 0.0 - 100.0
    practice_seconds: float = 0.0
    politeness_distribution: Dict[str, int] = field(default_factory=lambda: {
        "polite": 0,       # 丁寧語 (Teineigo)
        "humble": 0,       # 謙譲語 (Kenjougo)
        "respectful": 0,   # 尊敬語 (Sonkeigo)
        "casual": 0,       # 普通体・カジュアル
    })
    scenario_distribution: Dict[str, int] = field(default_factory=lambda: {
        "free_talk": 0,
        "cafe": 0,
        "transit": 0,
        "hotel": 0,
        "business": 0,
    })
    vocabulary_collected: List[str] = field(default_factory=list)
    recent_grammar_tips: List[Dict[str, str]] = field(default_factory=list)
    active_days: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FluencyStats":
        return cls(
            total_turns=data.get("total_turns", 0),
            coach_turns=data.get("coach_turns", 0),
            natural_turns=data.get("natural_turns", 0),
            needs_correction_turns=data.get("needs_correction_turns", 0),
            fluency_score=data.get("fluency_score", 100.0),
            practice_seconds=data.get("practice_seconds", 0.0),
            politeness_distribution=data.get("politeness_distribution", {
                "polite": 0, "humble": 0, "respectful": 0, "casual": 0
            }),
            scenario_distribution=data.get("scenario_distribution", {
                "free_talk": 0, "cafe": 0, "transit": 0, "hotel": 0, "business": 0
            }),
            vocabulary_collected=data.get("vocabulary_collected", []),
            recent_grammar_tips=data.get("recent_grammar_tips", []),
            active_days=data.get("active_days", 1)
        )

class AnalyticsEngine:
    """Calculates fluency metrics and aggregates language learner progress."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join("models_cache", "learning_analytics.json")

    def classify_politeness_key(self, raw_label: str) -> str:
        """Categorizes raw politeness text into normalized standard keys."""
        if not raw_label:
            return "casual"
        low = raw_label.lower()
        if "謙譲" in raw_label or "humble" in low:
            return "humble"
        elif "尊敬" in raw_label or "honorific" in low or "respect" in low:
            return "respectful"
        elif "丁寧" in raw_label or "polite" in low or "です" in raw_label or "ます" in raw_label:
            return "polite"
        else:
            return "casual"

    def compute_from_turns(self, turns: List[Any]) -> FluencyStats:
        """Computes comprehensive metrics from a list of ConversationTurn objects."""
        stats = FluencyStats()
        stats.total_turns = len(turns)

        if not turns:
            return stats

        vocab_set = set()
        grammar_tips_list = []
        dates_seen = set()

        for turn in turns:
            # Timestamp tracking for active days
            ts = getattr(turn, "timestamp", None)
            if ts:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts).date()
                else:
                    dt = date.today()
                dates_seen.add(dt.isoformat())

            # Audio duration accumulation
            audio_s = getattr(turn, "total_latency_ms", 1500) / 1000.0
            stats.practice_seconds += audio_s

            is_coach = getattr(turn, "is_coach_turn", False)
            if is_coach:
                stats.coach_turns += 1

                # Fluency check
                is_nat = getattr(turn, "is_natural", True)
                if is_nat:
                    stats.natural_turns += 1
                else:
                    stats.needs_correction_turns += 1

                # Politeness categorization
                polite_raw = getattr(turn, "politeness_level", "")
                p_key = self.classify_politeness_key(polite_raw)
                stats.politeness_distribution[p_key] = stats.politeness_distribution.get(p_key, 0) + 1

                # Scenario categorization
                sc_id = getattr(turn, "scenario_id", "free_talk") or "free_talk"
                stats.scenario_distribution[sc_id] = stats.scenario_distribution.get(sc_id, 0) + 1

                # Vocabulary tips extraction
                v_tips = getattr(turn, "vocabulary_tips", [])
                for v in v_tips:
                    if v and v.strip():
                        vocab_set.add(v.strip())

                # Grammar notes extraction
                g_notes = getattr(turn, "grammar_notes", "")
                orig = getattr(turn, "original_text", "")
                corr = getattr(turn, "suggested_correction", "")
                if g_notes and (not is_nat or corr != orig):
                    grammar_tips_list.append({
                        "original": orig,
                        "correction": corr,
                        "note": g_notes,
                        "scenario": sc_id
                    })

        # Calculate fluency rating
        if stats.coach_turns > 0:
            stats.fluency_score = round((stats.natural_turns / stats.coach_turns) * 100.0, 1)
        else:
            stats.fluency_score = 100.0

        stats.vocabulary_collected = sorted(list(vocab_set))
        stats.recent_grammar_tips = grammar_tips_list[-10:]  # Keep last 10 tips
        stats.active_days = max(1, len(dates_seen))
        stats.practice_seconds = round(stats.practice_seconds, 1)

        return stats

    def save_stats(self, stats: FluencyStats) -> bool:
        """Persists stats to local JSON file for offline recall."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(stats.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved learning analytics to {self.storage_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save learning analytics: {e}")
            return False

    def load_stats(self) -> Optional[FluencyStats]:
        """Loads persisted learning statistics if file exists."""
        if not os.path.exists(self.storage_path):
            return None
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FluencyStats.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load learning analytics: {e}")
            return None

    def generate_markdown_summary(self, stats: FluencyStats) -> str:
        """Creates a clean GitHub markdown formatted report of the user's progress."""
        mins = int(stats.practice_seconds // 60)
        secs = int(stats.practice_seconds % 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        p_total = sum(stats.politeness_distribution.values()) or 1
        polite_pct = round((stats.politeness_distribution.get("polite", 0) / p_total) * 100)
        humble_pct = round((stats.politeness_distribution.get("humble", 0) / p_total) * 100)
        resp_pct = round((stats.politeness_distribution.get("respectful", 0) / p_total) * 100)
        cas_pct = round((stats.politeness_distribution.get("casual", 0) / p_total) * 100)

        lines = [
            "# 📊 EchoBridge Language Fluency & Learning Report",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 🏆 Performance Overview",
            f"- **Overall Fluency Score:** `{stats.fluency_score}%`",
            f"- **Total Utterances Practiced:** `{stats.total_turns}`",
            f"- **Coach Evaluated Turns:** `{stats.coach_turns}`",
            f"- **Natural / Fluent Turns:** `{stats.natural_turns}`",
            f"- **Grammar Tips Triggered:** `{stats.needs_correction_turns}`",
            f"- **Total Practice Duration:** `{time_str}`",
            "",
            "## 🎎 Politeness Dynamics (敬語)",
            f"- **丁寧語 (Polite):** `{stats.politeness_distribution.get('polite', 0)}` ({polite_pct}%)",
            f"- **謙譲語 (Humble):** `{stats.politeness_distribution.get('humble', 0)}` ({humble_pct}%)",
            f"- **尊敬語 (Respectful):** `{stats.politeness_distribution.get('respectful', 0)}` ({resp_pct}%)",
            f"- **普通体 (Casual):** `{stats.politeness_distribution.get('casual', 0)}` ({cas_pct}%)",
            "",
            "## 🗺️ Role-Play Scenario Distribution",
            f"- **🗣️ Daily Talk:** `{stats.scenario_distribution.get('free_talk', 0)}`",
            f"- **🍵 Cafe & Dining:** `{stats.scenario_distribution.get('cafe', 0)}`",
            f"- **🚅 Transit & Navigation:** `{stats.scenario_distribution.get('transit', 0)}`",
            f"- **🏨 Hotel Check-in:** `{stats.scenario_distribution.get('hotel', 0)}`",
            f"- **💼 Business & Interview:** `{stats.scenario_distribution.get('business', 0)}`",
            "",
            f"## 📚 Vocabulary Mastered ({len(stats.vocabulary_collected)} items)",
        ]

        if stats.vocabulary_collected:
            for v in stats.vocabulary_collected[:15]:
                lines.append(f"- 💡 {v}")
        else:
            lines.append("_No vocabulary collected yet. Practice with the AI Coach to build your deck!_")

        if stats.recent_grammar_tips:
            lines.append("")
            lines.append("## ⚡ Key Learning Points & Corrections")
            for tip in stats.recent_grammar_tips[-5:]:
                lines.append(f"- **You said:** *\"{tip.get('original', '')}\"*")
                lines.append(f"  **Suggested:** **\"{tip.get('correction', '')}\"**")
                lines.append(f"  **Note:** {tip.get('note', '')}")

        return "\n".join(lines)
