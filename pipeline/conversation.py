"""Two-way conversation manager for bidirectional speech translation."""
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import numpy as np

from pipeline.translator import TranslationPipeline

logger = logging.getLogger(__name__)

@dataclass
class ConversationTurn:
    id: int
    timestamp: float
    speaker_lang: str
    target_lang: str
    original_text: str
    translated_text: str
    stt_latency_ms: float
    mt_latency_ms: float
    tts_latency_ms: float
    total_latency_ms: float

class ConversationManager:
    """Manages two-way conversational flow, history, and direction switching."""
    def __init__(
        self,
        lang_a: str = "en",
        lang_b: str = "ja",
        models_dir: str = "models_cache",
        stt_size: str = "base",
        auto_playback: bool = True
    ):
        self.lang_a = lang_a
        self.lang_b = lang_b
        self.history: List[ConversationTurn] = []
        self._turn_counter = 0

        # Conversation UI callbacks
        self.on_turn_added: Optional[Callable[[ConversationTurn], None]] = None
        self.on_active_direction_changed: Optional[Callable[[str, str], None]] = None

        self.pipeline = TranslationPipeline(
            source_lang=lang_a,
            target_lang=lang_b,
            models_dir=models_dir,
            stt_size=stt_size,
            auto_playback=auto_playback
        )

        self.pipeline.on_pipeline_done = self._handle_pipeline_result

    def _handle_pipeline_result(self, metrics: Dict[str, Any]):
        """Record turn into conversation history."""
        self._turn_counter += 1
        turn = ConversationTurn(
            id=self._turn_counter,
            timestamp=time.time(),
            speaker_lang=metrics["source_language"],
            target_lang=metrics["target_language"],
            original_text=metrics["original_text"],
            translated_text=metrics["translated_text"],
            stt_latency_ms=metrics["stt_latency_ms"],
            mt_latency_ms=metrics["mt_latency_ms"],
            tts_latency_ms=metrics["tts_latency_ms"],
            total_latency_ms=metrics["total_e2e_latency_ms"]
        )
        self.history.append(turn)
        logger.info(f"Recorded Conversation Turn #{turn.id}: [{turn.speaker_lang} -> {turn.target_lang}] '{turn.original_text}'")
        
        if self.on_turn_added:
            self.on_turn_added(turn)

    def set_active_speaker_lang(self, speaker_lang: str):
        """Set who is currently speaking (lang_a, lang_b, or 'auto' for dynamic bilingual switching)."""
        if speaker_lang == "auto":
            target = "auto"
        elif speaker_lang == self.lang_a:
            target = self.lang_b
        elif speaker_lang == self.lang_b:
            target = self.lang_a
        else:
            raise ValueError(f"Unknown language: {speaker_lang}. Expected {self.lang_a}, {self.lang_b}, or 'auto'")

        self.pipeline.set_languages(speaker_lang, target)
        if self.on_active_direction_changed:
            self.on_active_direction_changed(speaker_lang, target)

    def toggle_direction(self):
        """Toggle translation direction between Lang A -> Lang B and Lang B -> Lang A."""
        if self.pipeline.source_lang == "auto":
            self.set_active_speaker_lang(self.lang_a)
        elif self.pipeline.source_lang == self.lang_a:
            self.set_active_speaker_lang(self.lang_b)
        else:
            self.set_active_speaker_lang(self.lang_a)

    def clear_history(self):
        """Clear conversation history."""
        self.history.clear()
        self._turn_counter = 0

    def get_history_as_dicts(self) -> List[Dict[str, Any]]:
        """Return history as JSON-serializable list of dictionaries."""
        return [
            {
                "id": t.id,
                "timestamp": t.timestamp,
                "time_str": time.strftime("%H:%M:%S", time.localtime(t.timestamp)),
                "speaker_lang": t.speaker_lang,
                "target_lang": t.target_lang,
                "original_text": t.original_text,
                "translated_text": t.translated_text,
                "stt_latency_ms": t.stt_latency_ms,
                "mt_latency_ms": t.mt_latency_ms,
                "tts_latency_ms": t.tts_latency_ms,
                "total_latency_ms": t.total_latency_ms
            }
            for t in self.history
        ]
