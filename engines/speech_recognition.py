"""Speech Recognition Engine using Faster-Whisper (CTranslate2 INT8)."""
import time
import logging
from typing import Optional, Tuple
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
        
        logger.info(f"Loading WhisperModel({model_size}, compute_type={compute_type}, threads={cpu_threads})...")
        t0 = time.perf_counter()
        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                local_files_only=True
            )
        except Exception as e:
            logger.info(f"Local files only load failed ({e}), attempting initial download...")
            self.model = WhisperModel(
                model_size,
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
        beam_size: int = 1,
        temperature: float = 0.0
    ) -> Tuple[str, str, float]:
        """
        Transcribe audio numpy array (16kHz mono float32).
        Returns: (transcribed_text, detected_language, latency_ms)
        """
        if audio_data is None or len(audio_data) == 0:
            return "", language or "unknown", 0.0

        t0 = time.perf_counter()
        
        segments, info = self.model.transcribe(
            audio_data,
            language=language,
            beam_size=beam_size,
            temperature=temperature,
            condition_on_previous_text=False,
            vad_filter=False # VAD is already handled upstream
        )
        
        text_segments = [s.text.strip() for s in segments if s.text.strip()]
        full_text = " ".join(text_segments).strip()
        detected_lang = info.language if info else (language or "unknown")
        latency_ms = (time.perf_counter() - t0) * 1000

        logger.debug(f"Transcribed ({detected_lang}) in {latency_ms:.2f}ms: '{full_text}'")
        return full_text, detected_lang, latency_ms
