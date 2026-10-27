"""Enhanced Modern Desktop GUI for EchoBridge with Live Audio VU Meter and Clear High-Contrast Controls."""
import os
import sys
import json
import time
import logging
from typing import Optional, Dict, Any
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QFrame, 
    QProgressBar, QTextEdit, QTabWidget, QSplitter,
    QStatusBar, QMessageBox, QGraphicsDropShadowEffect,
    QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QKeySequence, QShortcut

from pipeline.translator import TranslationPipeline
from pipeline.conversation import ConversationManager, ConversationTurn
from ui.conversation_view import ConversationView
from ui.visualizer import SoundwaveVisualizer
from ui.overlay_window import SubtitleOverlayWindow
from ui.settings_view import SettingsDialog
from engines.text_to_speech import TTSEngine

logger = logging.getLogger(__name__)

class PipelineWorker(QThread):
    """Background worker thread to handle speech translation inference off the UI thread."""
    audio_level_changed = Signal(float)
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
        pipeline.on_audio_level = lambda lvl: self.audio_level_changed.emit(lvl)
        pipeline.on_speech_detected = lambda: self.speech_detected.emit()
        pipeline.on_transcription = lambda text, lang, lat: self.transcription_ready.emit(text, lang, lat)
        pipeline.on_translation = lambda text, lat: self.translation_ready.emit(text, lat)
        pipeline.on_synthesis = lambda audio, sr, lat: self.synthesis_ready.emit(audio, sr, lat)
        
        orig_done = self.manager._handle_pipeline_result
        def _on_done(metrics):
            if orig_done:
                orig_done(metrics)
            self.pipeline_completed.emit(metrics)
        pipeline.on_pipeline_done = _on_done
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
        self.resize(1060, 780)
        self.setMinimumSize(900, 650)

        # Initialize conversation manager and background worker with Auto-Detect as default
        self.manager = ConversationManager(
            lang_a=self.config.get("general", {}).get("source_language", "en"),
            lang_b=self.config.get("general", {}).get("target_language", "ja"),
            models_dir=self.config.get("models_dir", "models_cache"),
            stt_size=self.config.get("stt", {}).get("model_size", "base"),
            auto_playback=self.config.get("audio", {}).get("auto_playback", True)
        )
        self.manager.pipeline.source_lang = "auto"
        self.manager.pipeline.target_lang = "auto"
        self.worker = PipelineWorker(self.manager)
        self.connect_worker_signals()

        self.last_audio_bytes = b""
        self.last_sample_rate = 16000
        self.overlay_window: Optional[SubtitleOverlayWindow] = None

        self.setup_ui()
        self.apply_dark_theme()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def connect_worker_signals(self):
        self.worker.audio_level_changed.connect(self.on_audio_level)
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
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # --- Top Header Bar ---
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_label = QLabel("EchoBridge")
        title_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px;")
        sub_title = QLabel("Zero-Cost Offline Real-Time Speech Translator")
        sub_title.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(title_label)
        title_box.addWidget(sub_title)

        badge = QLabel("100% OFFLINE MODE")
        badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            padding: 6px 14px;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 800;
            border: 1px solid #059669;
        """)

        self.hud_btn = QPushButton("🪟 Subtitle Overlay")
        self.hud_btn.setObjectName("headerActionBtn")
        self.hud_btn.setFixedHeight(36)
        self.hud_btn.setToolTip("Switch to compact floating subtitle overlay HUD mode (Ctrl+H)")
        self.hud_btn.clicked.connect(self.toggle_overlay_hud)

        self.export_btn = QPushButton("📥 Export Transcript")
        self.export_btn.setObjectName("headerActionBtn")
        self.export_btn.setFixedHeight(36)
        self.export_btn.setToolTip("Save formatted conversation transcript to a text file (Ctrl+E)")
        self.export_btn.clicked.connect(self.export_transcript)

        self.analytics_btn = QPushButton("📊 Fluency Analytics")
        self.analytics_btn.setObjectName("headerActionBtn")
        self.analytics_btn.setFixedHeight(36)
        self.analytics_btn.setToolTip("View spoken fluency score, politeness breakdown, and scenario metrics (Ctrl+A)")
        self.analytics_btn.clicked.connect(self.open_analytics)

        self.deck_btn = QPushButton("🎴 Practice Deck")
        self.deck_btn.setObjectName("headerActionBtn")
        self.deck_btn.setFixedHeight(36)
        self.deck_btn.setToolTip("Review saved flashcards and study corrections with flip cards (Ctrl+D)")
        self.deck_btn.clicked.connect(self.open_flashcards)

        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.setObjectName("headerActionBtn")
        self.clear_btn.setFixedHeight(36)
        self.clear_btn.setToolTip("Reset active conversation feed (Ctrl+Shift+C)")
        self.clear_btn.clicked.connect(self.clear_conversation_history)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedHeight(36)
        self.settings_btn.setToolTip("Configure audio devices, models, and latency (F1)")
        self.settings_btn.clicked.connect(self.open_settings)

        header.addLayout(title_box)
        header.addSpacing(16)
        header.addWidget(badge)
        header.addStretch()
        header.addWidget(self.hud_btn)
        header.addWidget(self.analytics_btn)
        header.addWidget(self.deck_btn)
        header.addWidget(self.export_btn)
        header.addWidget(self.clear_btn)
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        # --- Main Control Panel Card ---
        ctrl_card = QFrame()
        ctrl_card.setObjectName("controlCard")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(18, 16, 18, 16)
        ctrl_layout.setSpacing(14)

        # Row 0: Mode Selector (Translation Mode vs AI Language Coach & Tutor)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)

        self.btn_mode_translate = QPushButton("✨ Live Translation Mode (Bilingual)")
        self.btn_mode_translate.setFixedHeight(34)
        self.btn_mode_translate.setCursor(Qt.PointingHandCursor)
        self.btn_mode_translate.setToolTip("Bidirectional real-time speech-to-speech translation between English & Japanese")
        self.btn_mode_translate.clicked.connect(lambda: self.switch_app_mode("translate"))

        self.btn_mode_coach = QPushButton("🎓 AI Language Coach & Conversational Tutor")
        self.btn_mode_coach.setFixedHeight(34)
        self.btn_mode_coach.setCursor(Qt.PointingHandCursor)
        self.btn_mode_coach.setToolTip("Interactive live conversational practice partner with instant grammar, fluency & politeness coaching")
        self.btn_mode_coach.clicked.connect(lambda: self.switch_app_mode("coach"))

        mode_row.addWidget(self.btn_mode_translate, stretch=1)
        mode_row.addWidget(self.btn_mode_coach, stretch=1)
        ctrl_layout.addLayout(mode_row)

        # Row 1: Languages + Direction Swap
        lang_row = QHBoxLayout()
        lang_row.setSpacing(12)

        src_box = QVBoxLayout()
        self.src_label = QLabel("TRANSLATION MODE")
        self.src_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        self.src_combo = QComboBox()
        self.src_combo.setFixedHeight(38)
        self.src_combo.addItem("✨ AUTO-DETECT (EN ⇄ JA VICE VERSA)", "auto")
        self.src_combo.addItem("English (United States) ➔ Japanese", "en")
        self.src_combo.addItem("Japanese (Japan) ➔ English", "ja")
        self.src_combo.currentIndexChanged.connect(self.on_lang_combo_changed)
        src_box.addWidget(self.src_label)
        src_box.addWidget(self.src_combo)

        self.swap_btn = QPushButton("✨ AUTO ACTIVE")
        self.swap_btn.setObjectName("swapBtn")
        self.swap_btn.setFixedHeight(38)
        self.swap_btn.setFixedWidth(180)
        self.swap_btn.clicked.connect(self.on_swap_clicked)

        tgt_box = QVBoxLayout()
        self.tgt_label = QLabel("OUTPUT SPOKEN LANGUAGE")
        self.tgt_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        self.tgt_combo = QComboBox()
        self.tgt_combo.setFixedHeight(38)
        self.tgt_combo.addItem("Automatic (Vice Versa)", "auto")
        self.tgt_combo.addItem("Japanese (Japan)", "ja")
        self.tgt_combo.addItem("English (United States)", "en")
        self.tgt_combo.setEnabled(False)
        self.tgt_combo.currentIndexChanged.connect(self.on_lang_combo_changed)
        tgt_box.addWidget(self.tgt_label)
        tgt_box.addWidget(self.tgt_combo)

        # Scenario Selector (Visible in Coach Mode)
        self.scenario_box_widget = QWidget()
        sc_box = QVBoxLayout(self.scenario_box_widget)
        sc_box.setContentsMargins(0, 0, 0, 0)
        self.scenario_label = QLabel("PRACTICE ROLE-PLAY SCENARIO")
        self.scenario_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #a5b4fc;")
        self.scenario_combo = QComboBox()
        self.scenario_combo.setFixedHeight(38)
        self.scenario_combo.addItem("🗣️ Free Conversation (日常会話)", "free_talk")
        self.scenario_combo.addItem("🍵 Cafe & Dining (カフェ・飲食店)", "cafe")
        self.scenario_combo.addItem("🚅 Transit & Directions (道案内・駅)", "transit")
        self.scenario_combo.addItem("🏨 Hotel Check-in (ホテル・旅館)", "hotel")
        self.scenario_combo.addItem("💼 Business & Interview (面接・ビジネス)", "business")
        self.scenario_combo.currentIndexChanged.connect(self.on_scenario_changed)
        sc_box.addWidget(self.scenario_label)
        sc_box.addWidget(self.scenario_combo)
        self.scenario_box_widget.hide()

        lang_row.addLayout(src_box, stretch=1)
        lang_row.addWidget(self.swap_btn, alignment=Qt.AlignBottom)
        lang_row.addLayout(tgt_box, stretch=1)
        lang_row.addWidget(self.scenario_box_widget, stretch=1)
        ctrl_layout.addLayout(lang_row)

        self.update_mode_button_styles()

        # Row 2: Action Buttons (Large, high-contrast)
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        # Start Listening Toggle Button
        self.mic_btn = QPushButton("▶  START LISTENING")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.setFixedHeight(44)
        self.mic_btn.setMinimumWidth(200)
        self.mic_btn.setToolTip("Toggle microphone listening (Ctrl+Space)")
        self.mic_btn.clicked.connect(self.toggle_microphone)

        # Push-to-Talk Button
        self.ptt_btn = QPushButton("HOLD TO TALK")
        self.ptt_btn.setObjectName("pttBtn")
        self.ptt_btn.setFixedHeight(44)
        self.ptt_btn.setMinimumWidth(160)
        self.ptt_btn.pressed.connect(self.on_ptt_pressed)
        self.ptt_btn.released.connect(self.on_ptt_released)

        # Speaker Mute Button
        self.mute_btn = QPushButton("AUDIO OUTPUT: ON")
        self.mute_btn.setObjectName("muteBtn")
        self.mute_btn.setFixedHeight(44)
        self.mute_btn.setToolTip("Mute/unmute speaker playback (Ctrl+M)")
        self.mute_btn.clicked.connect(self.toggle_mute)

        # Quick Test Button
        self.test_en_btn = QPushButton("TEST SAMPLE (EN ➔ JA)")
        self.test_en_btn.setObjectName("testBtn")
        self.test_en_btn.setFixedHeight(44)
        self.test_en_btn.clicked.connect(self.run_quick_test)

        action_row.addWidget(self.mic_btn, stretch=2)
        action_row.addWidget(self.ptt_btn, stretch=1)
        action_row.addWidget(self.mute_btn, stretch=1)
        action_row.addWidget(self.test_en_btn, stretch=1)
        ctrl_layout.addLayout(action_row)

        # Row 3: Live Microphone Reactive Soundwave Visualizer & VAD Status Bar
        meter_row = QHBoxLayout()
        meter_row.setSpacing(12)

        mic_icon = QLabel("AUDIO SPECTRUM:")
        mic_icon.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        
        self.visualizer = SoundwaveVisualizer(num_bars=36)

        self.vad_badge = QLabel("MIC IDLE")
        self.vad_badge.setObjectName("vadBadge")
        self.vad_badge.setAlignment(Qt.AlignCenter)
        self.vad_badge.setFixedSize(130, 28)

        meter_row.addWidget(mic_icon)
        meter_row.addWidget(self.visualizer, stretch=1)
        meter_row.addWidget(self.vad_badge)
        ctrl_layout.addLayout(meter_row)

        main_layout.addWidget(ctrl_card)

        # --- Status Banner ---
        self.status_label = QLabel("Ready. Press 'START LISTENING' or hold 'HOLD TO TALK' to begin.")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600; padding: 2px 4px;")
        main_layout.addWidget(self.status_label)

        # --- Main Tabs (Live Translation vs Conversation History) ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")

        # Tab 1: Live Translation
        live_widget = QWidget()
        live_layout = QHBoxLayout(live_widget)
        live_layout.setContentsMargins(0, 10, 0, 0)
        live_layout.setSpacing(14)

        # Left Card: Original Speech
        orig_card = QFrame()
        orig_card.setObjectName("textCard")
        orig_layout = QVBoxLayout(orig_card)
        orig_header_layout = QHBoxLayout()
        orig_header = QLabel("Original Transcription")
        orig_header.setStyleSheet("color: #cbd5e1; font-weight: 800; font-size: 14px;")
        orig_header_layout.addWidget(orig_header)
        orig_header_layout.addStretch()

        self.orig_text = QTextEdit()
        self.orig_text.setReadOnly(True)
        self.orig_text.setPlaceholderText("Spoken words will appear here in real-time as you speak...")
        orig_layout.addLayout(orig_header_layout)
        orig_layout.addWidget(self.orig_text)

        # Right Card: Translated Speech
        trans_card = QFrame()
        trans_card.setObjectName("textCard")
        trans_layout = QVBoxLayout(trans_card)
        trans_header_layout = QHBoxLayout()
        trans_header = QLabel("Translated Speech")
        trans_header.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 14px;")
        
        self.replay_btn = QPushButton("▶ Replay Voice")
        self.replay_btn.setObjectName("replayBtn")
        self.replay_btn.setFixedHeight(30)
        self.replay_btn.clicked.connect(self.replay_audio)
        self.replay_btn.setEnabled(False)

        trans_header_layout.addWidget(trans_header)
        trans_header_layout.addStretch()
        trans_header_layout.addWidget(self.replay_btn)

        self.trans_text = QTextEdit()
        self.trans_text.setReadOnly(True)
        self.trans_text.setPlaceholderText("Translated output will appear and be spoken aloud here...")
        trans_layout.addLayout(trans_header_layout)
        trans_layout.addWidget(self.trans_text)

        live_layout.addWidget(orig_card, stretch=1)
        live_layout.addWidget(trans_card, stretch=1)

        # Tab 1: Modern Conversation Stream (Cards & Replay)
        self.conversation_view = ConversationView()
        self.conversation_view.replay_requested.connect(self.on_conversation_replay)
        self.tabs.addTab(self.conversation_view, "💬 Conversation Stream")

        # Tab 2: Live Translation Side-by-Side
        self.tabs.addTab(live_widget, "⚡ Real-Time Side-by-Side")

        main_layout.addWidget(self.tabs, stretch=1)

        # --- Latency Telemetry Footer ---
        footer_card = QFrame()
        footer_card.setObjectName("footerCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        self.stt_lat_label = QLabel("STT: -- ms")
        self.mt_lat_label = QLabel("MT: -- ms")
        self.tts_lat_label = QLabel("TTS: -- ms")
        self.total_lat_label = QLabel("Total Latency: -- ms")
        self.total_lat_label.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 13px;")

        self.target_badge = QLabel("Benchmark: <1.5s Target")
        self.target_badge.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")

        footer_layout.addWidget(self.stt_lat_label)
        footer_layout.addSpacing(16)
        footer_layout.addWidget(self.mt_lat_label)
        footer_layout.addSpacing(16)
        footer_layout.addWidget(self.tts_lat_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.target_badge)
        footer_layout.addSpacing(16)
        footer_layout.addWidget(self.total_lat_label)
        main_layout.addWidget(footer_card)

        # Initialize global keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Configure convenient global keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle_microphone)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self.toggle_overlay_hud)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_transcript)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.clear_conversation_history)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.toggle_mute)
        QShortcut(QKeySequence("F1"), self, activated=self.open_settings)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QFrame#controlCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 12px;
            }
            QFrame#textCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 12px;
                padding: 12px;
            }
            QFrame#footerCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 10px;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
            QComboBox {
                background-color: #1f2937;
                color: #ffffff;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
            QPushButton#swapBtn {
                background-color: #312e81;
                color: #c7d2fe;
                border: 1px solid #4338ca;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton#swapBtn:hover {
                background-color: #3730a3;
                color: #ffffff;
            }
            QPushButton#micBtn {
                background-color: #059669;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QPushButton#micBtn:hover {
                background-color: #10b981;
            }
            QPushButton#micBtn[recording="true"] {
                background-color: #dc2626;
            }
            QPushButton#micBtn[recording="true"]:hover {
                background-color: #ef4444;
            }
            QPushButton#pttBtn {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#pttBtn:hover {
                background-color: #0ea5e9;
            }
            QPushButton#pttBtn:pressed {
                background-color: #0369a1;
            }
            QPushButton#muteBtn {
                background-color: #1f2937;
                color: #e2e8f0;
                border: 1px solid #374151;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#muteBtn:hover {
                background-color: #374151;
            }
            QPushButton#testBtn {
                background-color: #1e1b4b;
                color: #a5b4fc;
                border: 1px solid #3730a3;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton#testBtn:hover {
                background-color: #312e81;
                color: #ffffff;
            }
            QPushButton#headerActionBtn {
                background-color: #1f2937;
                color: #cbd5e1;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#headerActionBtn:hover {
                color: #ffffff;
                background-color: #374151;
                border-color: #4b5563;
            }
            QPushButton#settingsBtn {
                background-color: #1f2937;
                color: #94a3b8;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton#settingsBtn:hover {
                color: #ffffff;
                background-color: #374151;
            }
            QPushButton#replayBtn {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#replayBtn:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
            QProgressBar#vuBar {
                background-color: #1f2937;
                border-radius: 6px;
            }
            QProgressBar#vuBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:0.8 #06b6d4, stop:1 #f59e0b);
                border-radius: 6px;
            }
            QLabel#vadBadge {
                background-color: #1f2937;
                color: #64748b;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 800;
            }
            QTextEdit {
                background-color: #0b0f19;
                color: #f8fafc;
                border: 1px solid #1f2937;
                border-radius: 8px;
                font-size: 16px;
                line-height: 1.5;
                padding: 12px;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #111827;
                color: #94a3b8;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1f2937;
                color: #38bdf8;
                font-weight: bold;
                border-bottom: 2px solid #38bdf8;
            }
        """)

    # --- UI Event Handlers ---
    def toggle_overlay_hud(self):
        """Switch to compact floating subtitle overlay mode."""
        if self.overlay_window is None:
            self.overlay_window = SubtitleOverlayWindow()
            self.overlay_window.restore_requested.connect(self.restore_from_overlay)
            self.overlay_window.close_requested.connect(self.close_overlay)

        is_rec = self.manager.pipeline.capture.is_recording
        self.overlay_window.set_active_state(is_rec)
        self.overlay_window.show()
        self.hide()

    def restore_from_overlay(self):
        """Restore full application window from overlay mode."""
        if self.overlay_window:
            self.overlay_window.hide()
        self.showNormal()
        self.activateWindow()

    def close_overlay(self):
        """Close overlay and return to normal window."""
        if self.overlay_window:
            self.overlay_window.hide()
        self.showNormal()
        self.activateWindow()

    def toggle_microphone(self):
        pipeline = self.manager.pipeline
        if not pipeline.capture.is_recording:
            pipeline.start_listening()
            self.visualizer.set_active(True)
            if self.overlay_window and self.overlay_window.isVisible():
                self.overlay_window.set_active_state(True)
            self.mic_btn.setText("■  STOP LISTENING")
            self.mic_btn.setProperty("recording", True)
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            self.status_label.setText("Listening for speech... Speak into your microphone now.")
            self.vad_badge.setText("MIC ACTIVE")
            self.vad_badge.setStyleSheet("background-color: #064e3b; color: #34d399; font-weight: bold; border-radius: 6px;")
        else:
            pipeline.stop_listening(flush=True)
            self.visualizer.set_active(False)
            if self.overlay_window and self.overlay_window.isVisible():
                self.overlay_window.set_active_state(False)
            self.mic_btn.setText("▶  START LISTENING")
            self.mic_btn.setProperty("recording", False)
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            self.status_label.setText("Microphone stopped. Processing any pending speech...")
            self.vad_badge.setText("MIC IDLE")
            self.vad_badge.setStyleSheet("background-color: #1f2937; color: #64748b; font-weight: bold; border-radius: 6px;")

    def on_ptt_pressed(self):
        pipeline = self.manager.pipeline
        if not pipeline.capture.is_recording:
            pipeline.start_listening()
            self.visualizer.set_active(True)
            self.status_label.setText("Push-to-Talk active: Speaking...")
            self.vad_badge.setText("HOLDING PTT")
            self.vad_badge.setStyleSheet("background-color: #075985; color: #38bdf8; font-weight: bold; border-radius: 6px;")

    def on_ptt_released(self):
        pipeline = self.manager.pipeline
        if pipeline.capture.is_recording:
            pipeline.stop_listening(flush=True)
            self.visualizer.set_active(False)
            self.status_label.setText("Push-to-Talk released. Processing speech...")
            self.vad_badge.setText("PROCESSING")
            self.vad_badge.setStyleSheet("background-color: #78350f; color: #f59e0b; font-weight: bold; border-radius: 6px;")

    def toggle_mute(self):
        playback = self.manager.pipeline.playback
        playback.muted = not playback.muted
        if playback.muted:
            self.mute_btn.setText("AUDIO OUTPUT: MUTED")
            self.mute_btn.setStyleSheet("color: #f87171; border-color: #ef4444;")
        else:
            self.mute_btn.setText("AUDIO OUTPUT: ON")
            self.mute_btn.setStyleSheet("")

    def update_mode_button_styles(self):
        is_coach = getattr(self.manager.pipeline, "app_mode", "translate") == "coach"
        if not is_coach:
            self.btn_mode_translate.setStyleSheet("""
                background-color: #0c4a6e;
                color: #38bdf8;
                border: 2px solid #0284c7;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
            """)
            self.btn_mode_coach.setStyleSheet("""
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            """)
        else:
            self.btn_mode_translate.setStyleSheet("""
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            """)
            self.btn_mode_coach.setStyleSheet("""
                background-color: #312e81;
                color: #c7d2fe;
                border: 2px solid #6366f1;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
            """)

    def switch_app_mode(self, mode: str):
        if mode == "translate":
            self.manager.pipeline.app_mode = "translate"
            self.src_combo.blockSignals(True)
            self.src_combo.clear()
            self.src_combo.addItem("✨ AUTO-DETECT (EN ⇄ JA VICE VERSA)", "auto")
            self.src_combo.addItem("English (United States) ➔ Japanese", "en")
            self.src_combo.addItem("Japanese (Japan) ➔ English", "ja")
            self.src_combo.setCurrentIndex(0)
            self.src_combo.blockSignals(False)
            self.src_label.setText("TRANSLATION MODE")
            self.swap_btn.setEnabled(True)
            self.swap_btn.show()
            self.tgt_combo.show()
            self.tgt_label.show()
            if hasattr(self, "scenario_box_widget"):
                self.scenario_box_widget.hide()
            self.update_mode_button_styles()
            self.on_lang_combo_changed()
            self.status_label.setText("Live Translation Mode: Bidirectional speech translation between English & Japanese.")
        else:
            self.manager.pipeline.app_mode = "coach"
            self.src_combo.blockSignals(True)
            self.src_combo.clear()
            self.src_combo.addItem("🇯🇵 Practice Japanese (AI Partner replies in Japanese & coaches grammar)", "ja")
            self.src_combo.addItem("🇺🇸 Practice English (AI Partner replies in English & coaches grammar)", "en")
            self.src_combo.setCurrentIndex(0)
            self.src_combo.blockSignals(False)
            self.src_label.setText("PRACTICE & COACHING TARGET LANGUAGE")
            self.swap_btn.setText("🎓 COACH ACTIVE")
            self.swap_btn.setEnabled(False)
            self.tgt_combo.hide()
            self.tgt_label.hide()
            if hasattr(self, "scenario_box_widget"):
                self.scenario_box_widget.show()
                # Apply current scenario to coach engine
                if hasattr(self.manager.pipeline, "coach"):
                    self.manager.pipeline.coach.set_scenario(self.scenario_combo.currentData())
            practice_lang = "ja"
            self.manager.pipeline.practice_lang = practice_lang
            self.manager.pipeline.set_languages(practice_lang, practice_lang)
            self.update_mode_button_styles()
            self.test_en_btn.setText("TEST COACH (JA)")
            sc_text = self.scenario_combo.currentText()
            self.status_label.setText(f"AI Language Coach Mode: Active scenario [{sc_text}]. Speak naturally for instant coaching & conversational reply.")

    def on_scenario_changed(self):
        sc_id = self.scenario_combo.currentData()
        if hasattr(self.manager.pipeline, "coach"):
            self.manager.pipeline.coach.set_scenario(sc_id)
            sc_text = self.scenario_combo.currentText()
            self.status_label.setText(f"AI Language Coach: Switched scenario to [{sc_text}].")

    def on_swap_clicked(self):
        if getattr(self.manager.pipeline, "app_mode", "translate") == "coach":
            cur_idx = self.src_combo.currentIndex()
            new_idx = 1 if cur_idx == 0 else 0
            self.src_combo.setCurrentIndex(new_idx)
            return

        src = self.src_combo.currentData()
        if src == "auto":
            self.src_combo.setCurrentIndex(self.src_combo.findData("en"))
        elif src == "en":
            self.src_combo.setCurrentIndex(self.src_combo.findData("ja"))
        else:
            self.src_combo.setCurrentIndex(self.src_combo.findData("auto"))

    def on_lang_combo_changed(self):
        src = self.src_combo.currentData()
        if getattr(self.manager.pipeline, "app_mode", "translate") == "coach":
            practice_lang = src if src in ("ja", "en") else "ja"
            self.manager.pipeline.practice_lang = practice_lang
            self.manager.pipeline.set_languages(practice_lang, practice_lang)
            self.test_en_btn.setText(f"TEST COACH ({practice_lang.upper()})")
            lang_name = "Japanese" if practice_lang == "ja" else "English"
            self.status_label.setText(f"AI Coach ({lang_name} Practice): Speak naturally to receive conversational replies and grammar tips.")
            return

        if src == "auto":
            self.tgt_combo.blockSignals(True)
            self.tgt_combo.setCurrentIndex(self.tgt_combo.findData("auto"))
            self.tgt_combo.setEnabled(False)
            self.tgt_combo.blockSignals(False)
            self.swap_btn.setText("✨ AUTO ACTIVE")
            self.manager.set_active_speaker_lang("auto")
            self.status_label.setText("Mode: Auto-Detect (EN ⇄ JA Vice Versa) — Speak in either language naturally!")
            self.test_en_btn.setText("TEST SAMPLE (AUTO)")
        elif src == "en":
            self.tgt_combo.blockSignals(True)
            self.tgt_combo.setEnabled(True)
            self.tgt_combo.setCurrentIndex(self.tgt_combo.findData("ja"))
            self.tgt_combo.blockSignals(False)
            self.swap_btn.setText("⇄  SWAP (EN ➔ JA)")
            self.manager.pipeline.set_languages("en", "ja")
            self.status_label.setText("Active direction: EN ➔ JA (English to Japanese)")
            self.test_en_btn.setText("TEST SAMPLE (EN ➔ JA)")
        elif src == "ja":
            self.tgt_combo.blockSignals(True)
            self.tgt_combo.setEnabled(True)
            self.tgt_combo.setCurrentIndex(self.tgt_combo.findData("en"))
            self.tgt_combo.blockSignals(False)
            self.swap_btn.setText("⇄  SWAP (JA ➔ EN)")
            self.manager.pipeline.set_languages("ja", "en")
            self.status_label.setText("Active direction: JA ➔ EN (Japanese to English)")
            self.test_en_btn.setText("TEST SAMPLE (JA ➔ EN)")

    def open_analytics(self):
        """Opens the Fluency & Learning Analytics dashboard dialog."""
        from ui.analytics_dialog import AnalyticsDialog
        turns = self.manager.history if hasattr(self, "manager") else []
        dialog = AnalyticsDialog(turns, parent=self)
        dialog.exec()

    def open_flashcards(self):
        """Opens the Practice Deck & Flashcard Review dialog."""
        from ui.flashcard_dialog import FlashcardDialog
        tts = getattr(self.manager.pipeline, "tts", None) if hasattr(self, "manager") else None
        dialog = FlashcardDialog(tts_engine=tts, parent=self)
        dialog.exec()

    def open_settings(self):
        dialog = SettingsDialog(self.config_path, self)
        dialog.settings_saved.connect(self.on_settings_updated)
        dialog.exec()

    def on_settings_updated(self, new_config):
        self.config = new_config
        audio_cfg = new_config.get("audio", {})
        self.manager.pipeline.playback.volume = audio_cfg.get("playback_volume", 1.0)
        self.manager.pipeline.auto_playback = audio_cfg.get("auto_playback", True)
        self.manager.pipeline.playback.device_index = audio_cfg.get("output_device_index")
        self.manager.pipeline.capture.device_index = audio_cfg.get("input_device_index")

        coach_cfg = new_config.get("coach", {})
        if hasattr(self.manager.pipeline, "coach"):
            self.manager.pipeline.coach.provider = coach_cfg.get("provider", "builtin")
            self.manager.pipeline.coach.ollama_model = coach_cfg.get("ollama_model", "qwen2.5:0.5b")
            self.manager.pipeline.coach.ollama_url = coach_cfg.get("ollama_url", "http://localhost:11434")

        self.status_label.setText("Settings applied.")

    def replay_audio(self):
        if self.last_audio_bytes:
            self.manager.pipeline.playback.play_raw_bytes(
                self.last_audio_bytes,
                sample_rate=self.last_sample_rate
            )
            self.status_label.setText("Replaying translated speech aloud...")

    def on_conversation_replay(self, text: str, target_lang: str):
        """Synthesize and play audio for any past conversation card."""
        try:
            self.status_label.setText(f"Replaying voice ({target_lang.upper()}): {text[:30]}...")
            pcm, sr, _ = self.manager.pipeline.tts.synthesize(text, target_lang)
            self.manager.pipeline.playback.play_raw_bytes(pcm, sample_rate=sr)
        except Exception as e:
            logger.error(f"Error replaying conversation audio: {e}")
            self.status_label.setText(f"Replay error: {e}")

    def export_transcript(self):
        """Save formatted conversation history to a text file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Conversation Transcript", "transcript.txt", "Text Files (*.txt);;All Files (*)"
        )
        if filepath:
            try:
                history = self.manager.get_history_as_dicts()
                self.conversation_view.export_to_text(filepath, history)
                self.status_label.setText(f"Transcript exported successfully to {os.path.basename(filepath)}")
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Could not export transcript: {e}")

    def clear_conversation_history(self):
        """Reset conversation manager and clear all cards from view."""
        self.manager.clear_history()
        self.conversation_view.clear()
        self.orig_text.clear()
        self.trans_text.clear()
        self.status_label.setText("Conversation history cleared.")

    def run_quick_test(self):
        """Simulate an instant spoken utterance to verify audio, STT, MT, and TTS or AI Coach."""
        self.status_label.setText("Generating test spoken utterance...")
        if getattr(self.manager.pipeline, "app_mode", "translate") == "coach":
            practice_lang = getattr(self.manager.pipeline, "practice_lang", "ja")
            if practice_lang == "ja":
                test_phrase = "どこ行きますか？"
            else:
                test_phrase = "where is station?"
            test_lang = practice_lang
        else:
            src = self.manager.pipeline.source_lang
            if src in ("auto", None):
                if not hasattr(self, "_test_counter"):
                    self._test_counter = 0
                self._test_counter += 1
                test_lang = "ja" if self._test_counter % 2 == 0 else "en"
            else:
                test_lang = src

            test_phrase = "Hello, where is the nearest station?" if test_lang == "en" else "こんにちは、駅はどこですか？"

        # Generate audio using local TTS
        tts = TTSEngine("models_cache/tts")
        pcm, sr, _ = tts.synthesize(test_phrase, test_lang)
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if sr != 16000:
            import scipy.signal
            audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr)).astype(np.float32)

        # Process through pipeline
        self.manager.pipeline.process_utterance(audio)

    # --- Worker Signal Slots ---
    @Slot(float)
    def on_audio_level(self, level: float):
        """Update live reactive soundwave equalizer."""
        self.visualizer.set_level(level)

    @Slot()
    def on_speech_detected(self):
        self.vad_badge.setText("SPEAKING...")
        self.vad_badge.setStyleSheet("background-color: #92400e; color: #fbbf24; font-weight: bold; border-radius: 6px;")
        self.status_label.setText("Voice detected! Listening to speech...")
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.set_active_state(True, is_speaking=True)

    @Slot(str, str, float)
    def on_transcription_ready(self, text: str, lang: str, lat: float):
        self.orig_text.setPlainText(text)
        self.stt_lat_label.setText(f"STT: {lat:.0f} ms")
        self.vad_badge.setText("TRANSLATING...")
        self.vad_badge.setStyleSheet("background-color: #1e3a8a; color: #60a5fa; font-weight: bold; border-radius: 6px;")
        self.status_label.setText("Transcribed speech. Translating text...")
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.update_transcription(text, lang)

    @Slot(str, float)
    def on_translation_ready(self, text: str, lat: float):
        self.trans_text.setPlainText(text)
        self.mt_lat_label.setText(f"MT: {lat:.0f} ms")
        self.status_label.setText("Translated. Synthesizing voice audio...")
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.update_translation(text)

    @Slot(bytes, int, float)
    def on_synthesis_ready(self, audio: bytes, sr: int, lat: float):
        self.last_audio_bytes = audio
        self.last_sample_rate = sr
        self.replay_btn.setEnabled(True)
        self.tts_lat_label.setText(f"TTS: {lat:.0f} ms")
        self.status_label.setText("Playing translated speech aloud through speakers...")

    @Slot(dict)
    def on_pipeline_completed(self, metrics: dict):
        total_lat = metrics.get("total_e2e_latency_ms", 0)
        self.total_lat_label.setText(f"Total Latency: {total_lat:.0f} ms")
        
        target_met = total_lat < 1500
        target_color = "#34d399" if target_met else "#f59e0b"
        self.target_badge.setText("Target: <1.5s (PASSED)" if target_met else "Target: <1.5s")
        self.target_badge.setStyleSheet(f"color: {target_color}; font-weight: bold;")

        if self.manager.history:
            turn_dict = self.manager.get_history_as_dicts()[-1]
            self.conversation_view.add_turn(turn_dict)

        self.vad_badge.setText("MIC LISTENING")
        self.vad_badge.setStyleSheet("background-color: #064e3b; color: #34d399; font-weight: bold; border-radius: 6px;")
        if metrics.get("is_coach_turn"):
            self.status_label.setText("AI Coach feedback ready. Spoken reply played aloud.")
        else:
            self.status_label.setText("Translation complete. Ready for next utterance.")

        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.set_active_state(True, is_speaking=False)

    @Slot(str)
    def on_error_occurred(self, err_msg: str):
        self.status_label.setText(f"Error: {err_msg}")
        self.status_label.setStyleSheet("color: #f87171; font-weight: bold;")

    def closeEvent(self, event):
        if self.overlay_window:
            self.overlay_window.close()
        self.manager.pipeline.stop_listening()
        self.manager.pipeline.playback.stop()
        event.accept()
