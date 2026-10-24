"""Hardware and Model Compatibility Module for EchoBridge."""
import platform
import sys
import shutil
import os
import json
import ctypes
from typing import Dict, Any, List

# Catalog of verified compatible offline models and their licenses
MODEL_CATALOG = {
    "vad": {
        "silero_vad": {
            "name": "Silero VAD (ONNX)",
            "license": "MIT",
            "url": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
            "size_mb": 1.8,
            "latency_target_ms": 15,
            "ram_mb": 25,
            "description": "Ultra-fast voice activity detector with negligible CPU impact"
        }
    },
    "stt": {
        "faster-whisper-tiny": {
            "name": "Faster-Whisper Tiny (INT8)",
            "license": "MIT",
            "repo_id": "Systran/faster-whisper-tiny",
            "size_mb": 75,
            "latency_target_ms": 250,
            "ram_mb": 150,
            "languages": ["en", "ja", "es", "fr", "de", "it", "zh", "ko"],
            "description": "Ultra-lightweight STT, ideal for extreme speed"
        },
        "faster-whisper-base": {
            "name": "Faster-Whisper Base (INT8)",
            "license": "MIT",
            "repo_id": "Systran/faster-whisper-base",
            "size_mb": 145,
            "latency_target_ms": 400,
            "ram_mb": 250,
            "languages": ["en", "ja", "es", "fr", "de", "it", "zh", "ko"],
            "description": "Best balance of Japanese accuracy and low latency on 4-core CPU"
        }
    },
    "translation": {
        "argos_en_ja": {
            "name": "Argos Translate English -> Japanese",
            "license": "MIT / Creative Commons",
            "from_code": "en",
            "to_code": "ja",
            "url": "https://argos-net.com/v1/translate-en_ja-1_1.argosmodel",
            "size_mb": 85,
            "latency_target_ms": 150,
            "ram_mb": 180,
            "description": "Offline CTranslate2-based translation"
        },
        "argos_ja_en": {
            "name": "Argos Translate Japanese -> English",
            "license": "MIT / Creative Commons",
            "from_code": "ja",
            "to_code": "en",
            "url": "https://argos-net.com/v1/translate-ja_en-1_1.argosmodel",
            "size_mb": 88,
            "latency_target_ms": 150,
            "ram_mb": 180,
            "description": "Offline CTranslate2-based translation"
        }
    },
    "tts": {
        "piper_en_amy_low": {
            "name": "Piper TTS en_US-amy-low",
            "license": "MIT / Public Domain",
            "language": "en",
            "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx",
            "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx.json",
            "size_mb": 28,
            "latency_target_ms": 120,
            "ram_mb": 80,
            "description": "Lightweight, high-speed natural English voice synthesis"
        },
        "piper_ja_captain_medium": {
            "name": "Piper TTS ja_JP-hi_fi_captain-medium",
            "license": "MIT / Public Domain",
            "language": "ja",
            "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx",
            "config_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx.json",
            "size_mb": 65,
            "latency_target_ms": 200,
            "ram_mb": 120,
            "description": "High-quality offline Japanese voice synthesis"
        }
    }
}

def detect_hardware() -> Dict[str, Any]:
    """Detect local hardware capabilities."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

    cwd = os.getcwd()
    total_disk, _, free_disk = shutil.disk_usage(cwd)

    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu_cores": os.cpu_count() or 4,
        "total_ram_gb": round(stat.ullTotalPhys / (1024 ** 3), 2),
        "available_ram_gb": round(stat.ullAvailPhys / (1024 ** 3), 2),
        "free_disk_gb": round(free_disk / (1024 ** 3), 2),
        "gpu_acceleration": "CPU only (AVX2 INT8 quantized execution recommended)"
    }

def generate_compatibility_report(pair_from: str = "en", pair_to: str = "ja") -> Dict[str, Any]:
    """Generate a compatibility report for the specified language pair."""
    hw = detect_hardware()
    estimated_total_ram_mb = 25 + 250 + 180 + 120  # ~575 MB peak
    estimated_total_disk_mb = 1.8 + 145 + 85 + 88 + 28 + 65  # ~413 MB

    compatible = (hw["available_ram_gb"] * 1024 > estimated_total_ram_mb) and (hw["free_disk_gb"] * 1024 > estimated_total_disk_mb)

    return {
        "hardware": hw,
        "language_pair": f"{pair_from} <-> {pair_to}",
        "estimated_peak_ram_mb": estimated_total_ram_mb,
        "estimated_disk_usage_mb": estimated_total_disk_mb,
        "is_compatible": compatible,
        "model_selection": {
            "vad": "silero_vad",
            "stt": "faster-whisper-base (INT8)",
            "translation_forward": f"argos_{pair_from}_{pair_to}",
            "translation_reverse": f"argos_{pair_to}_{pair_from}",
            "tts_forward": f"piper_{pair_to}_captain_medium" if pair_to == "ja" else "piper_en_amy_low",
            "tts_reverse": f"piper_{pair_from}_amy_low" if pair_from == "en" else "piper_ja_captain_medium"
        },
        "target_latency_estimate_ms": {
            "vad": 15,
            "stt": 400,
            "translation": 150,
            "tts": 200,
            "audio_io": 50,
            "total_estimated_ms": 815
        }
    }
