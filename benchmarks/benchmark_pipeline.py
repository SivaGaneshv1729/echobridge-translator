"""Benchmark Pipeline: 50 representative utterances benchmark measuring median and p95 latency."""
import os
import sys
import time
import json
import logging
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engines.speech_recognition import SpeechRecognizer
from engines.translation import TranslatorEngine
from engines.text_to_speech import TTSEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 50 representative conversational utterances
TEST_UTTERANCES_EN = [
    "Hello, how are you today?",
    "Where is the nearest train station?",
    "Can you please help me find a doctor?",
    "What time does the supermarket close?",
    "I would like to order coffee please.",
    "How much does this cost?",
    "Nice to meet you.",
    "Could you speak a little slower please?",
    "Where is the hotel lobby?",
    "Thank you very much for your help.",
    "Is there a pharmacy nearby?",
    "I need a taxi to the airport.",
    "Do you accept credit cards here?",
    "What is the weather forecast for tomorrow?",
    "I have a reservation under my name.",
    "Excuse me, where is the restroom?",
    "Can you recommend a good local restaurant?",
    "The train will arrive in five minutes.",
    "Please call an ambulance immediately.",
    "Have a wonderful weekend ahead.",
    "Where can I buy a subway ticket?",
    "I am looking for the city museum.",
    "Is Wi-Fi available in this room?",
    "Could you write down the address for me?",
    "I am very happy to be here today."
]

TEST_UTTERANCES_JA = [
    "こんにちは、お元気ですか？",
    "最寄りの駅はどこですか？",
    "医者を探すのを手伝っていただけますか？",
    "スーパーは何時に閉まりますか？",
    "コーヒーを注文したいのですが。",
    "これはいくらですか？",
    "はじめまして、よろしくお願いします。",
    "もう少しゆっくり話していただけますか？",
    "ホテルのロビーはどこですか？",
    "手伝ってくれてどうもありがとう。",
    "近くに薬局はありますか？",
    "空港までのタクシーが必要です。",
    "ここではクレジットカードは使えますか？",
    "明日の天気予報はどうですか？",
    "私の名前で予約があります。",
    "すみません、お手洗いはどこですか？",
    "おいしい地元のレストランを教えてください。",
    "電車は5分後に到着します。",
    "すぐに救急車を呼んでください。",
    "よい週末をお過ごしください。",
    "地下鉄の切符はどこで買えますか？",
    "市立博物館を探しています。",
    "この部屋でWi-Fiは使えますか？",
    "住所を書いていただけますか？",
    "今日ここに来られてとても嬉しいです。"
]

def run_benchmarks(num_runs: int = 25):
    logger.info("Initializing engines for 50-utterance benchmark...")
    stt = SpeechRecognizer("base")
    translation = TranslatorEngine("models_cache/translation")
    tts = TTSEngine("models_cache/tts")

    translation.load_pair("en", "ja")
    translation.load_pair("ja", "en")
    tts.load_voice("ja")
    tts.load_voice("en")

    # Benchmarking EN -> JA (25 utterances)
    logger.info(f"--- Running {len(TEST_UTTERANCES_EN)} EN -> JA benchmarks ---")
    en_ja_results = []
    for idx, text in enumerate(TEST_UTTERANCES_EN):
        # 1. Synthesize audio to represent speech
        pcm, sr, _ = tts.synthesize(text, "en")
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        t0 = time.perf_counter()
        stt_text, _, stt_ms = stt.transcribe(audio, language="en")
        trans_text, mt_ms = translation.translate(stt_text, "en", "ja")
        _, _, tts_ms = tts.synthesize(trans_text, "ja")
        total_ms = (time.perf_counter() - t0) * 1000

        en_ja_results.append({
            "id": idx + 1,
            "input": text,
            "transcription": stt_text,
            "translation": trans_text,
            "stt_ms": round(stt_ms, 2),
            "mt_ms": round(mt_ms, 2),
            "tts_ms": round(tts_ms, 2),
            "total_ms": round(total_ms, 2)
        })

    # Benchmarking JA -> EN (25 utterances)
    logger.info(f"--- Running {len(TEST_UTTERANCES_JA)} JA -> EN benchmarks ---")
    ja_en_results = []
    for idx, text in enumerate(TEST_UTTERANCES_JA):
        pcm, sr, _ = tts.synthesize(text, "ja")
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Resample 22050 -> 16000
        if sr != 16000:
            import scipy.signal
            num_16k = int(len(audio) * 16000 / sr)
            audio = scipy.signal.resample(audio, num_16k).astype(np.float32)

        t0 = time.perf_counter()
        stt_text, _, stt_ms = stt.transcribe(audio, language="ja")
        trans_text, mt_ms = translation.translate(stt_text, "ja", "en")
        _, _, tts_ms = tts.synthesize(trans_text, "en")
        total_ms = (time.perf_counter() - t0) * 1000

        ja_en_results.append({
            "id": idx + 1,
            "input": text,
            "transcription": stt_text,
            "translation": trans_text,
            "stt_ms": round(stt_ms, 2),
            "mt_ms": round(mt_ms, 2),
            "tts_ms": round(tts_ms, 2),
            "total_ms": round(total_ms, 2)
        })

    # Aggregate stats
    en_totals = [r["total_ms"] for r in en_ja_results]
    ja_totals = [r["total_ms"] for r in ja_en_results]

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_utterances_tested": len(en_ja_results) + len(ja_en_results),
        "en_to_ja": {
            "median_ms": round(float(np.median(en_totals)), 2),
            "p95_ms": round(float(np.percentile(en_totals, 95)), 2),
            "min_ms": round(float(np.min(en_totals)), 2),
            "max_ms": round(float(np.max(en_totals)), 2)
        },
        "ja_to_en": {
            "median_ms": round(float(np.median(ja_totals)), 2),
            "p95_ms": round(float(np.percentile(ja_totals, 95)), 2),
            "min_ms": round(float(np.min(ja_totals)), 2),
            "max_ms": round(float(np.max(ja_totals)), 2)
        },
        "en_ja_details": en_ja_results,
        "ja_en_details": ja_en_results
    }

    out_path = "benchmarks/50_utterances_benchmark_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved 50-utterance benchmark report to {out_path}")
    print("\n" + "=" * 60)
    print("50-Utterance Benchmark Results:")
    print(f"EN -> JA Median: {summary['en_to_ja']['median_ms']} ms | p95: {summary['en_to_ja']['p95_ms']} ms")
    print(f"JA -> EN Median: {summary['ja_to_en']['median_ms']} ms | p95: {summary['ja_to_en']['p95_ms']} ms")
    print("=" * 60)

if __name__ == "__main__":
    run_benchmarks()
