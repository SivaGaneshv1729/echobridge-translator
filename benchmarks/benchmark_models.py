"""Phase 1 Model Benchmark: Independently benchmark VAD, STT, MT, and TTS models on local hardware."""
import os
import sys
import time
import json
import logging
import numpy as np
import psutil

# Ensure stdout handles UTF-8 cleanly on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.model_manager import ModelManager
from models.compatibility import detect_hardware
import pykakasi
from piper.phonemize_japanese import OPENJTALK_TO_IPA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def get_current_process_ram_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def benchmark_vad(manager: ModelManager) -> dict:
    logger.info("=== Benchmarking Silero VAD ===")
    import onnxruntime as ort
    
    if not manager.is_vad_ready():
        manager.download_vad()

    vad_path = manager.get_vad_path()
    start_ram = get_current_process_ram_mb()

    t0 = time.perf_counter()
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(vad_path, opts, providers=["CPUExecutionProvider"])
    load_time_ms = (time.perf_counter() - t0) * 1000

    dummy_chunk = np.zeros((1, 512), dtype=np.float32)
    sr_tensor = np.array(16000, dtype=np.int64)
    state = np.zeros((2, 1, 128), dtype=np.float32)

    latencies = []
    for _ in range(50):
        t1 = time.perf_counter()
        ort_inputs = {"input": dummy_chunk, "sr": sr_tensor, "state": state}
        _, state = session.run(None, ort_inputs)
        latencies.append((time.perf_counter() - t1) * 1000)

    end_ram = get_current_process_ram_mb()
    res = {
        "model": "Silero VAD ONNX",
        "license": "MIT",
        "load_time_ms": round(load_time_ms, 2),
        "chunk_latency_median_ms": round(float(np.median(latencies)), 2),
        "chunk_latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "ram_usage_mb": round(end_ram - start_ram, 2)
    }
    logger.info(f"VAD Results: {res}")
    return res

def benchmark_stt(manager: ModelManager, model_size: str = "base") -> dict:
    logger.info(f"=== Benchmarking Faster-Whisper ({model_size}) ===")
    from faster_whisper import WhisperModel
    
    start_ram = get_current_process_ram_mb()
    t0 = time.perf_counter()
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=4)
    load_time_ms = (time.perf_counter() - t0) * 1000

    sample_rate = 16000
    duration_s = 2.0
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    audio_data = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    latencies = []
    for _ in range(3):
        t1 = time.perf_counter()
        segments, _ = model.transcribe(audio_data, language="en", beam_size=1)
        _ = list(segments)
        latencies.append((time.perf_counter() - t1) * 1000)

    end_ram = get_current_process_ram_mb()
    res = {
        "model": f"Faster-Whisper-{model_size}-int8",
        "license": "MIT",
        "load_time_ms": round(load_time_ms, 2),
        "transcribe_2s_latency_median_ms": round(float(np.median(latencies)), 2),
        "ram_usage_mb": round(end_ram - start_ram, 2)
    }
    logger.info(f"STT Results: {res}")
    return res

def benchmark_translation() -> dict:
    logger.info("=== Benchmarking CTranslate2 Argos Models (en <-> ja) ===")
    import ctranslate2
    import sentencepiece as spm

    start_ram = get_current_process_ram_mb()

    # EN -> JA
    en_ja_model_dir = "models_cache/translation/en_ja"
    en_ja_translator = ctranslate2.Translator(os.path.join(en_ja_model_dir, "model"), device="cpu", compute_type="int8", intra_threads=4)
    en_sp = spm.SentencePieceProcessor()
    en_sp.load(os.path.join(en_ja_model_dir, "sentencepiece.model"))

    en_samples = [
        "Hello, how are you today?",
        "Where is the nearest train station?",
        "Thank you very much for your assistance."
    ]
    en_ja_latencies = []
    en_ja_outputs = []
    for s in en_samples:
        t0 = time.perf_counter()
        tokens = en_sp.encode_as_pieces(s)
        results = en_ja_translator.translate_batch([tokens])
        out_text = en_sp.decode_pieces(results[0].hypotheses[0])
        en_ja_latencies.append((time.perf_counter() - t0) * 1000)
        en_ja_outputs.append(out_text)

    # JA -> EN
    ja_en_model_dir = "models_cache/translation/ja_en"
    ja_en_translator = ctranslate2.Translator(os.path.join(ja_en_model_dir, "model"), device="cpu", compute_type="int8", intra_threads=4)
    ja_sp = spm.SentencePieceProcessor()
    ja_sp.load(os.path.join(ja_en_model_dir, "sentencepiece.model"))

    ja_samples = [
        "こんにちは、お元気ですか？",
        "最寄りの駅はどこですか？",
        "お手伝いいただきありがとうございます。"
    ]
    ja_en_latencies = []
    ja_en_outputs = []
    for s in ja_samples:
        t0 = time.perf_counter()
        tokens = ja_sp.encode_as_pieces(s)
        results = ja_en_translator.translate_batch([tokens])
        out_text = ja_sp.decode_pieces(results[0].hypotheses[0])
        ja_en_latencies.append((time.perf_counter() - t0) * 1000)
        ja_en_outputs.append(out_text)

    end_ram = get_current_process_ram_mb()
    res = {
        "model": "CTranslate2 INT8 (Argos en <-> ja)",
        "license": "MIT / CC",
        "en_to_ja_latency_median_ms": round(float(np.median(en_ja_latencies)), 2),
        "ja_to_en_latency_median_ms": round(float(np.median(ja_en_latencies)), 2),
        "en_to_ja_pairs": list(zip(en_samples, en_ja_outputs)),
        "ja_to_en_pairs": list(zip(ja_samples, ja_en_outputs)),
        "ram_usage_mb": round(end_ram - start_ram, 2)
    }
    logger.info(f"Translation Results: {res}")
    return res

