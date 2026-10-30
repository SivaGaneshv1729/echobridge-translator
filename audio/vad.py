"""Voice Activity Detection (VAD) module using Silero VAD ONNX."""
import os
import numpy as np
import onnxruntime as ort
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

class SileroVAD:
    """Ultra-fast, local CPU voice activity detector."""
    def __init__(self, model_path: str = "models_cache/vad/silero_vad.onnx", threshold: float = 0.35):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"VAD model not found at: {model_path}. Please download it first.")
        
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.threshold = threshold
        self.sample_rate = 16000
        self.reset_states()

    def reset_states(self):
        """Reset internal recurrent states and context window."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)

    def is_speech(self, audio_chunk_512: np.ndarray) -> float:
        """
        Process a single 512-sample (32ms at 16kHz) float32 chunk.
        Returns speech probability between 0.0 and 1.0.
        """
        if len(audio_chunk_512.shape) == 1:
            chunk = np.expand_dims(audio_chunk_512, 0)
        else:
            chunk = audio_chunk_512

        if chunk.shape[1] != 512:
            raise ValueError(f"Chunk size must be 512 samples. Got: {chunk.shape[1]}")

        # Silero VAD v5 requires 64 context samples from previous chunk prepended (total 576 samples)
        model_input = np.concatenate([self._context, chunk.astype(np.float32)], axis=1)

        ort_inputs = {
            "input": model_input,
            "sr": np.array(self.sample_rate, dtype=np.int64),
            "state": self._state
        }

        prob, self._state = self.session.run(None, ort_inputs)
        self._context = chunk[:, -64:].astype(np.float32)
        return float(prob[0][0])


class UtteranceSegmenter:
    """Accumulates audio chunks and segments them into discrete utterances based on VAD."""
    def __init__(
        self,
        vad: SileroVAD,
        sample_rate: int = 16000,
        min_speech_duration_ms: int = 150,
        min_silence_duration_ms: int = 650,
        speech_pad_ms: int = 300
    ):
        self.vad = vad
        self.sample_rate = sample_rate
        self.min_speech_chunks = max(2, int((min_speech_duration_ms / 1000) * sample_rate / 512))
        self.min_silence_chunks = int((min_silence_duration_ms / 1000) * sample_rate / 512)
        self.pad_chunks = int((speech_pad_ms / 1000) * sample_rate / 512)
        # Keep ~120ms of post-speech cushion to avoid clipping final consonant while preventing dead air
        self.trailing_pad_chunks = max(2, int((120 / 1000) * sample_rate / 512))

        self.buffer: List[np.ndarray] = []
        self.pre_buffer: List[np.ndarray] = []
        self.candidate_buffer: List[np.ndarray] = []
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_chunks_count = 0
        self.on_speech_started: Optional[Callable[[], None]] = None

    def process_chunk(self, chunk_512: np.ndarray) -> Optional[np.ndarray]:
        """
        Feed a 512-sample float32 chunk.
        Returns complete utterance float32 array when end of speech is detected, else None.
        """
        prob = self.vad.is_speech(chunk_512)
        is_speech_chunk = prob >= self.vad.threshold

        if not self.is_speaking:
            if is_speech_chunk:
                self.candidate_buffer.append(chunk_512)
                self.speech_chunks_count += 1
                if self.speech_chunks_count >= self.min_speech_chunks:
                    self.is_speaking = True
                    # Full lead-in: pre-speech ambient cushion + confirmed speech candidates
                    self.buffer = list(self.pre_buffer) + list(self.candidate_buffer)
                    self.pre_buffer.clear()
                    self.candidate_buffer.clear()
                    self.silence_counter = 0
                    if self.on_speech_started:
                        try:
                            self.on_speech_started()
                        except Exception as e:
                            logger.error(f"Error in on_speech_started: {e}")
            else:
                # Discard transient false-alarm clicks (less than min_speech_chunks)
                if self.candidate_buffer:
                    self.pre_buffer.extend(self.candidate_buffer)
                    self.candidate_buffer.clear()
                self.speech_chunks_count = 0
                self.pre_buffer.append(chunk_512)
                while len(self.pre_buffer) > self.pad_chunks:
                    self.pre_buffer.pop(0)

            return None
        else:
            self.buffer.append(chunk_512)
            if not is_speech_chunk:
                self.silence_counter += 1
                if self.silence_counter >= self.min_silence_chunks:
                    # End of utterance detected — trim excessive trailing dead air
                    cutoff = max(
                        self.min_speech_chunks,
                        len(self.buffer) - self.silence_counter + self.trailing_pad_chunks
                    )
                    trimmed_chunks = self.buffer[:cutoff] if cutoff < len(self.buffer) else self.buffer
                    utterance = np.concatenate(trimmed_chunks) if trimmed_chunks else None
                    self.reset()
                    return utterance
            else:
                self.silence_counter = 0
            return None

    def flush(self) -> Optional[np.ndarray]:
        """Flush currently buffered speech into a complete utterance (used on PTT release or Stop)."""
        utterance = None
        if len(self.buffer) > 0 and len(self.buffer) >= self.min_speech_chunks:
            # Trim trailing silence if any
            cutoff = max(
                self.min_speech_chunks,
                len(self.buffer) - self.silence_counter + self.trailing_pad_chunks
            )
            trimmed_chunks = self.buffer[:cutoff] if cutoff < len(self.buffer) else self.buffer
            utterance = np.concatenate(trimmed_chunks) if trimmed_chunks else None
        elif len(self.candidate_buffer) >= self.min_speech_chunks:
            all_chunks = list(self.pre_buffer) + list(self.candidate_buffer)
            utterance = np.concatenate(all_chunks) if all_chunks else None
        elif len(self.pre_buffer) > 0 and self.speech_chunks_count >= self.min_speech_chunks:
            utterance = np.concatenate(self.pre_buffer)

        self.reset()
        return utterance

    def reset(self):
        """Reset segmenter state."""
        self.buffer.clear()
        self.pre_buffer.clear()
        self.candidate_buffer.clear()
        self.is_speaking = False
        self.silence_counter = 0
        self.speech_chunks_count = 0
        self.vad.reset_states()
