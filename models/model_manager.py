"""Model Manager: Downloads, verifies, and manages local offline AI models for EchoBridge."""
import os
import shutil
import urllib.request
import json
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, models_dir: str = "models_cache"):
        self.models_dir = os.path.abspath(models_dir)
        self.vad_dir = os.path.join(self.models_dir, "vad")
        self.stt_dir = os.path.join(self.models_dir, "stt")
        self.translation_dir = os.path.join(self.models_dir, "translation")
        self.tts_dir = os.path.join(self.models_dir, "tts")

        for d in [self.vad_dir, self.stt_dir, self.translation_dir, self.tts_dir]:
            os.makedirs(d, exist_ok=True)

    def check_disk_space(self, required_mb: float) -> bool:
        """Check if sufficient disk space is available."""
        _, _, free = shutil.disk_usage(self.models_dir)
        free_mb = free / (1024 * 1024)
        return free_mb >= required_mb

    def _download_file(self, url: str, dest_path: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
        """Helper to download a file with progress reporting."""
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
            logger.info(f"File already exists: {dest_path}")
            return dest_path

        temp_path = dest_path + ".tmp"
        headers = {'User-Agent': 'EchoBridge-Offline-Translator/1.0'}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 1024 * 64

            with open(temp_path, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        os.replace(temp_path, dest_path)
        logger.info(f"Successfully downloaded: {dest_path}")
        return dest_path

    # --- Silero VAD ---
    def get_vad_path(self) -> str:
        return os.path.join(self.vad_dir, "silero_vad.onnx")

    def is_vad_ready(self) -> bool:
        path = self.get_vad_path()
        return os.path.exists(path) and os.path.getsize(path) > 100_000

    def download_vad(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
        url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
        dest = self.get_vad_path()
        return self._download_file(url, dest, progress_callback)

    # --- Faster-Whisper ---
    def get_stt_model_path(self, model_size: str = "base") -> str:
        return os.path.join(self.stt_dir, f"faster-whisper-{model_size}")

    def is_stt_ready(self, model_size: str = "base") -> bool:
        model_path = self.get_stt_model_path(model_size)
        model_bin = os.path.join(model_path, "model.bin")
        return os.path.exists(model_bin) and os.path.getsize(model_bin) > 10_000_000

    def download_stt(self, model_size: str = "base", progress_callback: Optional[Callable[[str], None]] = None) -> str:
        """Pre-downloads faster-whisper model files into local cache directory."""
        from faster_whisper import download_model
        if progress_callback:
            progress_callback(f"Downloading Whisper {model_size} model...")
        local_dir = self.get_stt_model_path(model_size)
        download_model(model_size, output_dir=local_dir)
        return local_dir

    # --- Argos Translate ---
    def is_translation_pair_ready(self, from_code: str, to_code: str) -> bool:
        try:
            import argostranslate.package
            installed = argostranslate.package.get_installed_packages()
            for pkg in installed:
                if pkg.from_code == from_code and pkg.to_code == to_code:
                    return True
            return False
        except Exception:
            return False

    def download_translation_pair(self, from_code: str, to_code: str, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Download and install an Argos Translate package offline."""
        import argostranslate.package
        if progress_callback:
            progress_callback(f"Updating Argos package index for {from_code} -> {to_code}...")
        
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package_to_install = next(
            (p for p in available_packages if p.from_code == from_code and p.to_code == to_code),
            None
        )

        if package_to_install is None:
            raise ValueError(f"No offline translation package available for {from_code} -> {to_code}")

        if progress_callback:
            progress_callback(f"Installing offline translation model for {from_code} -> {to_code}...")

        download_path = package_to_install.download()
        argostranslate.package.install_from_path(download_path)
        logger.info(f"Installed Argos model {from_code} -> {to_code}")
        return True

    # --- Piper TTS ---
    def get_tts_model_path(self, voice_name: str) -> Dict[str, str]:
        return {
            "onnx": os.path.join(self.tts_dir, f"{voice_name}.onnx"),
            "json": os.path.join(self.tts_dir, f"{voice_name}.onnx.json")
        }

    def is_tts_ready(self, voice_name: str) -> bool:
        paths = self.get_tts_model_path(voice_name)
        return (os.path.exists(paths["onnx"]) and os.path.getsize(paths["onnx"]) > 1_000_000 and
                os.path.exists(paths["json"]) and os.path.getsize(paths["json"]) > 100)

    def download_tts_voice(self, voice_name: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, str]:
        """Download Piper TTS voice model and its JSON configuration."""
        paths = self.get_tts_model_path(voice_name)
        
        # Determine HuggingFace path based on voice naming
        # e.g. en_US-amy-low -> en/en_US/amy/low/en_US-amy-low.onnx
        # ja_JP-hi_fi_captain-medium -> ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx
        parts = voice_name.split("-")
        locale = parts[0]
        lang = locale.split("_")[0]
        speaker = parts[1]
        quality = parts[2] if len(parts) > 2 else "medium"

        base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{locale}/{speaker}/{quality}/{voice_name}"
        onnx_url = f"{base_url}.onnx"
        json_url = f"{base_url}.onnx.json"

        self._download_file(onnx_url, paths["onnx"], progress_callback)
        self._download_file(json_url, paths["json"])
        return paths

    def check_all_ready(self, from_code: str = "en", to_code: str = "ja", 
                        stt_size: str = "base",
                        tts_voices: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        """Check offline readiness for all pipeline components."""
        if tts_voices is None:
            tts_voices = {"en": "en_US-amy-low", "ja": "ja_JP-hi_fi_captain-medium"}

        status = {
            "vad": self.is_vad_ready(),
            "stt": self.is_stt_ready(stt_size),
            f"translation_{from_code}_{to_code}": self.is_translation_pair_ready(from_code, to_code),
            f"translation_{to_code}_{from_code}": self.is_translation_pair_ready(to_code, from_code),
            f"tts_{from_code}": self.is_tts_ready(tts_voices.get(from_code, "en_US-amy-low")),
            f"tts_{to_code}": self.is_tts_ready(tts_voices.get(to_code, "ja_JP-hi_fi_captain-medium")),
        }
        status["all_ready"] = all(status.values())
        return status
