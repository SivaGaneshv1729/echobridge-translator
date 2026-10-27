"""Interactive Practice Flashcard & Vocabulary Deck Dialog for EchoBridge Desktop."""
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QWidget, QStackedWidget, QProgressBar, QMessageBox
)

from pipeline.deck import PracticeDeck, DeckCard
from engines.text_to_speech import TTSEngine

class FlashcardDialog(QDialog):
    """Interactive Flip-Card Language Learning & Spaced Practice Dialog."""

    def __init__(self, tts_engine: Optional[TTSEngine] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EchoBridge - Practice Flashcards & Vocabulary Deck")
        self.setMinimumSize(720, 560)
        self.setStyleSheet("background-color: #0b0f19; color: #f1f5f9; font-family: 'Segoe UI', sans-serif;")

        self.deck = PracticeDeck()
        self.tts = tts_engine
        self.current_index = 0
        self.filter_mode = "all"  # "all", "unmastered", "mastered"
        self.active_cards: List[DeckCard] = []

        self._update_active_cards()
        self._init_ui()
        self._display_current_card()

    def _update_active_cards(self):
        if self.filter_mode == "unmastered":
            self.active_cards = [c for c in self.deck.cards if not c.mastered]
        elif self.filter_mode == "mastered":
            self.active_cards = [c for c in self.deck.cards if c.mastered]
        else:
            self.active_cards = list(self.deck.cards)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header
        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("🎴 Practice Flashcards & Vocabulary Deck")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #ffffff;")
        self.progress_subtitle = QLabel("Card 0 of 0 • 0 Mastered")
        self.progress_subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(title)
        title_box.addWidget(self.progress_subtitle)

        # Filter Tabs
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.btn_filter_all = QPushButton("All Cards")
        self.btn_filter_unmastered = QPushButton("Needs Practice")
        self.btn_filter_mastered = QPushButton("Mastered")
        
        for btn, mode in [
            (self.btn_filter_all, "all"),
            (self.btn_filter_unmastered, "unmastered"),
            (self.btn_filter_mastered, "mastered")
        ]:
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, m=mode: self._set_filter(m))
            filter_row.addWidget(btn)

        top_row.addLayout(title_box)
        top_row.addStretch()
        top_row.addLayout(filter_row)
        main_layout.addLayout(top_row)

        # Progress bar
        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(6)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #6366f1);
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self.prog_bar)

        # Main Flip Card Area (StackedWidget: 0 = Front, 1 = Back)
        self.card_stack = QStackedWidget()
        self.card_stack.setMinimumHeight(320)

        # --- FRONT CARD ---
        self.front_frame = QFrame()
        self.front_frame.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 2px solid #312e81;
                border-radius: 16px;
                padding: 24px;
            }
            QFrame:hover {
                border: 2px solid #4f46e5;
            }
        """)
        f_layout = QVBoxLayout(self.front_frame)
        f_layout.setSpacing(12)

        f_header = QHBoxLayout()
        self.f_scenario_badge = QLabel("🗣️ Daily Talk")
        self.f_scenario_badge.setStyleSheet("""
            background-color: #1e1b4b;
            color: #c7d2fe;
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 700;
            border: 1px solid #4338ca;
        """)
        self.f_status_badge = QLabel("🌱 NEEDS PRACTICE")
        self.f_status_badge.setStyleSheet("""
            background-color: #1f2937;
            color: #94a3b8;
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 800;
        """)
        f_header.addWidget(self.f_scenario_badge)
        f_header.addWidget(self.f_status_badge)
        f_header.addStretch()
        f_layout.addLayout(f_header)

        f_layout.addStretch()
        f_prompt_lbl = QLabel("PROMPT / WHAT YOU SAID")
        f_prompt_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        self.f_text = QLabel("アイスコーヒーをひとつ、お願い。")
        self.f_text.setWordWrap(True)
        self.f_text.setAlignment(Qt.AlignCenter)
        self.f_text.setStyleSheet("color: #f1f5f9; font-size: 22px; font-weight: 700; line-height: 1.4;")
        f_layout.addWidget(f_prompt_lbl, alignment=Qt.AlignCenter)
        f_layout.addWidget(self.f_text)
        f_layout.addStretch()

        flip_btn = QPushButton("💡 Tap to Reveal Correction & Grammar Tip")
        flip_btn.setFixedHeight(40)
        flip_btn.setCursor(Qt.PointingHandCursor)
        flip_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 10px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
        """)
        flip_btn.clicked.connect(lambda: self.card_stack.setCurrentIndex(1))
        f_layout.addWidget(flip_btn)

        # --- BACK CARD ---
        self.back_frame = QFrame()
        self.back_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 2px solid #059669;
                border-radius: 16px;
                padding: 24px;
            }
        """)
        b_layout = QVBoxLayout(self.back_frame)
        b_layout.setSpacing(12)

        b_header = QHBoxLayout()
        self.b_polite_badge = QLabel("丁寧語 (Polite)")
        self.b_polite_badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 700;
            border: 1px solid #059669;
        """)
        b_header.addWidget(self.b_polite_badge)
        b_header.addStretch()

        listen_btn = QPushButton("🔊 Listen")
        listen_btn.setFixedHeight(28)
        listen_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
        """)
        listen_btn.clicked.connect(self._play_tts)
        b_header.addWidget(listen_btn)
        b_layout.addLayout(b_header)

        b_prompt_lbl = QLabel("NATURAL CORRECTION")
        b_prompt_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        self.b_text = QLabel("アイスコーヒーをひとつ、お願いします。")
        self.b_text.setWordWrap(True)
        self.b_text.setAlignment(Qt.AlignCenter)
        self.b_text.setStyleSheet("color: #ffffff; font-size: 22px; font-weight: 800; line-height: 1.4;")
        b_layout.addWidget(b_prompt_lbl, alignment=Qt.AlignCenter)
        b_layout.addWidget(self.b_text)

        # Grammar note
        self.b_note = QLabel("Note: Append お願いします for polite etiquette.")
        self.b_note.setWordWrap(True)
        self.b_note.setAlignment(Qt.AlignCenter)
        self.b_note.setStyleSheet("color: #94a3b8; font-size: 12px; font-style: italic;")
        b_layout.addWidget(self.b_note)

        # Vocab chips
        self.b_vocab = QLabel("💡 ひとつ (One item)")
        self.b_vocab.setWordWrap(True)
        self.b_vocab.setAlignment(Qt.AlignCenter)
        self.b_vocab.setStyleSheet("color: #c7d2fe; font-size: 11px; font-weight: bold;")
        b_layout.addWidget(self.b_vocab)

        b_layout.addStretch()
        flip_back_btn = QPushButton("↩ Flip Back to Prompt")
        flip_back_btn.setFixedHeight(34)
        flip_back_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: white;
            }
        """)
        flip_back_btn.clicked.connect(lambda: self.card_stack.setCurrentIndex(0))
        b_layout.addWidget(flip_back_btn)

        self.card_stack.addWidget(self.front_frame)
        self.card_stack.addWidget(self.back_frame)
        main_layout.addWidget(self.card_stack)

        # Bottom Control Deck
        ctrl_bar = QHBoxLayout()
        
        prev_btn = QPushButton("⬅ Previous")
        prev_btn.setFixedHeight(38)
        prev_btn.setStyleSheet(self._btn_style("#1f2937", "#cbd5e1", "#374151"))
        prev_btn.clicked.connect(self._prev_card)

        del_btn = QPushButton("🗑 Remove")
        del_btn.setFixedHeight(38)
        del_btn.setStyleSheet(self._btn_style("#1f2937", "#f87171", "#7f1d1d"))
        del_btn.clicked.connect(self._delete_card)

        practice_again_btn = QPushButton("🔁 Needs Review")
        practice_again_btn.setFixedHeight(38)
        practice_again_btn.setStyleSheet(self._btn_style("#451a03", "#fbbf24", "#d97706"))
        practice_again_btn.clicked.connect(lambda: self._mark_mastered(False))

        master_btn = QPushButton("✅ Mark Mastered")
        master_btn.setFixedHeight(38)
        master_btn.setStyleSheet(self._btn_style("#064e3b", "#34d399", "#059669"))
        master_btn.clicked.connect(lambda: self._mark_mastered(True))

        next_btn = QPushButton("Next ➡")
        next_btn.setFixedHeight(38)
        next_btn.setStyleSheet(self._btn_style("#1f2937", "#cbd5e1", "#374151"))
        next_btn.clicked.connect(self._next_card)

        ctrl_bar.addWidget(prev_btn)
        ctrl_bar.addWidget(del_btn)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(practice_again_btn)
        ctrl_bar.addWidget(master_btn)
        ctrl_bar.addWidget(next_btn)
        main_layout.addLayout(ctrl_bar)

        self._update_filter_button_styles()

    def _btn_style(self, bg: str, text: str, border: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {text};
            }}
        """

    def _set_filter(self, mode: str):
        self.filter_mode = mode
        self.current_index = 0
        self._update_active_cards()
        self._update_filter_button_styles()
        self._display_current_card()

    def _update_filter_button_styles(self):
        active_style = "background-color: #4f46e5; color: white; border: 1px solid #6366f1; border-radius: 6px; font-size: 11px; font-weight: bold; padding: 0 10px;"
        idle_style = "background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; font-size: 11px; font-weight: bold; padding: 0 10px;"
        self.btn_filter_all.setStyleSheet(active_style if self.filter_mode == "all" else idle_style)
        self.btn_filter_unmastered.setStyleSheet(active_style if self.filter_mode == "unmastered" else idle_style)
        self.btn_filter_mastered.setStyleSheet(active_style if self.filter_mode == "mastered" else idle_style)

    def _display_current_card(self):
        self.card_stack.setCurrentIndex(0)
        total = len(self.active_cards)
        mastered_total = self.deck.mastered_count

        if total == 0:
            self.progress_subtitle.setText(f"No cards in filter [{self.filter_mode}]. Total deck: {self.deck.total_count}")
            self.f_text.setText("🎴 Practice Deck Empty")
            self.f_scenario_badge.setText("Empty Deck")
            self.f_status_badge.setText("NO CARDS")
            self.b_text.setText("Practice with AI Coach to bookmark cards!")
            self.b_note.setText("")
            self.b_vocab.setText("")
            self.prog_bar.setValue(0)
            return

        self.current_index = max(0, min(self.current_index, total - 1))
        card = self.active_cards[self.current_index]

        self.progress_subtitle.setText(f"Card {self.current_index + 1} of {total} • Mastered: {mastered_total} / {self.deck.total_count}")
        self.prog_bar.setValue(int(((self.current_index + 1) / total) * 100))

        # Front content
        self.f_text.setText(card.original_text)
        sc_map = {
            "cafe": "🍵 Cafe & Dining", "transit": "🚅 Transit & Nav",
            "hotel": "🏨 Hotel Check-in", "business": "💼 Business", "free_talk": "🗣️ Daily Talk"
        }
        self.f_scenario_badge.setText(sc_map.get(card.scenario_id, "🗣️ Daily Talk"))
        
        if card.mastered:
            self.f_status_badge.setText("✅ MASTERED")
            self.f_status_badge.setStyleSheet("background-color: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 10px; font-size: 10px; font-weight: 800;")
        else:
            self.f_status_badge.setText("🌱 NEEDS PRACTICE")
            self.f_status_badge.setStyleSheet("background-color: #451a03; color: #fbbf24; padding: 4px 10px; border-radius: 10px; font-size: 10px; font-weight: 800;")

        # Back content
        self.b_text.setText(card.suggested_correction)
        self.b_polite_badge.setText(card.politeness_level or "丁寧語 (Polite)")
        self.b_note.setText(f"Grammar Note: {card.grammar_notes}" if card.grammar_notes else "")
        self.b_vocab.setText(" | ".join(card.vocabulary_tips) if card.vocabulary_tips else "")

    def _next_card(self):
        if self.active_cards:
            self.current_index = (self.current_index + 1) % len(self.active_cards)
            self._display_current_card()

    def _prev_card(self):
        if self.active_cards:
            self.current_index = (self.current_index - 1) % len(self.active_cards)
            self._display_current_card()

    def _mark_mastered(self, mastered: bool):
        if not self.active_cards:
            return
        card = self.active_cards[self.current_index]
        self.deck.mark_mastered(card.id, mastered)
        self._update_active_cards()
        self._display_current_card()

    def _delete_card(self):
        if not self.active_cards:
            return
        card = self.active_cards[self.current_index]
        self.deck.remove_card(card.id)
        self._update_active_cards()
        self._display_current_card()

    def _play_tts(self):
        if not self.active_cards:
            return
        card = self.active_cards[self.current_index]
        text = card.suggested_correction
        if self.tts:
            self.tts.synthesize_and_play(text, lang="ja")
