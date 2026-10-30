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

        # Step 1: Pre-detect language in bilingual mode (language=None)
        # This prevents Whisper from decoding in an arbitrary wrong language on acoustic noise
        resolved_decode_lang = language
        if language is None:
            try:
                detected_candidate, prob, all_probs = self.model.detect_language(audio_data)
                probs = dict(all_probs) if all_probs else {}
                if detected_candidate in ("en", "ja"):
                    resolved_decode_lang = detected_candidate
                else:
                    # Disambiguate between English and Japanese
                    resolved_decode_lang = "ja" if probs.get("ja", 0.0) > probs.get("en", 0.0) else "en"
                logger.debug(f"Pre-detected language: {resolved_decode_lang} (raw: {detected_candidate}, prob: {prob:.2f})")
            except Exception as e:
                logger.debug(f"Language pre-detection fallback: {e}")
                resolved_decode_lang = None

        # Step 2: Build dynamic context-aware prompt using conversation history & resolved language
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
            if resolved_decode_lang == "en":
                prompt_parts.append("Conversational English dialogue: Clear speech, punctuation, question marks, and full sentences.")
            elif resolved_decode_lang == "ja":
                prompt_parts.append("自然な日本語の会話：です、ます、敬語、日常表現、句読点を含む丁寧な対話。")
            else:
                prompt_parts.append("Bilingual English and Japanese natural conversation: Hello, こんにちは, よろしくお願いします。")

        full_prompt = " ".join(prompt_parts)

        # Step 3: Standard hotwords for travel, everyday dialogue, and polite speech
        default_hotwords = hotwords
        if not default_hotwords:
            if resolved_decode_lang == "ja":
                default_hotwords = "駅 改札 切符 売り場 切符売り場 おすすめ お願いします ありがとうございます です ます どこ 新幹線 ホテル 注文 メニュー 会計 領収書 トイレ 出口 空港"
            elif resolved_decode_lang == "en":
                default_hotwords = "station ticket platform entrance recommend please thank you bill check where directions hotel airport"

        # Step 4: Transcribe using resolved decode language
        try:
            segments, info = self.model.transcribe(
                audio_data,
                language=resolved_decode_lang,
                beam_size=beam_size,
                best_of=best_of,
                patience=patience,
                temperature=temperature,
                initial_prompt=full_prompt,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                hallucination_silence_threshold=1.2,
                hotwords=default_hotwords,
                condition_on_previous_text=False,
                vad_filter=False  # Upstream Silero VAD already handled segmentation
            )
        except TypeError:
            # Fallback for environments with minimal parameter signatures
            segments, info = self.model.transcribe(
                audio_data,
                language=resolved_decode_lang,
                beam_size=beam_size,
                temperature=temperature,
                initial_prompt=full_prompt,
                condition_on_previous_text=False,
                vad_filter=False
            )

        # Step 5: Filter hallucinations, repetitive artifacts, and low-confidence non-speech segments
        known_hallucinations = {
            "thank you", "thank you.", "thank you very much.", "thank you for watching.",
            "thanks for watching.", "thanks for watching", "please subscribe.",
            "subscribe to my channel.", "subtitles by", "translated by", "bye.", "bye bye.",
            "see you next time.", "[music]", "(music)", "[applause]", "(applause)",
            "...", "..", ".", "you", "so", "oh",
            "ご視聴ありがとうございました", "ご視聴ありがとうございました。",
            "チャンネル登録お願いします", "チャンネル登録をお願いします",
            "チャンネル登録", "字幕", "おやすみなさい", "ではまた"
        }

        text_segments = []
        for s in segments:
            text = s.text.strip()
            if not text:
                continue

            # Check segment compression ratio and no-speech probability
            if getattr(s, "no_speech_prob", 0.0) > 0.65 and getattr(s, "avg_logprob", 0.0) < -1.0:
                continue
            if getattr(s, "compression_ratio", 1.0) > 2.4:
                continue

            cleaned_check = text.strip(" !?.,;:~()[]{}\"'\u3001\u3002\uFF01\uFF1F").lower()
            if cleaned_check in known_hallucinations:
                continue

            text_segments.append(text)

        full_text = " ".join(text_segments).strip()

        # Step 6: Determine detected language
        detected_lang = resolved_decode_lang or (info.language if info else (language or "unknown"))

        # Step 7: Post-transcription script consistency validation
        if full_text:
            import re
            has_japanese_chars = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', full_text))
            has_latin_chars = bool(re.search(r'[A-Za-z]{2,}', full_text))

            if has_japanese_chars and not has_latin_chars:
                detected_lang = "ja"
            elif has_latin_chars and not has_japanese_chars:
                detected_lang = "en"

        latency_ms = (time.perf_counter() - t0) * 1000

        logger.debug(f"Transcribed ({detected_lang}) in {latency_ms:.2f}ms: '{full_text}'")
        return full_text, detected_lang, latency_ms
