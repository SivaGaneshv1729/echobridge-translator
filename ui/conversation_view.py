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


class CoachingBubble(QFrame):
    """Modern conversational coaching card displaying spoken speech, grammar corrections, and AI assistant reply."""
    replay_requested = Signal(str, str) # (assistant_reply_text, practice_lang)

    def __init__(self, turn_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.turn_data = turn_data
        self.setObjectName("coachingBubble")

        practice_lang = turn_data.get("target_lang", "ja")
        is_natural = turn_data.get("is_natural", True)
        politeness = turn_data.get("politeness_level", "Polite")
        correction = turn_data.get("suggested_correction", "").strip()
        grammar_notes = turn_data.get("grammar_notes", "").strip()
        vocab_tips = turn_data.get("vocabulary_tips", [])
        original_text = turn_data.get("original_text", "").strip()
        reply_text = turn_data.get("translated_text", "").strip()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header Row: AI Coach Avatar, Practice Lang, Politeness, Fluency Pill, Latency
        header = QHBoxLayout()
        header.setSpacing(8)

        coach_badge = QLabel("🎓 AI Language Coach")
        coach_badge.setStyleSheet("""
            background-color: #312e81;
            color: #c7d2fe;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 800;
            border: 1px solid #4f46e5;
        """)

        lang_label = "🇯🇵 JA Practice" if practice_lang == "ja" else "🇺🇸 EN Practice"
        lang_badge = QLabel(lang_label)
        lang_badge.setStyleSheet("color: #a5b4fc; font-size: 11px; font-weight: bold;")

        polite_badge = QLabel(politeness)
        polite_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 700;
            border: 1px solid #334155;
        """)

        if is_natural:
            fluency_badge = QLabel("✓ Natural & Fluent")
            fluency_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                padding: 3px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 800;
                border: 1px solid #059669;
            """)
        else:
            fluency_badge = QLabel("⚡ Grammar Tip")
            fluency_badge.setStyleSheet("""
                background-color: #451a03;
                color: #fbbf24;
                padding: 3px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 800;
                border: 1px solid #d97706;
            """)

        time_str = turn_data.get("time_str", time.strftime("%H:%M:%S"))
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #64748b; font-size: 11px;")

        total_lat = turn_data.get("total_latency_ms", 0)
        lat_badge = QLabel(f"⚡ {total_lat:.0f} ms")
        lat_badge.setStyleSheet("""
            background-color: #111827;
            color: #38bdf8;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 800;
            border: 1px solid #1f2937;
        """)

        scenario_id = turn_data.get("scenario_id", "free_talk")
        scenario_labels = {
            "cafe": "🍵 Cafe & Dining",
            "transit": "🚅 Transit & Navigation",
            "hotel": "🏨 Hotel & Travel",
            "business": "💼 Business & Interview",
            "free_talk": "🗣️ Daily Talk"
        }
        sc_name = scenario_labels.get(scenario_id, "🗣️ Daily Talk")
        sc_badge = QLabel(sc_name)
        sc_badge.setStyleSheet("""
            background-color: #1e1b4b;
            color: #c7d2fe;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
            border: 1px solid #4338ca;
        """)

        header.addWidget(coach_badge)
        header.addWidget(lang_badge)
        header.addWidget(sc_badge)
        header.addWidget(polite_badge)
        header.addWidget(fluency_badge)
        header.addWidget(time_label)
        header.addStretch()
        header.addWidget(lat_badge)
        layout.addLayout(header)

        # 1. User Spoken Sentence
        orig_box = QVBoxLayout()
        orig_box.setSpacing(2)
        orig_title = QLabel("WHAT YOU SAID")
        orig_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
        
        self.orig_label = QLabel(original_text)
        self.orig_label.setWordWrap(True)
        self.orig_label.setStyleSheet("color: #f1f5f9; font-size: 15px; font-weight: 500; line-height: 1.4;")
        self.orig_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        orig_box.addWidget(orig_title)
        orig_box.addWidget(self.orig_label)
        layout.addLayout(orig_box)

        # 2. Suggested Improvement / Correction Card (if not natural or correction differs)
        if correction and (not is_natural or correction != original_text):
            corr_frame = QFrame()
            corr_frame.setObjectName("correctionBox")
            corr_layout = QVBoxLayout(corr_frame)
            corr_layout.setContentsMargins(12, 10, 12, 10)
            corr_layout.setSpacing(4)

            corr_title = QLabel("✨ MORE NATURAL PHRASING:")
            corr_title.setStyleSheet("color: #a5b4fc; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
            
            corr_label = QLabel(correction)
            corr_label.setWordWrap(True)
            corr_label.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 700; line-height: 1.4;")
            corr_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            corr_layout.addWidget(corr_title)
            corr_layout.addWidget(corr_label)
            corr_frame.setStyleSheet("""
                QFrame#correctionBox {
                    background-color: #1e1b4b;
                    border: 1px solid #4338ca;
                    border-radius: 8px;
                }
            """)
            layout.addWidget(corr_frame)

        # 3. Coach's Grammar Notes & Explanations
        if grammar_notes:
            notes_frame = QFrame()
            notes_frame.setObjectName("notesBox")
            notes_layout = QVBoxLayout(notes_frame)
            notes_layout.setContentsMargins(12, 10, 12, 10)
            notes_layout.setSpacing(4)

            notes_title = QLabel("💡 COACH'S EXPLANATION & GRAMMAR TIP:")
            notes_title.setStyleSheet("color: #fbbf24; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")

            notes_label = QLabel(grammar_notes)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 500; line-height: 1.4;")
            notes_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            notes_layout.addWidget(notes_title)
            notes_layout.addWidget(notes_label)
            notes_frame.setStyleSheet("""
                QFrame#notesBox {
                    background-color: #111827;
                    border: 1px solid #374151;
                    border-radius: 8px;
                }
            """)
            layout.addWidget(notes_frame)

        # 4. Spoken Conversational Reply (AI Partner speaking aloud)
        if reply_text:
            reply_frame = QFrame()
            reply_frame.setObjectName("replyBox")
            reply_layout = QVBoxLayout(reply_frame)
            reply_layout.setContentsMargins(12, 10, 12, 10)
            reply_layout.setSpacing(4)

            reply_title = QLabel("🤖 COACH'S CONVERSATIONAL REPLY (Spoken Aloud):")
            reply_title.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")

            self.reply_label = QLabel(reply_text)
            self.reply_label.setWordWrap(True)
            self.reply_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 700; line-height: 1.4;")
            self.reply_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            reply_layout.addWidget(reply_title)
            reply_layout.addWidget(self.reply_label)
            reply_frame.setStyleSheet("""
                QFrame#replyBox {
                    background-color: #06221d;
                    border: 1px solid #059669;
                    border-radius: 8px;
                }
            """)
            layout.addWidget(reply_frame)

        # 5. Vocabulary Tips (if available)
        if vocab_tips:
            tips_row = QHBoxLayout()
            tips_row.setSpacing(6)
            tips_label = QLabel("TIPS:")
            tips_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800;")
            tips_row.addWidget(tips_label)
            for tip in vocab_tips:
                pill = QLabel(f"🏷️ {tip}")
                pill.setStyleSheet("""
                    background-color: #1e293b;
                    color: #cbd5e1;
                    padding: 2px 8px;
                    border-radius: 8px;
                    font-size: 10px;
                    border: 1px solid #334155;
                """)
                tips_row.addWidget(pill)
            tips_row.addStretch()
            layout.addLayout(tips_row)

        # Footer Action Toolbar: Replay Voice & Copy Feedback
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.replay_btn = QPushButton("▶ Replay Voice")
        self.replay_btn.setObjectName("coachReplayBtn")
        self.replay_btn.setFixedHeight(28)
        self.replay_btn.clicked.connect(self._on_replay_clicked)

        self.copy_btn = QPushButton("📋 Copy Feedback")
        self.copy_btn.setObjectName("coachActionBtn")
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.clicked.connect(self._on_copy_clicked)

        self.deck_btn = QPushButton("⭐ Save to Deck")
        self.deck_btn.setObjectName("coachActionBtn")
        self.deck_btn.setFixedHeight(28)
        self.deck_btn.clicked.connect(self._on_save_to_deck)

        footer.addWidget(self.replay_btn)
        footer.addWidget(self.copy_btn)
        footer.addWidget(self.deck_btn)
        footer.addStretch()

        stt_ms = turn_data.get("stt_latency_ms", 0)
        mt_ms = turn_data.get("mt_latency_ms", 0)
        tts_ms = turn_data.get("tts_latency_ms", 0)
        telemetry_label = QLabel(f"STT: {stt_ms:.0f}ms | Coach: {mt_ms:.0f}ms | TTS: {tts_ms:.0f}ms")
        telemetry_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        footer.addWidget(telemetry_label)

        layout.addLayout(footer)

        self.setStyleSheet("""
            QFrame#coachingBubble {
                background-color: #0f111a;
                border: 1px solid #4f46e5;
                border-radius: 12px;
            }
            QPushButton#coachReplayBtn {
                background-color: #1e293b;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#coachReplayBtn:hover {
                background-color: #059669;
                color: #ffffff;
            }
            QPushButton#coachActionBtn {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#coachActionBtn:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)

    def _on_replay_clicked(self):
        text = self.turn_data.get("translated_text", "")
        practice_lang = self.turn_data.get("target_lang", "ja")
        self.replay_requested.emit(text, practice_lang)

    def _on_copy_clicked(self):
        clipboard = QApplication.clipboard()
        orig = self.turn_data.get("original_text", "")
        corr = self.turn_data.get("suggested_correction", "")
        notes = self.turn_data.get("grammar_notes", "")
        reply = self.turn_data.get("translated_text", "")
        polite = self.turn_data.get("politeness_level", "")
        text = f"[EchoBridge AI Language Coach]\nStudent Spoke: {orig}\nSuggested Phrasing: {corr}\nPoliteness: {polite}\nGrammar Notes: {notes}\nSpoken Reply: {reply}"
        clipboard.setText(text)
        self.copy_btn.setText("✓ Copied!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋 Copy Feedback"))

    def _on_save_to_deck(self):
        from pipeline.deck import PracticeDeck
        deck = PracticeDeck()
        deck.add_card(
            original_text=self.turn_data.get("original_text", ""),
            suggested_correction=self.turn_data.get("suggested_correction", "") or self.turn_data.get("original_text", ""),
            grammar_notes=self.turn_data.get("grammar_notes", ""),
            vocabulary_tips=self.turn_data.get("vocabulary_tips", []),
            politeness_level=self.turn_data.get("politeness_level", ""),
            scenario_id=self.turn_data.get("scenario_id", "free_talk")
        )
        self.deck_btn.setText("✓ Saved to Deck!")
        self.deck_btn.setEnabled(False)


class EmptyStateHero(QFrame):
    """Welcome card shown when conversation history is empty."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyHero")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("🎙️ ⇄ 🌐 🎓")
        icon.setStyleSheet("font-size: 36px; margin-bottom: 4px;")
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel("Ready for Real-Time Translation & Language Coaching")
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "Speak naturally in English or Japanese.\n"
            "EchoBridge instantly translates two-way speech offline, or acts as your interactive AI Language Coach\n"
            "explaining grammar improvements and replying aloud in natural conversation."
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
        """Append a new conversation turn bubble (translation or coaching)."""
        if not self.empty_hero.isHidden():
            self.empty_hero.hide()

        if turn_data.get("is_coach_turn"):
            bubble = CoachingBubble(turn_data)
        else:
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
            f.write("   EchoBridge Conversation & Language Coaching Transcript\n")
            f.write(f"   Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            for t in history:
                src = t.get("speaker_lang", "").upper()
                tgt = t.get("target_lang", "").upper()
                lat = t.get("total_latency_ms", 0)
                if t.get("is_coach_turn"):
                    f.write(f"[{t.get('time_str')}] [AI COACH - {tgt} PRACTICE] (Latency: {lat:.0f}ms)\n")
                    f.write(f"  Student Said:       {t.get('original_text')}\n")
                    if not t.get("is_natural", True) or t.get("suggested_correction"):
                        f.write(f"  Suggested Phrasing: {t.get('suggested_correction')}\n")
                    if t.get("grammar_notes"):
                        f.write(f"  Grammar Coaching:   {t.get('grammar_notes')}\n")
                    if t.get("politeness_level"):
                        f.write(f"  Politeness Level:   {t.get('politeness_level')}\n")
                    f.write(f"  Coach Spoken Reply: {t.get('translated_text')}\n\n")
                else:
                    f.write(f"[{t.get('time_str')}] [{src} ➔ {tgt}] (Total: {lat:.0f}ms)\n")
                    f.write(f"  Spoken:     {t.get('original_text')}\n")
                    f.write(f"  Translated: {t.get('translated_text')}\n\n")

