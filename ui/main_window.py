"""Main Desktop Application Window for EchoBridge Speech Translator."""
import os
import sys
import json
import logging
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QFrame, 
    QProgressBar, QTextEdit, QTabWidget, QSplitter,
    QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QPalette

from pipeline.translator import TranslationPipeline
from pipeline.conversation import ConversationManager, ConversationTurn
from ui.conversation_view import ConversationView
from ui.settings_view import SettingsDialog

logger = logging.getLogger(__name__)

class PipelineWorker(QThread):
    """Background worker thread to handle speech translation inference off the UI thread."""
    speech_detected = Signal()
    transcription_ready = Signal(str, str, float)
    translation_ready = Signal(str, float)
    synthesis_ready = Signal(bytes, int, float)
    pipeline_completed = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, manager: ConversationManager):
        super().__init__()
        self.manager = manager
        self._setup_callbacks()

    def _setup_callbacks(self):
        pipeline = self.manager.pipeline
        pipeline.on_speech_detected = lambda: self.speech_detected.emit()
        pipeline.on_transcription = lambda text, lang, lat: self.transcription_ready.emit(text, lang, lat)
        pipeline.on_translation = lambda text, lat: self.translation_ready.emit(text, lat)
        pipeline.on_synthesis = lambda audio, sr, lat: self.synthesis_ready.emit(audio, sr, lat)
        pipeline.on_pipeline_done = lambda metrics: self.pipeline_completed.emit(metrics)
        pipeline.on_error = lambda err: self.error_occurred.emit(err)

    def start_listening(self):
        self.manager.pipeline.start_listening()

    def stop_listening(self):
        self.manager.pipeline.stop_listening()


