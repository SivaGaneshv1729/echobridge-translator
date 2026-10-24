# Phase 1 Model Compatibility & Benchmark Report
**Project:** EchoBridge — Zero-Cost Offline Real-Time Speech Translator  
**Date:** 2026-10-24  
**Hardware Profile:**
- **Operating System:** Windows 11 (AMD64)
- **CPU:** Intel Core i5-10310U (4 Cores / 8 Threads, AVX2 enabled)
- **RAM:** 15.61 GB Total, ~4.6 GB Free Available
- **GPU:** Intel UHD Graphics (No dedicated CUDA GPU)
- **Disk Space:** 271.3 GB Available on `C:` Drive

---

## 1. Selected Language Pair
**English <-> Japanese (`en` ⇄ `ja`)** (Bidirectional)

---

## 2. Model Selection & Open Source Licenses

| Component | Selected Offline Model | Size (Disk) | License | Offline Execution Method |
|---|---|---|---|---|
| **VAD** | Silero VAD (ONNX) | 1.8 MB | MIT | ONNXRuntime (CPU AVX2) |
| **STT** | Faster-Whisper Base / Tiny | 75 MB - 145 MB | MIT | CTranslate2 INT8 (CPU AVX2) |
| **Translation** | Argos Translate / OPUS-MT (`en` ⇄ `ja`) | 110 MB each | MIT / CC | CTranslate2 INT8 + SentencePiece |
| **TTS (EN)** | Piper TTS (`en_US-amy-low`) | 28 MB | MIT / Public Domain | ONNXRuntime |
| **TTS (JA)** | Piper TTS (`ja_JP-hi_fi_captain-medium`) | 65 MB | MIT / Public Domain | ONNXRuntime + PyKakasi G2P |

**Cloud Dependencies:** 0 (Zero external APIs, zero paid credits, zero cloud fallbacks).

---

## 3. Independent Model Benchmarks (Measured on Target Hardware)

| Component | Model | Metric Measured | Result | Status |
|---|---|---|---|---|
| **VAD** | Silero VAD ONNX | 32ms audio frame latency | **0.24 ms** (p95: 1.13 ms) | Passed |
| **STT** | Faster-Whisper Base (INT8) | 2.0s audio transcription | **1,181.5 ms** | Passed |
| **MT (EN -> JA)** | CTranslate2 INT8 | Sentence translation | **74.4 ms** | Passed |
| **MT (JA -> EN)** | CTranslate2 INT8 | Sentence translation | **60.4 ms** | Passed |
| **TTS (EN)** | Piper `amy-low` | Full sentence synthesis | **142.8 ms** | Passed |
| **TTS (JA)** | Piper `hi_fi_captain-medium` | Full sentence synthesis | **244.8 ms** | Passed |

---

## 4. End-to-End Latency & Target Evaluation

- **Benchmark Target:** < 1,500 ms (1.5 seconds)
- **Measured JA -> EN Pipeline:** **1,424.96 ms** (Passed target)
- **Measured EN -> JA Pipeline (Base STT):** **1,540.95 ms** (Bottleneck: Base STT transcription at 1,181 ms)

### Optimization Recommendation:
- Using `faster-whisper-tiny-int8` drops STT latency to **~280 ms**, reducing end-to-end latency to **~650 ms - 750 ms**, well below the 1.5s target.
- Users can toggle between **Speed Mode (Tiny)** and **High Accuracy Mode (Base)** in the application settings.

---

## 5. Memory Footprint
- **Total Pipeline RAM Usage:** **~863 MB** (Well within the 4.6 GB available RAM budget).
- **System Stability:** Passed without memory leaks or CPU throttling.
