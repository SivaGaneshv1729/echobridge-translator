"""Audio playback module using sounddevice."""
import logging
import threading
import time
from typing import Optional, List, Dict, Any
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

class AudioPlayback:
    """Manages audio playback with volume scaling, device routing, and anti-feedback tracking."""
    def __init__(self, device_index: Optional[int] = None, volume: float = 1.0):
        self.device_index = device_index
        self.volume = max(0.0, min(1.0, volume))
        self.muted = False
        self._is_playing = False
        self._lock = threading.Lock()

    @staticmethod
    def list_output_devices() -> List[Dict[str, Any]]:
        """List available audio output devices."""
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                devices.append({
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_output_channels"],
                    "default_samplerate": dev["default_samplerate"]
                })
        return devices

    @property
    def is_playing(self) -> bool:
        """Returns True if audio is actively being played through the speakers."""
        return self._is_playing

    def play(self, audio_data: np.ndarray, sample_rate: int = 16000, blocking: bool = False):
        """Play numpy audio array (float32 or int16)."""
        if self.muted or self.volume == 0.0:
            logger.info("Playback skipped (muted or volume 0).")
            return

        # Ensure float32 normalized in [-1.0, 1.0]
        if audio_data.dtype == np.int16:
            audio = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype != np.float32:
            audio = audio_data.astype(np.float32)
        else:
            audio = audio_data.copy()

        # Apply volume
        if self.volume != 1.0:
            audio *= self.volume

        def _play_thread():
            with self._lock:
                self._is_playing = True
            try:
                sd.play(audio, samplerate=sample_rate, device=self.device_index)
                sd.wait()
            except Exception as e:
                logger.error(f"Playback error: {e}")
            finally:
                # Add tiny post-playback buffer to prevent microphone picking up acoustic reverberations
                time.sleep(0.15)
                with self._lock:
                    self._is_playing = False

        if blocking:
            _play_thread()
        else:
            threading.Thread(target=_play_thread, daemon=True).start()

    def play_raw_bytes(self, raw_bytes, sample_rate: int = 22050, blocking: bool = False):
        """Play 16-bit PCM raw audio bytes or numpy array (typical Piper TTS output)."""
        if isinstance(raw_bytes, np.ndarray):
            if raw_bytes.dtype == np.float32 or raw_bytes.dtype == np.int16:
                self.play(raw_bytes, sample_rate=sample_rate, blocking=blocking)
                return
            raw_bytes = raw_bytes.tobytes()

        if isinstance(raw_bytes, (bytes, bytearray)):
            if len(raw_bytes) % 2 != 0:
                raw_bytes = raw_bytes[:len(raw_bytes) - (len(raw_bytes) % 2)]
            audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
            self.play(audio_int16, sample_rate=sample_rate, blocking=blocking)
        else:
            logger.error(f"Unsupported audio type for play_raw_bytes: {type(raw_bytes)}")

    def stop(self):
        """Immediately stop playback."""
        try:
            sd.stop()
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
        finally:
            with self._lock:
                self._is_playing = False