class MainWindow(QMainWindow):
    def __init__(self, config_path: str = "config/settings.json"):
        super().__init__()
        self.config_path = config_path
        self.load_config()

        self.setWindowTitle("EchoBridge — Offline Real-Time Speech Translator")
        self.resize(1000, 750)
        self.setMinimumSize(850, 600)

        # Initialize conversation manager and background worker
        self.manager = ConversationManager(
            lang_a=self.config.get("general", {}).get("source_language", "en"),
            lang_b=self.config.get("general", {}).get("target_language", "ja"),
            models_dir=self.config.get("models_dir", "models_cache"),
            stt_size=self.config.get("stt", {}).get("model_size", "base"),
            auto_playback=self.config.get("audio", {}).get("auto_playback", True)
        )
        self.worker = PipelineWorker(self.manager)
        self.connect_worker_signals()

        self.last_audio_bytes = b""
        self.last_sample_rate = 16000

        self.setup_ui()
        self.apply_dark_theme()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def connect_worker_signals(self):
        self.worker.speech_detected.connect(self.on_speech_detected)
        self.worker.transcription_ready.connect(self.on_transcription_ready)
        self.worker.translation_ready.connect(self.on_translation_ready)
        self.worker.synthesis_ready.connect(self.on_synthesis_ready)
        self.worker.pipeline_completed.connect(self.on_pipeline_completed)
        self.worker.error_occurred.connect(self.on_error_occurred)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # --- Top Header Bar ---
        header = QHBoxLayout()
        title_label = QLabel("🌉 EchoBridge")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")

        badge = QLabel("● 100% Offline Local Inference")
        badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        """)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.clicked.connect(self.open_settings)

        header.addWidget(title_label)
        header.addWidget(badge)
        header.addStretch()
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        # --- Language Selector & Control Bar ---
        ctrl_card = QFrame()
        ctrl_card.setObjectName("controlCard")
        ctrl_layout = QHBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(16, 12, 16, 12)
        ctrl_layout.setSpacing(12)

        # Source Lang Combo
        self.src_combo = QComboBox()
        self.src_combo.addItem("🇺🇸 English", "en")
        self.src_combo.addItem("🇯🇵 Japanese", "ja")
        self.src_combo.currentIndexChanged.connect(self.on_lang_combo_changed)

        # Swap Button
        self.swap_btn = QPushButton("⇄ Swap")
        self.swap_btn.setObjectName("swapBtn")
        self.swap_btn.clicked.connect(self.on_swap_clicked)

        # Target Lang Combo
        self.tgt_combo = QComboBox()
        self.tgt_combo.addItem("🇯🇵 Japanese", "ja")
        self.tgt_combo.addItem("🇺🇸 English", "en")
        self.tgt_combo.currentIndexChanged.connect(self.on_lang_combo_changed)

        # Mic Toggle Button
        self.mic_btn = QPushButton("🎤 Start Listening")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.clicked.connect(self.toggle_microphone)

        # Push to Talk
        self.ptt_btn = QPushButton("✋ Push to Talk")
        self.ptt_btn.setObjectName("pttBtn")
        self.ptt_btn.pressed.connect(self.on_ptt_pressed)
        self.ptt_btn.released.connect(self.on_ptt_released)

        # Speaker Mute Toggle
        self.mute_btn = QPushButton("🔊 Audio: ON")
        self.mute_btn.setObjectName("muteBtn")
        self.mute_btn.clicked.connect(self.toggle_mute)

        ctrl_layout.addWidget(QLabel("Speak:"))
        ctrl_layout.addWidget(self.src_combo)
        ctrl_layout.addWidget(self.swap_btn)
        ctrl_layout.addWidget(QLabel("Translate to:"))
        ctrl_layout.addWidget(self.tgt_combo)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.ptt_btn)
        ctrl_layout.addWidget(self.mic_btn)
        ctrl_layout.addWidget(self.mute_btn)
        main_layout.addWidget(ctrl_card)

        # --- Status & VAD Mic Indicator Bar ---
        status_bar_layout = QHBoxLayout()
        self.status_label = QLabel("Ready. Press 'Start Listening' or hold 'Push to Talk'.")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")

        self.vad_indicator = QLabel("● Mic Idle")
        self.vad_indicator.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold;")

        status_bar_layout.addWidget(self.status_label)
        status_bar_layout.addStretch()
        status_bar_layout.addWidget(self.vad_indicator)
        main_layout.addLayout(status_bar_layout)

        # --- Main View Tabs (Live Translation vs Conversation History) ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")

        # Tab 1: Live Translation Panels
        live_widget = QWidget()
        live_layout = QHBoxLayout(live_widget)
        live_layout.setContentsMargins(0, 10, 0, 0)
        live_layout.setSpacing(14)

        # Left: Original Speech Card
        orig_card = QFrame()
        orig_card.setObjectName("textCard")
        orig_layout = QVBoxLayout(orig_card)
        orig_header = QLabel("Original Transcription")
        orig_header.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 13px;")
        self.orig_text = QTextEdit()
        self.orig_text.setReadOnly(True)
        self.orig_text.setPlaceholderText("Spoken words will appear here in real-time...")
        orig_layout.addWidget(orig_header)
        orig_layout.addWidget(self.orig_text)

        # Right: Translated Speech Card
        trans_card = QFrame()
        trans_card.setObjectName("textCard")
        trans_layout = QVBoxLayout(trans_card)
        trans_header_layout = QHBoxLayout()
        trans_header = QLabel("Translated Speech")
        trans_header.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        
        self.replay_btn = QPushButton("▶ Replay Audio")
        self.replay_btn.setObjectName("replayBtn")
        self.replay_btn.clicked.connect(self.replay_audio)
        self.replay_btn.setEnabled(False)

        trans_header_layout.addWidget(trans_header)
        trans_header_layout.addStretch()
        trans_header_layout.addWidget(self.replay_btn)

        self.trans_text = QTextEdit()
        self.trans_text.setReadOnly(True)
        self.trans_text.setPlaceholderText("Translated output will be displayed and spoken here...")
        trans_layout.addLayout(trans_header_layout)
        trans_layout.addWidget(self.trans_text)

        live_layout.addWidget(orig_card, stretch=1)
        live_layout.addWidget(trans_card, stretch=1)
        self.tabs.addTab(live_widget, "💬 Live Translation")

        # Tab 2: Conversation History View
        self.conversation_view = ConversationView()
        self.tabs.addTab(self.conversation_view, "📜 Conversation History")

        main_layout.addWidget(self.tabs, stretch=1)

        # --- Latency Telemetry Footer ---
        footer_card = QFrame()
        footer_card.setObjectName("footerCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(14, 8, 14, 8)

        self.stt_lat_label = QLabel("STT: -- ms")
        self.mt_lat_label = QLabel("MT: -- ms")
        self.tts_lat_label = QLabel("TTS: -- ms")
        self.total_lat_label = QLabel("⚡ Total Latency: -- ms")
        self.total_lat_label.setStyleSheet("color: #38bdf8; font-weight: bold;")

        self.target_badge = QLabel("Target: <1.5s")
        self.target_badge.setStyleSheet("color: #94a3b8; font-size: 11px;")

        footer_layout.addWidget(self.stt_lat_label)
        footer_layout.addWidget(QLabel("|"))
        footer_layout.addWidget(self.mt_lat_label)
        footer_layout.addWidget(QLabel("|"))
        footer_layout.addWidget(self.tts_lat_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.target_badge)
        footer_layout.addWidget(self.total_lat_label)
        main_layout.addWidget(footer_card)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }
            QFrame#controlCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 10px;
            }
            QFrame#textCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 10px;
                padding: 10px;
            }
            QFrame#footerCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
            }
            QLabel {
                color: #e2e8f0;
            }
            QComboBox {
                background-color: #1f2937;
                color: #f8fafc;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton#swapBtn {
                background-color: #1f2937;
                color: #38bdf8;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton#swapBtn:hover {
                background-color: #374151;
            }
            QPushButton#micBtn {
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#micBtn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#micBtn[recording="true"] {
                background-color: #dc2626;
            }
            QPushButton#pttBtn {
                background-color: #0d9488;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton#pttBtn:pressed {
                background-color: #059669;
            }
            QPushButton#muteBtn {
                background-color: #1f2937;
                color: #e2e8f0;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton#settingsBtn {
                background-color: #1f2937;
                color: #94a3b8;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton#settingsBtn:hover {
                color: #f8fafc;
                background-color: #374151;
            }
            QPushButton#replayBtn {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton#replayBtn:hover {
                background-color: #334155;
            }
            QTextEdit {
                background-color: #0b0f19;
                color: #f8fafc;
                border: 1px solid #1f2937;
                border-radius: 6px;
                font-size: 15px;
                padding: 8px;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #111827;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #1f2937;
                color: #38bdf8;
                font-weight: bold;
            }
        """)

    # --- UI Event Handlers ---
    def toggle_microphone(self):
        pipeline = self.manager.pipeline
        if not pipeline.capture.is_recording:
            pipeline.start_listening()
            self.mic_btn.setText("⏹ Stop Listening")
            self.mic_btn.setProperty("recording", True)
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            self.status_label.setText("Listening for speech...")
            self.vad_indicator.setText("● Listening")
            self.vad_indicator.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            pipeline.stop_listening()
            self.mic_btn.setText("🎤 Start Listening")
            self.mic_btn.setProperty("recording", False)
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            self.status_label.setText("Microphone stopped.")
            self.vad_indicator.setText("● Mic Idle")
            self.vad_indicator.setStyleSheet("color: #64748b; font-weight: bold;")

    def on_ptt_pressed(self):
        pipeline = self.manager.pipeline
        if not pipeline.capture.is_recording:
            pipeline.start_listening()
            self.status_label.setText("Push-to-Talk active: Speaking...")
            self.vad_indicator.setText("● Recording PTT")
            self.vad_indicator.setStyleSheet("color: #06b6d4; font-weight: bold;")

    def on_ptt_released(self):
        pipeline = self.manager.pipeline
        if pipeline.capture.is_recording:
            pipeline.stop_listening()
            self.status_label.setText("Push-to-Talk released. Processing...")
            self.vad_indicator.setText("● Mic Idle")
            self.vad_indicator.setStyleSheet("color: #64748b; font-weight: bold;")

    def toggle_mute(self):
        playback = self.manager.pipeline.playback
        playback.muted = not playback.muted
        if playback.muted:
            self.mute_btn.setText("🔇 Audio: MUTED")
            self.mute_btn.setStyleSheet("color: #f87171;")
        else:
            self.mute_btn.setText("🔊 Audio: ON")
            self.mute_btn.setStyleSheet("color: #e2e8f0;")

    def on_swap_clicked(self):
        self.manager.toggle_direction()
        # Update comboboxes
        src = self.manager.pipeline.source_lang
        tgt = self.manager.pipeline.target_lang
        idx_src = self.src_combo.findData(src)
        idx_tgt = self.tgt_combo.findData(tgt)
        if idx_src >= 0:
            self.src_combo.blockSignals(True)
            self.src_combo.setCurrentIndex(idx_src)
            self.src_combo.blockSignals(False)
        if idx_tgt >= 0:
            self.tgt_combo.blockSignals(True)
            self.tgt_combo.setCurrentIndex(idx_tgt)
            self.tgt_combo.blockSignals(False)
        self.status_label.setText(f"Swapped language direction: {src.upper()} ➔ {tgt.upper()}")

    def on_lang_combo_changed(self):
        src = self.src_combo.currentData()
        tgt = self.tgt_combo.currentData()
        if src == tgt:
            # Auto-swap other combo
            alt = "ja" if src == "en" else "en"
            self.tgt_combo.blockSignals(True)
            self.tgt_combo.setCurrentIndex(self.tgt_combo.findData(alt))
            self.tgt_combo.blockSignals(False)
            tgt = alt
        self.manager.pipeline.set_languages(src, tgt)
        self.status_label.setText(f"Active language direction: {src.upper()} ➔ {tgt.upper()}")

    def open_settings(self):
        dialog = SettingsDialog(self.config_path, self)
        dialog.settings_saved.connect(self.on_settings_updated)
        dialog.exec()

    def on_settings_updated(self, new_config):
        self.config = new_config
        # Apply updated settings
        audio_cfg = new_config.get("audio", {})
        self.manager.pipeline.playback.volume = audio_cfg.get("playback_volume", 1.0)
        self.manager.pipeline.auto_playback = audio_cfg.get("auto_playback", True)
        self.manager.pipeline.playback.device_index = audio_cfg.get("output_device_index")
        self.manager.pipeline.capture.device_index = audio_cfg.get("input_device_index")
        self.status_label.setText("Settings applied.")

    def replay_audio(self):
        if self.last_audio_bytes:
            self.manager.pipeline.playback.play_raw_bytes(
                self.last_audio_bytes,
                sample_rate=self.last_sample_rate
            )
            self.status_label.setText("Replaying translated speech...")

    # --- Worker Callbacks ---
    @Slot()
    def on_speech_detected(self):
        self.vad_indicator.setText("● Speech Active")
        self.vad_indicator.setStyleSheet("color: #f59e0b; font-weight: bold;")
        self.status_label.setText("Speech detected, listening...")

    @Slot(str, str, float)
    def on_transcription_ready(self, text: str, lang: str, lat: float):
        self.orig_text.setPlainText(text)
        self.stt_lat_label.setText(f"STT: {lat:.0f} ms")
        self.status_label.setText("Transcribed speech. Translating...")

    @Slot(str, float)
    def on_translation_ready(self, text: str, lat: float):
        self.trans_text.setPlainText(text)
        self.mt_lat_label.setText(f"MT: {lat:.0f} ms")
        self.status_label.setText("Translated. Synthesizing voice...")

    @Slot(bytes, int, float)
    def on_synthesis_ready(self, audio: bytes, sr: int, lat: float):
        self.last_audio_bytes = audio
        self.last_sample_rate = sr
        self.replay_btn.setEnabled(True)
        self.tts_lat_label.setText(f"TTS: {lat:.0f} ms")
        self.status_label.setText("Playing translated speech aloud...")

    @Slot(dict)
    def on_pipeline_completed(self, metrics: dict):
        total_lat = metrics.get("total_e2e_latency_ms", 0)
        self.total_lat_label.setText(f"⚡ Total Latency: {total_lat:.0f} ms")
        
        target_met = total_lat < 1500
        target_color = "#34d399" if target_met else "#f59e0b"
        self.target_badge.setText("Target: <1.5s ✓" if target_met else "Target: <1.5s (High)")
        self.target_badge.setStyleSheet(f"color: {target_color}; font-weight: bold;")

        # Add to conversation history view
        turn = self.manager.history[-1] if self.manager.history else None
        if turn:
            self.conversation_view.add_turn({
                "speaker_lang": turn.speaker_lang,
                "target_lang": turn.target_lang,
                "original_text": turn.original_text,
                "translated_text": turn.translated_text,
                "total_latency_ms": turn.total_latency_ms,
                "time_str": time.strftime("%H:%M:%S", time.localtime(turn.timestamp))
            })

        self.vad_indicator.setText("● Listening")
        self.vad_indicator.setStyleSheet("color: #10b981; font-weight: bold;")
        self.status_label.setText("Ready for next utterance.")

    @Slot(str)
    def on_error_occurred(self, err_msg: str):
        self.status_label.setText(f"Error: {err_msg}")
        self.status_label.setStyleSheet("color: #f87171;")

    def closeEvent(self, event):
        """Clean shutdown of background threads and audio streams."""
        self.manager.pipeline.stop_listening()
        self.manager.pipeline.playback.stop()
        event.accept()
