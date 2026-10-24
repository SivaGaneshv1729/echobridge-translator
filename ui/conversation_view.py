"""Conversation View widget displaying turn-by-turn chat history with latency badges."""
import time
from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

class ChatBubble(QFrame):
    """Custom styled chat bubble displaying a conversation turn."""
    replay_requested = Signal(str, str) # (text, lang)

    def __init__(self, turn_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.turn_data = turn_data
        self.setObjectName("chatBubble")

        is_a_to_b = turn_data.get("speaker_lang") == "en"
        align_right = not is_a_to_b

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header: Language tag + timestamp + latency badge
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        src_flag = "🇺🇸 English" if turn_data.get("speaker_lang") == "en" else "🇯🇵 日本語"
        tgt_flag = "🇯🇵 日本語" if turn_data.get("target_lang") == "ja" else "🇺🇸 English"
        
        dir_label = QLabel(f"<b>{src_flag}</b> ➔ <b>{tgt_flag}</b>")
        dir_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        
        time_str = turn_data.get("time_str", time.strftime("%H:%M:%S"))
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #64748b; font-size: 11px;")

        lat_total = turn_data.get("total_latency_ms", 0)
        lat_badge = QLabel(f"⚡ {lat_total:.0f} ms")
        lat_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)

        header_layout.addWidget(dir_label)
        header_layout.addWidget(time_label)
        header_layout.addStretch()
        header_layout.addWidget(lat_badge)
        layout.addLayout(header_layout)

        # Original text
        orig_label = QLabel(turn_data.get("original_text", ""))
        orig_label.setWordWrap(True)
        orig_label.setStyleSheet("color: #cbd5e1; font-size: 14px; margin-top: 2px;")
        layout.addWidget(orig_label)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #334155; max-height: 1px;")
        layout.addWidget(divider)

        # Translated text
        trans_label = QLabel(turn_data.get("translated_text", ""))
        trans_label.setWordWrap(True)
        trans_label.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: bold; margin-top: 2px;")
        layout.addWidget(trans_label)

        # Styling bubble frame based on speaker
        border_color = "#3b82f6" if is_a_to_b else "#10b981"
        bg_color = "#0f172a" if is_a_to_b else "#062822"
        self.setStyleSheet(f"""
            QFrame#chatBubble {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
        """)


class ConversationView(QWidget):
    """Scrollable conversation history list."""
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
        self.container_layout.setContentsMargins(8, 8, 8, 8)
        self.container_layout.setSpacing(10)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

    def add_turn(self, turn_data: Dict[str, Any]):
        """Append a new conversation turn bubble."""
        bubble = ChatBubble(turn_data)
        # Insert before stretch
        self.container_layout.insertWidget(self.container_layout.count() - 1, bubble)
        # Scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def clear(self):
        """Clear all conversation bubbles."""
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
