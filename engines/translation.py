"""Translation Engine using CTranslate2 INT8 models and SentencePiece."""
import os
import time
import logging
from typing import Dict, Tuple, Optional
import ctranslate2
import sentencepiece as spm

logger = logging.getLogger(__name__)

class TranslatorEngine:
    """Offline translation engine powered by CTranslate2 and SentencePiece."""
    def __init__(self, models_base_dir: str = "models_cache/translation"):
        self.models_base_dir = os.path.abspath(models_base_dir)
        self._translators: Dict[str, ctranslate2.Translator] = {}
        self._tokenizers: Dict[str, spm.SentencePieceProcessor] = {}

    def _get_pair_key(self, from_code: str, to_code: str) -> str:
        return f"{from_code}_{to_code}"

    def load_pair(self, from_code: str, to_code: str):
        """Load translation model and tokenizer for a specific language pair."""
        pair_key = self._get_pair_key(from_code, to_code)
        if pair_key in self._translators:
            return

        pair_dir = os.path.join(self.models_base_dir, pair_key)
        model_path = os.path.join(pair_dir, "model")
        spm_path = os.path.join(pair_dir, "sentencepiece.model")

        if not os.path.exists(model_path) or not os.path.exists(spm_path):
            raise FileNotFoundError(f"Translation model files for {pair_key} not found in {pair_dir}")

        logger.info(f"Loading translation pair {pair_key} from {pair_dir}...")
        t0 = time.perf_counter()
        
        translator = ctranslate2.Translator(
            model_path,
            device="cpu",
            compute_type="int8",
            intra_threads=4
        )
        
        sp = spm.SentencePieceProcessor()
        sp.load(spm_path)

        self._translators[pair_key] = translator
        self._tokenizers[pair_key] = sp
        logger.info(f"Loaded {pair_key} translation model in {(time.perf_counter() - t0)*1000:.2f} ms")

    def translate(self, text: str, from_code: str, to_code: str) -> Tuple[str, float]:
        """
        Translate input text from source language to target language.
        Returns: (translated_text, latency_ms)
        """
        if not text or not text.strip():
            return "", 0.0

        pair_key = self._get_pair_key(from_code, to_code)
        if pair_key not in self._translators:
            self.load_pair(from_code, to_code)

        translator = self._translators[pair_key]
        sp = self._tokenizers[pair_key]

        t0 = time.perf_counter()
        tokens = sp.encode_as_pieces(text.strip())
        results = translator.translate_batch([tokens])
        out_tokens = results[0].hypotheses[0]
        translated = sp.decode_pieces(out_tokens).strip()
        latency_ms = (time.perf_counter() - t0) * 1000

        logger.debug(f"Translated [{pair_key}] in {latency_ms:.2f}ms: '{text}' -> '{translated}'")
        return translated, latency_ms

    def is_pair_loaded(self, from_code: str, to_code: str) -> bool:
        return self._get_pair_key(from_code, to_code) in self._translators
