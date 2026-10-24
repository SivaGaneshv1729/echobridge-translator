"""Test direct CTranslate2 translation on Argos model package with UTF-8 stdout."""
import os
import sys
import ctranslate2
import sentencepiece as spm
import time

sys.stdout.reconfigure(encoding='utf-8')

def run_test():
    model_dir = "models_cache/translation/en_ja"
    ct2_model_path = os.path.join(model_dir, "model")
    spm_path = os.path.join(model_dir, "sentencepiece.model")

    print(f"Loading CTranslate2 model from {ct2_model_path}...")
    t0 = time.perf_counter()
    translator = ctranslate2.Translator(ct2_model_path, device="cpu", compute_type="int8", intra_threads=4)
    load_time_ms = (time.perf_counter() - t0) * 1000
    print(f"Model loaded in {load_time_ms:.2f} ms")

    sp = spm.SentencePieceProcessor()
    sp.load(spm_path)

    test_sentences = [
        "Hello, how are you today?",
        "Where is the train station?",
        "Thank you very much for your help."
    ]

    print("\n--- Translation Benchmark (EN -> JA) ---")
    for s in test_sentences:
        t1 = time.perf_counter()
        tokens = sp.encode_as_pieces(s)
        results = translator.translate_batch([tokens])
        out_tokens = results[0].hypotheses[0]
        translation = sp.decode_pieces(out_tokens)
        elapsed_ms = (time.perf_counter() - t1) * 1000
        print(f"EN: {s}")
        print(f"JA: {translation}")
        print(f"Latency: {elapsed_ms:.2f} ms\n")

if __name__ == "__main__":
    run_test()
