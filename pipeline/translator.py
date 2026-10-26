"""End-to-End Real-Time Offline Speech Translation Pipeline with Non-Blocking Worker Queue."""
import time
import queue
import threading
import logging
from typing import Optional, Callable, Dict, Any
import numpy as np

from audio.vad import SileroVAD, UtteranceSegmenter
from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from engines.speech_recognition import SpeechRecognizer
from engines.translation import TranslatorEngine
from engines.text_to_speech import TTSEngine
from engines.language_coach import LanguageCoachEngine

logger = logging.getLogger(__name__)

class TranslationPipeline:
    def __init__(
        self,
        source_lang: str = "en",
        target_lang: str = "ja",
        models_dir: str = "models_cache",
        stt_size: str = "base",
        input_device_index: Optional[int] = None,
        output_device_index: Optional[int] = None,
        auto_playback: bool = True
    ):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.models_dir = models_dir
        self.auto_playback = auto_playback
        self.app_mode: str = "translate"     # "translate" or "coach"
        self.practice_lang: str = "ja"       # Target language user is practicing
        self.coach = LanguageCoachEngine()

        # Event callbacks
        self.on_audio_level: Optional[Callable[[float], None]] = None
        self.on_speech_detected: Optional[Callable[[], None]] = None
        self.on_transcription: Optional[Callable[[str, str, float], None]] = None
        self.on_translation: Optional[Callable[[str, float], None]] = None
        self.on_synthesis: Optional[Callable[[bytes, int, float], None]] = None
        self.on_pipeline_done: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Initialize audio and VAD
        logger.info("Initializing EchoBridge Pipeline components...")
        self.vad = SileroVAD(f"{models_dir}/vad/silero_vad.onnx", threshold=0.35)
        self.segmenter = UtteranceSegmenter(self.vad, min_speech_duration_ms=150, min_silence_duration_ms=400, speech_pad_ms=300)
        self.segmenter.on_speech_started = self._on_speech_started
        
        self.capture = AudioCapture(device_index=input_device_index, chunk_callback=self._on_audio_chunk)
        self.capture.level_callback = lambda lvl: self.on_audio_level(lvl) if self.on_audio_level else None
        self.playback = AudioPlayback(device_index=output_device_index)
        
        # Initialize engines
        self.stt = SpeechRecognizer(model_size=stt_size)
        self.translation = TranslatorEngine(f"{models_dir}/translation")
        self.tts = TTSEngine(f"{models_dir}/tts")

        # Preload models
        if self.source_lang in ("auto", None) or self.target_lang in ("auto", None):
            self.translation.load_pair("en", "ja")
            self.translation.load_pair("ja", "en")
            self.tts.load_voice("ja")
            self.tts.load_voice("en")
        else:
            self.translation.load_pair(self.source_lang, self.target_lang)
            self.translation.load_pair(self.target_lang, self.source_lang)
            self.tts.load_voice(self.target_lang)
            self.tts.load_voice(self.source_lang)

        # Worker thread for non-blocking asynchronous utterance processing
        self._utterance_queue = queue.Queue()
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        logger.info("EchoBridge Pipeline initialized and worker thread running.")

    def set_languages(self, source: str, target: str):
        """Update active translation direction."""
        self.source_lang = source
        self.target_lang = target
        if source in ("auto", None) or target in ("auto", None):
            self.translation.load_pair("en", "ja")
            self.translation.load_pair("ja", "en")
            self.tts.load_voice("ja")
            self.tts.load_voice("en")
            logger.info("Pipeline active language pair set to: AUTO-DETECT (EN ⇄ JA)")
        else:
            self.translation.load_pair(source, target)
            self.tts.load_voice(target)
            logger.info(f"Pipeline active language pair set to: {source} -> {target}")

    def swap_languages(self):
        """Swap source and target languages."""
        if self.source_lang == "auto":
            return
        self.set_languages(self.target_lang, self.source_lang)

    def _on_speech_started(self):
        """Invoked immediately when speech is detected (start of utterance)."""
        if self.on_speech_detected:
            try:
                self.on_speech_detected()
            except Exception as e:
                logger.error(f"Error in on_speech_detected: {e}")

    def _on_audio_chunk(self, chunk_512: np.ndarray):
        """Callback invoked for every 512-sample audio chunk from microphone."""
        # Acoustic feedback prevention: Do not process audio while speakers are playing translated output
        if self.playback.is_playing:
            self.segmenter.reset()
            return

        utterance = self.segmenter.process_chunk(chunk_512)
        if utterance is not None:
            # Push to background worker queue so PortAudio callback returns in <0.1ms
            self._utterance_queue.put(utterance)

    def _worker_loop(self):
        """Dedicated background thread loop that runs STT, MT, and TTS without freezing audio capture."""
        while self._worker_running:
            try:
                utterance = self._utterance_queue.get(timeout=0.2)
                if utterance is not None:
                    self.process_utterance(utterance)
                self._utterance_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in pipeline worker loop: {e}", exc_info=True)

    def process_utterance(self, audio_data: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Process a single completed speech utterance through the full translation pipeline:
        Audio -> STT -> MT -> TTS -> Playback
        """
        if audio_data is None or len(audio_data) < 2400: # Need at least 150ms of audio
            logger.info(f"Ignored short audio chunk ({len(audio_data) if audio_data is not None else 0} samples)")
            return None

        # 1. High-Pass Filter (75Hz) to remove mechanical desk thumps and low-frequency rumble
        try:
            import scipy.signal
            sos = scipy.signal.butter(2, 75, btype='highpass', fs=16000, output='sos')
            audio_data = scipy.signal.sosfilt(sos, audio_data).astype(np.float32)
        except Exception:
            pass

        # 2. Add 150ms (2400 samples) of clean silence padding on both ends to eliminate Whisper edge artifacts
        audio_data = np.pad(audio_data, (2400, 2400), mode="constant")

        t_start = time.perf_counter()
        
        # 3. Dynamic Peak Normalization / AGC for quiet laptop microphones
        max_amp = float(np.max(np.abs(audio_data)))
        if max_amp > 1e-4:
            gain = min(15.0, 0.75 / max_amp)
            if gain > 1.05:
                audio_data = np.clip(audio_data * gain, -1.0, 1.0).astype(np.float32)
                logger.info(f"Applied audio precision boost: {gain:.1f}x (original peak: {max_amp:.3f})")

        logger.info(f"Processing speech utterance ({len(audio_data)/16000:.2f}s of audio)...")

        try:
            # 1. Speech Recognition (Auto-detect language if in auto mode)
            stt_lang = None if self.source_lang in ("auto", None) else self.source_lang
            orig_text, detected_lang, stt_ms = self.stt.transcribe(
                audio_data,
                language=stt_lang
            )
            if not orig_text.strip():
                logger.info("Transcribed text was empty (no clear speech recognized).")
                return None

            # Resolve actual source and target language for translation and speech synthesis
            if self.source_lang in ("auto", None):
                if detected_lang == "ja":
                    act_source = "ja"
                    act_target = "en"
                else:
                    act_source = "en"
                    act_target = "ja"
            else:
                act_source = self.source_lang
                act_target = self.target_lang

            if self.on_transcription:
                self.on_transcription(orig_text, act_source, stt_ms)

            # Special Path: AI Language Coach & Conversational Partner Mode
            if self.app_mode == "coach":
                coach_lang = self.practice_lang if self.practice_lang in ("ja", "en") else act_source
                logger.info(f"Evaluating utterance with AI Language Coach ({coach_lang}): '{orig_text}'")
                coach_res = self.coach.evaluate_and_reply(orig_text, practice_lang=coach_lang)

                if self.on_translation:
                    self.on_translation(coach_res.reply_text, 0.0)

                # Synthesize coach's conversational reply aloud in the practice language
                audio_bytes, sample_rate, tts_ms = self.tts.synthesize(
                    coach_res.reply_text,
                    lang=coach_lang
                )
                if self.on_synthesis:
                    self.on_synthesis(audio_bytes, sample_rate, tts_ms)

                total_ms = (time.perf_counter() - t_start) * 1000

                if self.auto_playback and len(audio_bytes) > 0:
                    self.playback.play_raw_bytes(audio_bytes, sample_rate=sample_rate, blocking=False)

                metrics = {
                    "original_text": orig_text,
                    "detected_language": detected_lang,
                    "translated_text": coach_res.reply_text,
                    "source_language": coach_lang,
                    "target_language": coach_lang,
                    "is_coach_turn": True,
                    "coach_reply": coach_res.reply_text,
                    "suggested_correction": coach_res.suggested_correction,
                    "is_natural": coach_res.is_natural,
                    "politeness_level": coach_res.politeness_level,
                    "grammar_notes": coach_res.grammar_notes,
                    "vocabulary_tips": coach_res.vocabulary_tips,
                    "audio_duration_s": round(len(audio_data) / 16000, 2),
                    "stt_latency_ms": round(stt_ms, 2),
                    "mt_latency_ms": 0.0,
                    "tts_latency_ms": round(tts_ms, 2),
                    "total_e2e_latency_ms": round(total_ms, 2)
                }
                if self.on_pipeline_done:
                    self.on_pipeline_done(metrics)
                return metrics

            # 2. Machine Translation (Standard Bilingual Mode)
            translated_text, mt_ms = self.translation.translate(
                orig_text,
                from_code=act_source,
                to_code=act_target
            )
            if not translated_text.strip():
                logger.info("Translated text was empty, skipping.")
                return None

            if self.on_translation:
                self.on_translation(translated_text, mt_ms)

            # 3. Text-to-Speech Synthesis
            audio_bytes, sample_rate, tts_ms = self.tts.synthesize(
                translated_text,
                lang=act_target
            )

            if self.on_synthesis:
                self.on_synthesis(audio_bytes, sample_rate, tts_ms)

            total_ms = (time.perf_counter() - t_start) * 1000

            # 4. Speaker Playback
            if self.auto_playback and len(audio_bytes) > 0:
                self.playback.play_raw_bytes(audio_bytes, sample_rate=sample_rate, blocking=False)

            metrics = {
                "original_text": orig_text,
                "detected_language": detected_lang,
                "translated_text": translated_text,
                "source_language": act_source,
                "target_language": act_target,
                "audio_duration_s": round(len(audio_data) / 16000, 2),
                "stt_latency_ms": round(stt_ms, 2),
                "mt_latency_ms": round(mt_ms, 2),
                "tts_latency_ms": round(tts_ms, 2),
                "total_e2e_latency_ms": round(total_ms, 2)
            }

            logger.info(f"Pipeline Completed: [{act_source} -> {act_target}] '{orig_text}' -> '{translated_text}' [Total: {total_ms:.1f}ms (STT: {stt_ms:.1f}ms, MT: {mt_ms:.1f}ms, TTS: {tts_ms:.1f}ms)]")

            if self.on_pipeline_done:
                self.on_pipeline_done(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error in translation pipeline: {e}", exc_info=True)
            if self.on_error:
                self.on_error(str(e))
            return None

    def start_listening(self):
        """Start capturing microphone audio."""
        self.segmenter.reset()
        self.capture.start()

    def stop_listening(self, flush: bool = True):
        """Stop microphone audio capture. If flush=True, process any pending speech recorded before stopping."""
        self.capture.stop()
        if flush:
            flushed_utterance = self.segmenter.flush()
            if flushed_utterance is not None and len(flushed_utterance) >= 2400:
                logger.info(f"Flushing {len(flushed_utterance)/16000:.2f}s of audio on stop_listening")
                self._utterance_queue.put(flushed_utterance)
        else:
            self.segmenter.reset()
