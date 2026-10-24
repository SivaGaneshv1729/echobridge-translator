"""Test reverse CTranslate2 translation (JA -> EN) on Argos model package."""
import os
import sys
import zipfile
import urllib.request
import ctranslate2
import sentencepiece as spm
import time

sys.stdout.reconfigure(encoding='utf-8')

def download_and_test_ja_en():
    model_dir = "models_cache/translation/ja_en"
    zip_path = "models_cache/translation/translate-ja_en-1_1.argosmodel"
    os.makedirs("models_cache/translation", exist_ok=True)

    if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 50_000_000:
        url = "https://argos-net.com/v1/translate-ja_en-1_1.argosmodel"
        print(f"Downloading {url}...")
        temp_path = zip_path + ".tmp"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(temp_path, zip_path)
        print("Download complete.")

    if not os.path.exists(model_dir):
        print("Extracting ja_en package...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall("models_cache/translation")
        print("Extracted.")

    ct2_model_path = os.path.join(model_dir, "model")
    spm_path = os.path.join(model_dir, "sentencepiece.model")

    print(f"Loading CTranslate2 model from {ct2_model_path}...")
    t0 = time.perf_counter()
    translator = ctranslate2.Translator(ct2_model_path, device="cpu", compute_type="int8", intra_threads=4)
    print(f"Loaded in {(time.perf_counter() - t0)*1000:.2f} ms")

    sp = spm.SentencePieceProcessor()
    sp.load(spm_path)

    test_sentences = [
        "こんにちは、お元気ですか？",
        "駅はどこにありますか？",
        "ありがとうございます。"
    ]

    print("\n--- Translation Benchmark (JA -> EN) ---")
    for s in test_sentences:
        t1 = time.perf_counter()
        tokens = sp.encode_as_pieces(s)
        results = translator.translate_batch([tokens])
        out_tokens = results[0].hypotheses[0]
        translation = sp.decode_pieces(out_tokens)
        elapsed_ms = (time.perf_counter() - t1) * 1000
        print(f"JA: {s}")
        print(f"EN: {translation}")
        print(f"Latency: {elapsed_ms:.2f} ms\n")

if __name__ == "__main__":
    download_and_test_ja_en()
