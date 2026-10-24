"""End-to-End Real-Time Offline Speech Translation Pipeline."""
import time
import logging
from typing import Optional, Callable, Dict, Any
import numpy as np

from audio.vad import SileroVAD, UtteranceSegmenter
from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from engines.speech_recognition import SpeechRecognizer
from engines.translation import TranslatorEngine
from engines.text_to_speech import TTSEngine

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

        # Event callbacks
        self.on_speech_detected: Optional[Callable[[], None]] = None
        self.on_transcription: Optional[Callable[[str, str, float], None]] = None
        self.on_translation: Optional[Callable[[str, float], None]] = None
        self.on_synthesis: Optional[Callable[[bytes, int, float], None]] = None
        self.on_pipeline_done: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Initialize components
        logger.info("Initializing EchoBridge Pipeline components...")
        self.vad = SileroVAD(f"{models_dir}/vad/silero_vad.onnx")
        self.segmenter = UtteranceSegmenter(self.vad)
        self.capture = AudioCapture(device_index=input_device_index, chunk_callback=self._on_audio_chunk)
        self.playback = AudioPlayback(device_index=output_device_index)
        
        self.stt = SpeechRecognizer(model_size=stt_size)
        self.translation = TranslatorEngine(f"{models_dir}/translation")
        self.tts = TTSEngine(f"{models_dir}/tts")

        # Preload target engines
        self.translation.load_pair(self.source_lang, self.target_lang)
        self.translation.load_pair(self.target_lang, self.source_lang)
        self.tts.load_voice(self.target_lang)
        self.tts.load_voice(self.source_lang)
        logger.info("EchoBridge Pipeline initialized and models preloaded.")

    def set_languages(self, source: str, target: str):
        """Update active translation direction."""
        self.source_lang = source
        self.target_lang = target
        self.translation.load_pair(source, target)
        self.tts.load_voice(target)
        logger.info(f"Pipeline active language pair set to: {source} -> {target}")

    def swap_languages(self):
        """Swap source and target languages."""
        self.set_languages(self.target_lang, self.source_lang)

    def _on_audio_chunk(self, chunk_512: np.ndarray):
        """Callback invoked for every 512-sample audio chunk from microphone."""
        # Acoustic feedback prevention: Do not process audio while speakers are playing translated output
        if self.playback.is_playing:
            self.segmenter.reset()
            return

        utterance = self.segmenter.process_chunk(chunk_512)
        if utterance is not None:
            self.process_utterance(utterance)

    def process_utterance(self, audio_data: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Process a single completed speech utterance through the full translation pipeline:
        Audio -> STT -> MT -> TTS -> Playback
        """
        if audio_data is None or len(audio_data) < 1600: # Ignore very short transients (<100ms)
            return None

        t_start = time.perf_counter()
        logger.info(f"Processing utterance ({len(audio_data)/16000:.2f}s of audio)...")

        try:
            # 1. Speech Recognition
            orig_text, detected_lang, stt_ms = self.stt.transcribe(
                audio_data,
                language=self.source_lang
            )
            if not orig_text.strip():
                logger.info("Transcribed text was empty, skipping.")
                return None

            if self.on_transcription:
                self.on_transcription(orig_text, detected_lang, stt_ms)

            # 2. Machine Translation
            translated_text, mt_ms = self.translation.translate(
                orig_text,
                from_code=self.source_lang,
                to_code=self.target_lang
            )
            if not translated_text.strip():
                logger.info("Translated text was empty, skipping.")
                return None

            if self.on_translation:
                self.on_translation(translated_text, mt_ms)

            # 3. Text-to-Speech Synthesis
            audio_bytes, sample_rate, tts_ms = self.tts.synthesize(
                translated_text,
                lang=self.target_lang
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
                "source_language": self.source_lang,
                "target_language": self.target_lang,
                "audio_duration_s": round(len(audio_data) / 16000, 2),
                "stt_latency_ms": round(stt_ms, 2),
                "mt_latency_ms": round(mt_ms, 2),
                "tts_latency_ms": round(tts_ms, 2),
                "total_e2e_latency_ms": round(total_ms, 2)
            }

            logger.info(f"Pipeline Completed: '{orig_text}' -> '{translated_text}' [Total: {total_ms:.1f}ms (STT: {stt_ms:.1f}ms, MT: {mt_ms:.1f}ms, TTS: {tts_ms:.1f}ms)]")

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

    def stop_listening(self):
        """Stop microphone audio capture."""
        self.capture.stop()
        self.segmenter.reset()