def benchmark_tts() -> dict:
    logger.info("=== Benchmarking Piper TTS (en & ja) ===")
    from piper.voice import PiperVoice

    start_ram = get_current_process_ram_mb()

    # English TTS
    en_voice = PiperVoice.load("models_cache/tts/en_US-amy-low.onnx")
    en_latencies = []
    for _ in range(3):
        t0 = time.perf_counter()
        chunks = list(en_voice.synthesize("Hello, nice to meet you."))
        en_latencies.append((time.perf_counter() - t0) * 1000)

    # Japanese TTS
    ja_voice = PiperVoice.load("models_cache/tts/ja_JP-hi_fi_captain-medium.onnx")
    kks = pykakasi.kakasi()

    def ja_to_ipa(text: str) -> list[str]:
        romaji_to_phones = {
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
            "desu": ["d", "e", "s", "U"], "masu": ["m", "a", "s", "U"]
        }
        res = kks.convert(text)
        phones = []
        for item in res:
            rom = item['hepburn'].lower()
            idx = 0
            while idx < len(rom):
                matched = False
                for length in [4, 3, 2, 1]:
                    sub = rom[idx:idx+length]
                    if sub in romaji_to_phones:
                        for p in romaji_to_phones[sub]:
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

    ja_latencies = []
    for _ in range(3):
        t0 = time.perf_counter()
        ipa = ja_to_ipa("こんにちは、お会いできて嬉しいです。")
        p_ids = ja_voice.phonemes_to_ids(ipa)
        _ = ja_voice.phoneme_ids_to_audio(p_ids)
        ja_latencies.append((time.perf_counter() - t0) * 1000)

    end_ram = get_current_process_ram_mb()
    res = {
        "model": "Piper TTS (en: amy-low, ja: hi_fi_captain-medium)",
        "license": "MIT / Public Domain",
        "en_synthesis_median_ms": round(float(np.median(en_latencies)), 2),
        "ja_synthesis_median_ms": round(float(np.median(ja_latencies)), 2),
        "ram_usage_mb": round(end_ram - start_ram, 2)
    }
    logger.info(f"TTS Results: {res}")
    return res

def run_phase1():
    manager = ModelManager("models_cache")
    hw = detect_hardware()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": hw,
        "results": {
            "vad": benchmark_vad(manager),
            "stt": benchmark_stt(manager, "base"),
            "translation": benchmark_translation(),
            "tts": benchmark_tts()
        }
    }

    # Calculate end-to-end estimated latencies
    en_to_ja_est = (
        report["results"]["vad"]["chunk_latency_median_ms"] +
        report["results"]["stt"]["transcribe_2s_latency_median_ms"] +
        report["results"]["translation"]["en_to_ja_latency_median_ms"] +
        report["results"]["tts"]["ja_synthesis_median_ms"] +
        40.0 # audio I/O buffer
    )
    ja_to_en_est = (
        report["results"]["vad"]["chunk_latency_median_ms"] +
        report["results"]["stt"]["transcribe_2s_latency_median_ms"] +
        report["results"]["translation"]["ja_to_en_latency_median_ms"] +
        report["results"]["tts"]["en_synthesis_median_ms"] +
        40.0 # audio I/O buffer
    )

    report["estimated_end_to_end_latency_ms"] = {
        "en_to_ja": round(en_to_ja_est, 2),
        "ja_to_en": round(ja_to_en_est, 2),
        "target_1500ms_met": en_to_ja_est < 1500 and ja_to_en_est < 1500
    }

    total_ram = sum([
        report["results"]["vad"]["ram_usage_mb"],
        report["results"]["stt"]["ram_usage_mb"],
        report["results"]["translation"]["ram_usage_mb"],
        report["results"]["tts"]["ram_usage_mb"],
    ])
    report["total_pipeline_ram_mb"] = round(total_ram, 2)

    os.makedirs("benchmarks", exist_ok=True)
    out_file = os.path.join("benchmarks", "phase1_benchmark_report.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Phase 1 report saved to {out_file}")
    return report

if __name__ == "__main__":
    run_phase1()
