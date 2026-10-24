"""Text-to-Speech Engine using Piper ONNX and PyKakasi G2P."""
import os
import time
import logging
from typing import Dict, Tuple, Optional
import numpy as np
from piper.voice import PiperVoice
from piper.phonemize_japanese import OPENJTALK_TO_IPA
import pykakasi

logger = logging.getLogger(__name__)

class TTSEngine:
    """Offline Text-to-Speech engine supporting English and Japanese using Piper ONNX models."""
    def __init__(self, models_base_dir: str = "models_cache/tts"):
        self.models_base_dir = os.path.abspath(models_base_dir)
        self._voices: Dict[str, PiperVoice] = {}
        self._kakasi = pykakasi.kakasi()

        # Romaji to OpenJTalk phones lookup for Japanese phonemization
        self._romaji_to_phones = {
            "a": ["a"], "i": ["i"], "u": ["u"], "e": ["e"], "o": ["o"],
            "ka": ["k", "a"], "ki": ["ky", "i"], "ku": ["k", "u"], "ke": ["k", "e"], "ko": ["k", "o"],
            "sa": ["s", "a"], "shi": ["sh", "i"], "su": ["s", "u"], "se": ["s", "e"], "so": ["s", "o"],
            "ta": ["t", "a"], "chi": ["ch", "i"], "tsu": ["ts", "u"], "te": ["t", "e"], "to": ["t", "o"],
            "na": ["n", "a"], "ni": ["ny", "i"], "nu": ["n", "u"], "ne": ["n", "e"], "no": ["n", "o"],
            "ha": ["h", "a"], "hi": ["hy", "i"], "fu": ["f", "u"], "he": ["h", "e"], "ho": ["h", "o"],
            "ma": ["m", "a"], "mi": ["my", "i"], "mu": ["m", "u"], "me": ["m", "e"], "mo": ["m", "o"],
            "ya": ["y", "a"], "yu": ["y", "u"], "yo": ["y", "o"],
            "ra": ["r", "a"], "ri": ["ry", "i"], "ru": ["r", "u"], "re": ["r", "e"], "ro": ["r", "o"],
            "wa": ["w", "a"], "wo": ["o"], "n": ["N"],
            "ga": ["g", "a"], "gi": ["gy", "i"], "gu": ["g", "u"], "ge": ["g", "e"], "go": ["g", "o"],
            "za": ["z", "a"], "ji": ["j", "i"], "zu": ["z", "u"], "ze": ["z", "e"], "zo": ["z", "o"],
            "da": ["d", "a"], "de": ["d", "e"], "do": ["d", "o"],
            "ba": ["b", "a"], "bi": ["by", "i"], "bu": ["b", "u"], "be": ["b", "e"], "bo": ["b", "o"],
            "pa": ["p", "a"], "pi": ["py", "i"], "pu": ["p", "u"], "pe": ["p", "e"], "po": ["p", "o"],
            "kya": ["ky", "a"], "kyu": ["ky", "u"], "kyo": ["ky", "o"],
            "sha": ["sh", "a"], "shu": ["sh", "u"], "sho": ["sh", "o"],
            "cha": ["ch", "a"], "chu": ["ch", "u"], "cho": ["ch", "o"],
            "nya": ["ny", "a"], "nyu": ["ny", "u"], "nyo": ["ny", "o"],
            "hya": ["hy", "a"], "hyu": ["hy", "u"], "hyo": ["hy", "o"],
            "mya": ["my", "a"], "myu": ["my", "u"], "myo": ["my", "o"],
            "rya": ["ry", "a"], "ryu": ["ry", "u"], "ryo": ["ry", "o"],
            "gya": ["gy", "a"], "gyu": ["gy", "u"], "gyo": ["gy", "o"],
            "ja": ["j", "a"], "ju": ["j", "u"], "jo": ["j", "o"],
            "bya": ["by", "a"], "byu": ["by", "u"], "byo": ["by", "o"],
            "pya": ["py", "a"], "pyu": ["py", "u"], "pyo": ["py", "o"],
            "desu": ["d", "e", "s", "U"], "masu": ["m", "a", "s", "U"]
        }

    def load_voice(self, lang: str, voice_name: Optional[str] = None):
        """Preload Piper voice for a language."""
        if lang in self._voices:
            return

        if voice_name is None:
            voice_name = "ja_JP-hi_fi_captain-medium" if lang == "ja" else "en_US-amy-low"

        onnx_path = os.path.join(self.models_base_dir, f"{voice_name}.onnx")
        json_path = os.path.join(self.models_base_dir, f"{voice_name}.onnx.json")

        if not os.path.exists(onnx_path) or not os.path.exists(json_path):
            raise FileNotFoundError(f"Voice model files for {voice_name} not found in {self.models_base_dir}")

        logger.info(f"Loading Piper voice {voice_name} for language '{lang}'...")
        t0 = time.perf_counter()
        voice = PiperVoice.load(onnx_path, config_path=json_path)
        self._voices[lang] = voice
        logger.info(f"Loaded Piper voice {voice_name} in {(time.perf_counter() - t0)*1000:.2f} ms")

    def _ja_to_ipa(self, text: str) -> list[str]:
        """Convert Japanese text (kanji/kana) to Piper-compatible IPA phonemes."""
        # Normalize spoken particles and greetings
        normalized = text.replace("こんにちは", "こんにちわ").replace("こんばんは", "こんばんわ")
        
        res = self._kakasi.convert(normalized)
        phones = []
        for item in res:
            rom = item['hepburn'].lower()
            idx = 0
            while idx < len(rom):
                matched = False
                for length in [4, 3, 2, 1]:
                    sub = rom[idx:idx+length]
                    if sub in self._romaji_to_phones:
                        for p in self._romaji_to_phones[sub]:
                            phones.extend(list(OPENJTALK_TO_IPA.get(p.lower(), p)))
                        idx += length
                        matched = True
                        break
                if not matched:
                    if rom[idx] in "?!.,":
                        phones.append(rom[idx])
                    elif rom[idx] == " ":
                        phones.append("#")
                    idx += 1
        phones.append(".")
        return phones

    def synthesize(self, text: str, lang: str = "en") -> Tuple[bytes, int, float]:
        """
        Synthesize text to 16-bit PCM audio bytes.
        Returns: (pcm_bytes, sample_rate, latency_ms)
        """
        if not text or not text.strip():
            return b"", 16000, 0.0

        if lang not in self._voices:
            self.load_voice(lang)

        voice = self._voices[lang]
        sample_rate = voice.config.sample_rate

        t0 = time.perf_counter()
        if lang == "ja":
            ipa = self._ja_to_ipa(text.strip())
            phoneme_ids = voice.phonemes_to_ids(ipa)
            audio_array = voice.phoneme_ids_to_audio(phoneme_ids)
            # Piper returns float32 in [-1.0, 1.0]. Convert to 16-bit signed PCM bytes cleanly:
            if isinstance(audio_array, np.ndarray):
                audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767.0).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
            else:
                audio_bytes = bytes(audio_array)
        else:
            chunks = list(voice.synthesize(text.strip()))
            audio_bytes = b"".join([c.audio_int16_bytes for c in chunks])

        latency_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"Synthesized '{text}' ({lang}) in {latency_ms:.2f}ms ({len(audio_bytes)} bytes)")
        return audio_bytes, sample_rate, latency_ms
