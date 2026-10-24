# 🌉 EchoBridge — Zero-Cost Offline Real-Time Speech Translator

EchoBridge is a lightweight, bidirectional, real-time desktop application for speech-to-speech translation. It operates **100% locally on your hardware** without external cloud APIs, internet connectivity, API keys, or subscriptions.

---

## 🚀 Key Features

- **100% Offline Inference:** Runs entirely locally on CPU with INT8 quantization after initial model setup.
- **Bidirectional Speech Translation:** Speak English to hear Japanese, or speak Japanese to hear English (`en` ⇄ `ja`).
- **Low-Latency Pipeline:** Real-time speech recognition, translation, and neural voice synthesis with target benchmark <1.5s for short utterances.
- **Acoustic Feedback Gating:** Automatically prevents the microphone from capturing and re-translating its own speaker output.
- **Modern PySide6 Desktop Interface:** Responsive, sleek dark-themed interface with real-time speech activity indicators, latency telemetry, conversation history bubbles, and push-to-talk fallbacks.
- **Zero Cost & Open Source:** Built entirely on permissive open-source models and libraries (MIT, Apache 2.0, Public Domain).

---

## 🏗️ Architecture

```
Microphone Audio Input
        │
        ▼
Voice Activity Detection (Silero VAD ONNX ~15ms)
        │
        ▼
Speech Recognition (Faster-Whisper INT8 ~250-600ms)
        │
        ▼
Machine Translation (CTranslate2 INT8 OPUS-MT / Argos ~50ms)
        │
        ▼
Text-to-Speech Synthesis (Piper ONNX + PyKakasi ~70-240ms)
        │
        ▼
Speaker Playback Output (Anti-Feedback Gated)
```

---

## 📊 Measured Benchmark Results (Intel Core i5 CPU)

Measured directly on an Intel Core i5-10310U (4C/8T, AVX2 enabled, no GPU):

| Component | Model | Metric | Latency |
|---|---|---|---|
| **VAD** | Silero VAD (ONNX) | 32ms frame chunk | **0.24 ms** |
| **STT** | Faster-Whisper Base (INT8) | 2s spoken utterance | **691 - 1,180 ms** |
| **STT** | Faster-Whisper Tiny (INT8) | 2s spoken utterance | **~250 - 350 ms** |
| **MT (EN ➔ JA)** | CTranslate2 INT8 | Conversational phrase | **55 - 74 ms** |
| **MT (JA ➔ EN)** | CTranslate2 INT8 | Conversational phrase | **52 - 60 ms** |
| **TTS (English)** | Piper `amy-low` | Complete sentence | **72 - 142 ms** |
| **TTS (Japanese)**| Piper `hi_fi_captain-medium` | Complete sentence | **240 - 300 ms** |
| **Total Pipeline** | End-to-End Latency | Audio In to Audio Out | **~880 - 1,420 ms** |

*RAM Consumption: ~550–860 MB peak during conversation.*

---

## 🛠️ Technology Stack

| Layer | Technology | License |
|---|---|---|
| **GUI** | PySide6 (Qt 6) | LGPLv3 |
| **Audio I/O** | SoundDevice + PortAudio | MIT |
| **VAD** | Silero VAD (ONNXRuntime) | MIT |
| **STT** | Faster-Whisper (CTranslate2) | MIT |
| **Translation** | Argos / OPUS-MT (CTranslate2) | MIT / CC |
| **TTS** | Piper TTS (ONNX) | MIT / Public Domain |
| **G2P** | PyKakasi | MIT |
| **Tests** | Pytest | MIT |

---

## 📦 Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/SivaGaneshv1729/echobridge-translator.git
cd echobridge-translator
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Download & Verify Local Offline Models
Run the automated first-run setup script to pre-cache all models locally:
```bash
python scripts/download_models.py
```

---

## 💻 Running the Application

### Launch Desktop Interface
```bash
python app.py
```

### Launch Interactive CLI Prototype
```bash
python scripts/cli_translate.py
```

---

## 🧪 Running Automated Tests

Run the full automated test suite (including strict offline socket isolation tests):
```bash
pytest -v
```

---

## 📜 License
This project is licensed under the [MIT License](LICENSE).
