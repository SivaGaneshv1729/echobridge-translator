"""Settings dialog and configuration widget for EchoBridge."""
import json
import os
from typing import Dict, Any, Callable, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QSlider, QCheckBox, QPushButton, 
    QGroupBox, QFormLayout, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal

from audio.capture import AudioCapture
from audio.playback import AudioPlayback

class SettingsDialog(QDialog):
    settings_saved = Signal(dict)

    def __init__(self, config_path: str = "config/settings.json", parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.setWindowTitle("EchoBridge Settings")
        self.resize(500, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #38bdf8;
            }
            QLabel {
                color: #cbd5e1;
            }
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px;
                color: #f8fafc;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #334155;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f8fafc;
                border: 1px solid #38bdf8;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QPushButton {
                background-color: #38bdf8;
                color: #0f172a;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
            QPushButton#cancelBtn {
                background-color: #334155;
                color: #f8fafc;
            }
        """)

        self.load_config()
        self.setup_ui()

    def load_config(self):
        default = {
            "stt": {"model_size": "base"},
            "audio": {"input_device_index": None, "output_device_index": None, "auto_playback": True, "playback_volume": 1.0},
            "vad": {"threshold": 0.5},
            "coach": {
                "provider": "builtin",
                "ollama_model": "qwen2.5:0.5b",
                "ollama_url": "http://localhost:11434",
                "api_url": "",
                "api_key": ""
            }
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = default
        else:
            self.config = default

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 1. Audio Devices
        audio_group = QGroupBox("Audio Devices")
        audio_layout = QFormLayout(audio_group)

        self.input_combo = QComboBox()
        self.input_combo.addItem("Default Microphone", None)
        inputs = AudioCapture.list_input_devices()
        cur_in = self.config.get("audio", {}).get("input_device_index")
        for dev in inputs:
            self.input_combo.addItem(f"{dev['name']}", dev['index'])
            if cur_in == dev['index']:
                self.input_combo.setCurrentIndex(self.input_combo.count() - 1)

        self.output_combo = QComboBox()
        self.output_combo.addItem("Default Speaker", None)
        outputs = AudioPlayback.list_output_devices()
        cur_out = self.config.get("audio", {}).get("output_device_index")
        for dev in outputs:
            self.output_combo.addItem(f"{dev['name']}", dev['index'])
            if cur_out == dev['index']:
                self.output_combo.setCurrentIndex(self.output_combo.count() - 1)

        audio_layout.addRow("Microphone Input:", self.input_combo)
        audio_layout.addRow("Speaker Output:", self.output_combo)
        layout.addWidget(audio_group)

        # 2. Inference Models & Latency
        model_group = QGroupBox("Speech Recognition & Latency Mode")
        model_layout = QFormLayout(model_group)

        self.model_combo = QComboBox()
        self.model_combo.addItem("Speed Mode — Faster-Whisper Tiny (Latency ~650ms)", "tiny")
        self.model_combo.addItem("Accuracy Mode — Faster-Whisper Base (Latency ~1.1s)", "base")
        
        cur_model = self.config.get("stt", {}).get("model_size", "base")
        if cur_model == "tiny":
            self.model_combo.setCurrentIndex(0)
        else:
            self.model_combo.setCurrentIndex(1)

        model_layout.addRow("STT Model:", self.model_combo)
        layout.addWidget(model_group)

        # 3. AI Language Coach & Conversational Tutor
        coach_group = QGroupBox("🎓 AI Language Coach & Tutor Engine")
        coach_layout = QFormLayout(coach_group)

        self.coach_provider_combo = QComboBox()
        self.coach_provider_combo.addItem("100% Offline Rule & Linguistic Heuristics (<1ms, 0MB RAM)", "builtin")
        self.coach_provider_combo.addItem("Local Ollama SLM/LLM (e.g. Qwen2.5 / Llama3)", "ollama")
        self.coach_provider_combo.addItem("Custom Cloud / OpenAI-Compatible Endpoint", "api")
        
        cur_prov = self.config.get("coach", {}).get("provider", "builtin")
        idx = self.coach_provider_combo.findData(cur_prov)
        if idx >= 0:
            self.coach_provider_combo.setCurrentIndex(idx)

        self.ollama_model_edit = QLineEdit()
        self.ollama_model_edit.setPlaceholderText("e.g. qwen2.5:0.5b or llama3.2")
        self.ollama_model_edit.setText(self.config.get("coach", {}).get("ollama_model", "qwen2.5:0.5b"))

        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self.ollama_url_edit.setText(self.config.get("coach", {}).get("ollama_url", "http://localhost:11434"))

        coach_layout.addRow("Coach Provider:", self.coach_provider_combo)
        coach_layout.addRow("Ollama / API Model:", self.ollama_model_edit)
        coach_layout.addRow("Endpoint URL:", self.ollama_url_edit)
        layout.addWidget(coach_group)

        # 4. Voice Activity & Playback Controls
        ctrl_group = QGroupBox("Voice Activity & Playback")
        ctrl_layout = QFormLayout(ctrl_group)

        # VAD Threshold Slider (0.2 to 0.8)
        self.vad_slider = QSlider(Qt.Horizontal)
        self.vad_slider.setRange(20, 80)
        cur_vad = int(self.config.get("vad", {}).get("threshold", 0.5) * 100)
        self.vad_slider.setValue(cur_vad)
        self.vad_val_label = QLabel(f"{cur_vad / 100:.2f}")
        self.vad_slider.valueChanged.connect(lambda v: self.vad_val_label.setText(f"{v / 100:.2f}"))

        vad_row = QHBoxLayout()
        vad_row.addWidget(self.vad_slider)
        vad_row.addWidget(self.vad_val_label)
        ctrl_layout.addRow("Speech Sensitivity (VAD):", vad_row)

        # Volume Slider
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        cur_vol = int(self.config.get("audio", {}).get("playback_volume", 1.0) * 100)
        self.vol_slider.setValue(cur_vol)
        self.vol_val_label = QLabel(f"{cur_vol}%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_val_label.setText(f"{v}%"))

        vol_row = QHBoxLayout()
        vol_row.addWidget(self.vol_slider)
        vol_row.addWidget(self.vol_val_label)
        ctrl_layout.addRow("Playback Volume:", vol_row)

        self.autoplay_cb = QCheckBox("Automatically play translated speech aloud")
        self.autoplay_cb.setChecked(self.config.get("audio", {}).get("auto_playback", True))
        ctrl_layout.addRow("", self.autoplay_cb)

        layout.addWidget(ctrl_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def save_settings(self):
        in_idx = self.input_combo.currentData()
        out_idx = self.output_combo.currentData()
        model_size = self.model_combo.currentData()
        vad_thresh = self.vad_slider.value() / 100.0
        vol = self.vol_slider.value() / 100.0
        autoplay = self.autoplay_cb.isChecked()
        coach_prov = self.coach_provider_combo.currentData()
        ollama_model = self.ollama_model_edit.text().strip()
        ollama_url = self.ollama_url_edit.text().strip()

        if "audio" not in self.config:
            self.config["audio"] = {}
        if "stt" not in self.config:
            self.config["stt"] = {}
        if "vad" not in self.config:
            self.config["vad"] = {}
        if "coach" not in self.config:
            self.config["coach"] = {}

        self.config["audio"]["input_device_index"] = in_idx
        self.config["audio"]["output_device_index"] = out_idx
        self.config["audio"]["playback_volume"] = vol
        self.config["audio"]["auto_playback"] = autoplay
        self.config["stt"]["model_size"] = model_size
        self.config["vad"]["threshold"] = vad_thresh
        self.config["coach"]["provider"] = coach_prov
        self.config["coach"]["ollama_model"] = ollama_model
        self.config["coach"]["ollama_url"] = ollama_url

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

        self.settings_saved.emit(self.config)
        self.accept()
