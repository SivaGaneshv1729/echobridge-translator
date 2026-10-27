"""Speech Recognition Engine using Faster-Whisper (CTranslate2 INT8)."""
import time
import logging
from typing import Optional, Tuple, List
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class SpeechRecognizer:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        
        import os
        local_dir = os.path.join("models_cache", "stt", f"faster-whisper-{model_size}")
        model_target = local_dir if os.path.isdir(local_dir) else model_size

        logger.info(f"Loading WhisperModel({model_target}, compute_type={compute_type}, threads={cpu_threads})...")
        t0 = time.perf_counter()
        try:
            self.model = WhisperModel(
                model_target,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                local_files_only=True
            )
        except Exception as e:
            logger.info(f"Local files only load failed ({e}), attempting initial download...")
            self.model = WhisperModel(
                model_target,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                local_files_only=False
            )
        logger.info(f"WhisperModel loaded in {(time.perf_counter() - t0)*1000:.2f} ms")

    def transcribe(
        self,
        audio_data: np.ndarray,
        language: Optional[str] = None,
        beam_size: int = 3,
        best_of: int = 3,
        patience: float = 1.0,
        temperature: float = 0.0,
        initial_prompt: Optional[str] = None,
        context_history: Optional[List[str]] = None,
        hotwords: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Transcribe audio numpy array (16kHz mono float32) using multi-turn conversational context knowledge.
        Returns: (transcribed_text, detected_language, latency_ms)
        """
        if audio_data is None or len(audio_data) == 0:
            return "", language or "unknown", 0.0

        t0 = time.perf_counter()

        # Build dynamic context-aware prompt using conversation history
        prompt_parts = []
        if context_history:
            recent_context = " ".join([h.strip() for h in context_history[-4:] if h.strip()])
            if recent_context:
                # Keep context concise to avoid exceeding Whisper prompt tokens
                if len(recent_context) > 280:
                    recent_context = recent_context[-280:]
                prompt_parts.append(f"Conversation context: {recent_context}.")

        if initial_prompt:
            prompt_parts.append(initial_prompt)
        else:
            if language == "en":
                prompt_parts.append("Conversational English dialogue: Clear speech, punctuation, question marks, and full sentences.")
            elif language == "ja":
                prompt_parts.append("自然な日本語の会話：です、ます、敬語、日常表現、句読点を含む丁寧な対話。")
            else:
                prompt_parts.append("Bilingual English and Japanese natural conversation: Hello, こんにちは, よろしくお願いします。")

        full_prompt = " ".join(prompt_parts)

        # Standard hotwords for travel, everyday dialogue, and polite speech
        default_hotwords = hotwords
        if not default_hotwords:
            if language == "ja":
                default_hotwords = "駅 改札 おすすめ お願いします ありがとうございます です ます どこ"
            elif language == "en":
                default_hotwords = "station entrance recommend please thank you bill check where"

        try:
            segments, info = self.model.transcribe(
                audio_data,
                language=language,
                beam_size=beam_size,
                best_of=best_of,
                patience=patience,
                temperature=temperature,
                initial_prompt=full_prompt,
                repetition_penalty=1.1,
                no_repeat_ngram_size=3,
                hallucination_silence_threshold=1.5,
                hotwords=default_hotwords,
                condition_on_previous_text=False,
                vad_filter=False # VAD is already handled upstream
            )
        except TypeError:
            # Fallback for environments with minimal parameter signatures
            segments, info = self.model.transcribe(
                audio_data,
                language=language,
                beam_size=beam_size,
                temperature=temperature,
                initial_prompt=full_prompt,
                condition_on_previous_text=False,
                vad_filter=False
            )
        
        text_segments = [s.text.strip() for s in segments if s.text.strip()]
        full_text = " ".join(text_segments).strip()
        
        detected_lang = info.language if info else (language or "unknown")
        
        # In bilingual mode (EN <-> JA), if language detection picks an outlier code due to ambient noise,
        # resolve directly between en and ja using their probabilities
        if language is None and info and hasattr(info, "all_language_probs") and info.all_language_probs:
            probs = dict(info.all_language_probs)
            if detected_lang not in ("en", "ja"):
                detected_lang = "ja" if probs.get("ja", 0) > probs.get("en", 0) else "en"

        latency_ms = (time.perf_counter() - t0) * 1000

        logger.debug(f"Transcribed ({detected_lang}) in {latency_ms:.2f}ms: '{full_text}'")
        return full_text, detected_lang, latency_ms
