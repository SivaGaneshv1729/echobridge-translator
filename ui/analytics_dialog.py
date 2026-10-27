"""Fluency & Learning Analytics Dashboard Dialog for EchoBridge Desktop."""
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QWidget, QGridLayout, QFileDialog, QMessageBox, QProgressBar
)

from pipeline.analytics import AnalyticsEngine, FluencyStats
from pipeline.conversation import ConversationTurn

class StatCard(QFrame):
    """Sleek dark card displaying a single key metric."""
    def __init__(self, title: str, value: str, subtitle: str, color_hex: str = "#38bdf8", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 12px;
                padding: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {color_hex};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        t_lbl = QLabel(title.upper())
        t_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;")
        
        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(f"color: {color_hex}; font-size: 22px; font-weight: 900;")

        s_lbl = QLabel(subtitle)
        s_lbl.setStyleSheet("color: #64748b; font-size: 10px;")

        layout.addWidget(t_lbl)
        layout.addWidget(v_lbl)
        layout.addWidget(s_lbl)

class AnalyticsDialog(QDialog):
    """Modern Dark-Mode Fluency & Learning Analytics Dashboard."""

    def __init__(self, turns: List[ConversationTurn], parent=None):
        super().__init__(parent)
        self.setWindowTitle("EchoBridge - Fluency & Learning Analytics")
        self.setMinimumSize(820, 680)
        self.setStyleSheet("background-color: #0b0f19; color: #f1f5f9; font-family: 'Segoe UI', sans-serif;")
        
        self.engine = AnalyticsEngine()
        self.turns = turns
        self.stats = self.engine.compute_from_turns(turns)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("📊 Fluency & Learning Analytics")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        subtitle = QLabel("Real-time spoken fluency score, politeness dynamics, and role-play scenario progress.")
        subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        export_btn = QPushButton("📄 Export Report")
        export_btn.setFixedHeight(36)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
        """)
        export_btn.clicked.connect(self._export_report)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addWidget(export_btn)
        main_layout.addLayout(header_layout)

        # Scrollable Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(16)

        # 1. Stat Cards Row
        grid = QGridLayout()
        grid.setSpacing(12)

        # Format time
        mins = int(self.stats.practice_seconds // 60)
        secs = int(self.stats.practice_seconds % 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        score_color = "#34d399" if self.stats.fluency_score >= 80 else ("#fbbf24" if self.stats.fluency_score >= 60 else "#f87171")
        grid.addWidget(StatCard("Overall Fluency", f"{self.stats.fluency_score}%", f"{self.stats.natural_turns} / {self.stats.coach_turns} natural turns", score_color), 0, 0)
        grid.addWidget(StatCard("Total Utterances", str(self.stats.total_turns), f"{self.stats.coach_turns} evaluated with AI Coach", "#38bdf8"), 0, 1)
        grid.addWidget(StatCard("Practice Duration", time_str, f"{self.stats.active_days} active training day(s)", "#a78bfa"), 0, 2)
        grid.addWidget(StatCard("Grammar Corrections", str(self.stats.needs_correction_turns), "Linguistic tips provided", "#f43f5e"), 0, 3)
        c_layout.addLayout(grid)

        # 2. Politeness Breakdown Section (敬語)
        polite_frame = QFrame()
        polite_frame.setStyleSheet("background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 14px;")
        pf_layout = QVBoxLayout(polite_frame)
        pf_layout.setSpacing(8)

        pf_title = QLabel("🎎 POLITENESS & HONORIFICS (敬語バランス)")
        pf_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        pf_layout.addWidget(pf_title)

        p_dist = self.stats.politeness_distribution
        p_total = sum(p_dist.values()) or 1
        
        # Legend row
        legend_layout = QHBoxLayout()
        items = [
            ("丁寧語 (Polite)", p_dist.get("polite", 0), "#3b82f6"),
            ("謙譲語 (Humble)", p_dist.get("humble", 0), "#6366f1"),
            ("尊敬語 (Respectful)", p_dist.get("respectful", 0), "#8b5cf6"),
            ("普通体 (Casual)", p_dist.get("casual", 0), "#64748b"),
        ]
        for name, count, color in items:
            pct = round((count / p_total) * 100)
            tag = QLabel(f"● {name}: {count} ({pct}%)")
            tag.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")
            legend_layout.addWidget(tag)
        legend_layout.addStretch()
        pf_layout.addLayout(legend_layout)

        # Progress bar
        p_bar = QProgressBar()
        p_bar.setFixedHeight(12)
        p_bar.setTextVisible(False)
        p_bar.setValue(min(100, int((p_dist.get("polite", 0) + p_dist.get("humble", 0) + p_dist.get("respectful", 0)) / p_total * 100)))
        p_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 6px;
                border: 1px solid #334155;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
                border-radius: 6px;
            }
        """)
        pf_layout.addWidget(p_bar)
        c_layout.addWidget(polite_frame)

        # 3. Role-Play Scenario Mastery Section
        sc_frame = QFrame()
        sc_frame.setStyleSheet("background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 14px;")
        scf_layout = QVBoxLayout(sc_frame)
        scf_layout.setSpacing(10)

        scf_title = QLabel("🗺️ ROLE-PLAY SCENARIO MASTERY")
        scf_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        scf_layout.addWidget(scf_title)

        sc_grid = QHBoxLayout()
        sc_grid.setSpacing(8)
        sc_labels = [
            ("🗣️ Daily Talk", "free_talk", "#38bdf8"),
            ("🍵 Cafe & Dining", "cafe", "#10b981"),
            ("🚅 Transit & Nav", "transit", "#f59e0b"),
            ("🏨 Hotel Check-in", "hotel", "#8b5cf6"),
            ("💼 Business", "business", "#ec4899"),
        ]
        s_dist = self.stats.scenario_distribution
        for title_str, sc_id, color_hex in sc_labels:
            count = s_dist.get(sc_id, 0)
            box = QFrame()
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: #0b0f19;
                    border: 1px solid {color_hex}44;
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
            b_lay = QVBoxLayout(box)
            b_lay.setContentsMargins(6, 6, 6, 6)
            b_lay.setSpacing(2)
            lbl_name = QLabel(title_str)
            lbl_name.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
            lbl_cnt = QLabel(f"{count} turns")
            lbl_cnt.setStyleSheet(f"font-size: 14px; font-weight: 900; color: {color_hex};")
            b_lay.addWidget(lbl_name)
            b_lay.addWidget(lbl_cnt)
            sc_grid.addWidget(box)
        scf_layout.addLayout(sc_grid)
        c_layout.addWidget(sc_frame)

        # 4. Recent Grammar Corrections & Learning Points
        tips_frame = QFrame()
        tips_frame.setStyleSheet("background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 14px;")
        tf_layout = QVBoxLayout(tips_frame)
        tf_layout.setSpacing(8)

        tf_title = QLabel("⚡ RECENT LEARNING POINTS & CORRECTIONS")
        tf_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        tf_layout.addWidget(tf_title)

        if not self.stats.recent_grammar_tips:
            empty_lbl = QLabel("✨ All utterances in this session were natural and grammatically fluent! Keep it up.")
            empty_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-style: italic; padding: 8px 0;")
            tf_layout.addWidget(empty_lbl)
        else:
            for tip in reversed(self.stats.recent_grammar_tips[-4:]):
                item = QFrame()
                item.setStyleSheet("background-color: #0b0f19; border: 1px solid #1f2937; border-radius: 8px; padding: 8px;")
                i_lay = QVBoxLayout(item)
                i_lay.setContentsMargins(8, 6, 8, 6)
                i_lay.setSpacing(4)
                
                orig_lbl = QLabel(f"• You said: \"{tip.get('original', '')}\"")
                orig_lbl.setStyleSheet("color: #f87171; font-size: 12px;")
                
                corr_lbl = QLabel(f"  Suggested: \"{tip.get('correction', '')}\"")
                corr_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: bold;")
                
                note_lbl = QLabel(f"  Note: {tip.get('note', '')}")
                note_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-style: italic;")
                
                i_lay.addWidget(orig_lbl)
                i_lay.addWidget(corr_lbl)
                i_lay.addWidget(note_lbl)
                tf_layout.addWidget(item)

        c_layout.addWidget(tips_frame)

        # 5. Vocabulary Bank
        vocab_frame = QFrame()
        vocab_frame.setStyleSheet("background-color: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 14px;")
        vf_layout = QVBoxLayout(vocab_frame)
        vf_layout.setSpacing(8)

        vf_title = QLabel(f"📚 VOCABULARY BANK ({len(self.stats.vocabulary_collected)} items)")
        vf_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        vf_layout.addWidget(vf_title)

        if not self.stats.vocabulary_collected:
            no_vocab = QLabel("No vocabulary collected yet. Speak with the AI Coach to build your vocabulary bank!")
            no_vocab.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
            vf_layout.addWidget(no_vocab)
        else:
            v_wrap = QHBoxLayout()
            v_wrap.setSpacing(6)
            for v in self.stats.vocabulary_collected[:6]:
                chip = QLabel(f"💡 {v}")
                chip.setStyleSheet("""
                    background-color: #1e1b4b;
                    color: #c7d2fe;
                    border: 1px solid #4338ca;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-size: 10px;
                    font-weight: bold;
                """)
                v_wrap.addWidget(chip)
            v_wrap.addStretch()
            vf_layout.addLayout(v_wrap)
        c_layout.addWidget(vocab_frame)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 36)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        main_layout.addLayout(btn_row)

    def _export_report(self):
        """Exports markdown fluency report to a file chosen by the user."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Fluency & Learning Report",
            f"echobridge_fluency_report_{int(time.time())}.md",
            "Markdown Files (*.md);;Text Files (*.txt)"
        )
        if not file_path:
            return

        try:
            report_text = self.engine.generate_markdown_summary(self.stats)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_text)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Fluency & Learning report successfully exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {e}")
