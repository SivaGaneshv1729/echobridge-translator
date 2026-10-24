"""Audio capture module using sounddevice."""
import logging
import queue
import threading
from typing import Optional, Callable, List, Dict, Any
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

class AudioCapture:
    """Manages audio recording from microphone into 512-sample float32 chunks."""
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,
        device_index: Optional[int] = None,
        chunk_callback: Optional[Callable[[np.ndarray], None]] = None
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index
        self.chunk_callback = chunk_callback
        
        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._lock = threading.Lock()
        self.queue: queue.Queue = queue.Queue(maxsize=100)

    @staticmethod
    def list_input_devices() -> List[Dict[str, Any]]:
        """List available audio input devices."""
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_samplerate": dev["default_samplerate"]
                })
        return devices

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Internal sounddevice stream callback."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        
        # indata is (frames, channels), extract mono channel
        chunk = indata[:, 0].copy()
        
        if self.chunk_callback:
            try:
                self.chunk_callback(chunk)
            except Exception as e:
                logger.error(f"Error in chunk callback: {e}")

        try:
            self.queue.put_nowait(chunk)
        except queue.Full:
            pass

    def start(self):
        """Start microphone audio stream."""
        with self._lock:
            if self._is_recording:
                return

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.device_index,
                channels=1,
                dtype="float32",
                callback=self._audio_callback
            )
            self._stream.start()
            self._is_recording = True
            logger.info(f"Microphone recording started (device: {self.device_index or 'Default'}, SR: {self.sample_rate})")

    def stop(self):
        """Stop audio stream."""
        with self._lock:
            if not self._is_recording:
                return

            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._is_recording = False
            logger.info("Microphone recording stopped.")

    @property
    def is_recording(self) -> bool:
        return self._is_recording
