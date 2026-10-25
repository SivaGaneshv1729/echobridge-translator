"""Modern Conversation Stream View for EchoBridge with Glassmorphic Bubbles and Inline Controls."""
import time
import json
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton, QApplication,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

class ChatBubble(QFrame):
    """Modern conversational card displaying original speech, translation, and interactive controls."""
    replay_requested = Signal(str, str) # (translated_text, target_lang)

    def __init__(self, turn_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.turn_data = turn_data
        self.setObjectName("chatBubble")

        is_english_speaker = turn_data.get("speaker_lang") == "en"
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header Row: Speaker Avatar Badge, Direction, Timestamp, and Latency Pill
        header = QHBoxLayout()
        header.setSpacing(10)

        if is_english_speaker:
            speaker_badge = QLabel("🇺🇸 English Speaker")
            speaker_badge.setStyleSheet("""
                background-color: #0c4a6e;
                color: #38bdf8;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 800;
                border: 1px solid #0284c7;
            """)
            dir_tag = QLabel("EN ➔ JA")
        else:
            speaker_badge = QLabel("🇯🇵 Japanese Speaker")
            speaker_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 800;
                border: 1px solid #059669;
            """)
            dir_tag = QLabel("JA ➔ EN")

        dir_tag.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        
        time_str = turn_data.get("time_str", time.strftime("%H:%M:%S"))
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #64748b; font-size: 11px;")

        total_lat = turn_data.get("total_latency_ms", 0)
        lat_color = "#34d399" if total_lat < 1500 else "#f59e0b"
        lat_badge = QLabel(f"⚡ {total_lat:.0f} ms")
        lat_badge.setStyleSheet(f"""
            background-color: #111827;
            color: {lat_color};
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 800;
            border: 1px solid #1f2937;
        """)

        header.addWidget(speaker_badge)
        header.addWidget(dir_tag)
        header.addWidget(time_label)
        header.addStretch()
        header.addWidget(lat_badge)
        layout.addLayout(header)

        # Spoken Original Text
        orig_box = QVBoxLayout()
        orig_box.setSpacing(2)
        orig_title = QLabel("ORIGINAL SPOKEN")
        orig_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
        
        self.orig_label = QLabel(turn_data.get("original_text", ""))
        self.orig_label.setWordWrap(True)
        self.orig_label.setStyleSheet("color: #e2e8f0; font-size: 15px; font-weight: 500; line-height: 1.4;")
        self.orig_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        orig_box.addWidget(orig_title)
        orig_box.addWidget(self.orig_label)
        layout.addLayout(orig_box)

        # Subtle separator
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        layout.addWidget(divider)

        # Translated Output Text
        trans_box = QVBoxLayout()
        trans_box.setSpacing(2)
        trans_title = QLabel("TRANSLATED OUTPUT")
        trans_title_color = "#38bdf8" if is_english_speaker else "#34d399"
        trans_title.setStyleSheet(f"color: {trans_title_color}; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")

        self.trans_label = QLabel(turn_data.get("translated_text", ""))
        self.trans_label.setWordWrap(True)
        self.trans_label.setStyleSheet(f"color: #ffffff; font-size: 17px; font-weight: 700; line-height: 1.4;")
        self.trans_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        trans_box.addWidget(trans_title)
        trans_box.addWidget(self.trans_label)
        layout.addLayout(trans_box)

        # Footer Action Toolbar: Replay Voice & Copy Buttons
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.replay_btn = QPushButton("▶ Replay Voice")
        self.replay_btn.setObjectName("replayBtn")
        self.replay_btn.setFixedHeight(28)
        self.replay_btn.clicked.connect(self._on_replay_clicked)

        self.copy_btn = QPushButton("📋 Copy Translation")
        self.copy_btn.setObjectName("actionBtn")
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.clicked.connect(self._on_copy_clicked)

        footer.addWidget(self.replay_btn)
        footer.addWidget(self.copy_btn)
        footer.addStretch()

        # Telemetry breakdown pill
        stt_ms = turn_data.get("stt_latency_ms", 0)
        mt_ms = turn_data.get("mt_latency_ms", 0)
        tts_ms = turn_data.get("tts_latency_ms", 0)
        telemetry_label = QLabel(f"STT: {stt_ms:.0f}ms | MT: {mt_ms:.0f}ms | TTS: {tts_ms:.0f}ms")
        telemetry_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        footer.addWidget(telemetry_label)

        layout.addLayout(footer)

        # Card Border Styling
        card_border = "#0284c7" if is_english_speaker else "#059669"
        card_bg = "#0f172a" if is_english_speaker else "#06221d"
        self.setStyleSheet(f"""
            QFrame#chatBubble {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QPushButton#replayBtn {{
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#replayBtn:hover {{
                background-color: #0284c7;
                color: #ffffff;
            }}
            QPushButton#actionBtn {{
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#actionBtn:hover {{
                background-color: #334155;
                color: #ffffff;
            }}
        """)

    def _on_replay_clicked(self):
        text = self.turn_data.get("translated_text", "")
        target_lang = self.turn_data.get("target_lang", "ja")
        self.replay_requested.emit(text, target_lang)

    def _on_copy_clicked(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.turn_data.get("translated_text", ""))
        self.copy_btn.setText("✓ Copied!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋 Copy Translation"))


class EmptyStateHero(QFrame):
    """Welcome card shown when conversation history is empty."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyHero")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("🎙️ ⇄ 🌐")
        icon.setStyleSheet("font-size: 36px; margin-bottom: 4px;")
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel("Ready for Real-Time Speech Translation")
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "Speak naturally in English or Japanese.\n"
            "EchoBridge automatically detects who is speaking, translates instantly offline,\n"
            "and speaks the translation aloud through your speakers."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 13px; line-height: 1.5;")
        desc.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(desc)

        self.setStyleSheet("""
            QFrame#emptyHero {
                background-color: #111827;
                border: 1px dashed #334155;
                border-radius: 14px;
                margin: 20px 10px;
            }
        """)


class ConversationView(QWidget):
    """Unified conversational stream displaying live speech bubbles, telemetry, and export."""
    replay_requested = Signal(str, str) # (text, lang)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(6, 6, 6, 6)
        self.container_layout.setSpacing(12)

        self.empty_hero = EmptyStateHero()
        self.container_layout.addWidget(self.empty_hero)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

    def add_turn(self, turn_data: Dict[str, Any]):
        """Append a new conversation turn bubble."""
        if not self.empty_hero.isHidden():
            self.empty_hero.hide()

        bubble = ChatBubble(turn_data)
        bubble.replay_requested.connect(self.replay_requested.emit)
        
        # Insert before stretch
        self.container_layout.insertWidget(self.container_layout.count() - 1, bubble)
        
        # Smooth scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def clear(self):
        """Clear all conversation bubbles and restore empty hero card."""
        while self.container_layout.count() > 2:
            item = self.container_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self.empty_hero.show()

    def export_to_text(self, filepath: str, history: list):
        """Export conversation history to plain text."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("   EchoBridge Conversation Transcript\n")
            f.write(f"   Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            for t in history:
                src = t.get("speaker_lang", "").upper()
                tgt = t.get("target_lang", "").upper()
                f.write(f"[{t.get('time_str')}] [{src} ➔ {tgt}] (Total: {t.get('total_latency_ms', 0):.0f}ms)\n")
                f.write(f"  Spoken:     {t.get('original_text')}\n")
                f.write(f"  Translated: {t.get('translated_text')}\n\n")
