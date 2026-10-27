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
        Translate input text from source language to target language using beam search and clean post-processing.
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
        clean_text = text.strip()
        tokens = sp.encode_as_pieces(clean_text)
        
        try:
            results = translator.translate_batch(
                [tokens],
                beam_size=4,
                patience=1.2,
                length_penalty=1.0,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                replace_unknowns=True
            )
        except TypeError:
            # Fallback for environments with minimal parameter signatures
            results = translator.translate_batch([tokens], beam_size=2)

        out_tokens = results[0].hypotheses[0]
        translated = sp.decode_pieces(out_tokens).strip()

        # Clean punctuation and casing post-processing
        if to_code == "en":
            if translated and translated[0].islower():
                translated = translated[0].upper() + translated[1:]
            if clean_text.endswith("?") and not translated.endswith("?"):
                translated = translated.rstrip(".") + "?"
            elif not translated.endswith((".", "!", "?")):
                translated += "."
        elif to_code == "ja":
            # Replace half-width question mark with full-width if appropriate
            if translated.endswith("?"):
                translated = translated[:-1] + "？"
            elif not translated.endswith(("。", "！", "？")):
                translated += "。"

        latency_ms = (time.perf_counter() - t0) * 1000

        logger.debug(f"Translated [{pair_key}] in {latency_ms:.2f}ms: '{text}' -> '{translated}'")
        return translated, latency_ms

    def is_pair_loaded(self, from_code: str, to_code: str) -> bool:
        return self._get_pair_key(from_code, to_code) in self._translators
