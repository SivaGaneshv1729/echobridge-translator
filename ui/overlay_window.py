"""Floating transparent always-on-top subtitle overlay (HUD) for EchoBridge."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGraphicsDropShadowEffect, QApplication
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QFont

class SubtitleOverlayWindow(QWidget):
    """
    Frameless, semi-transparent, always-on-top floating HUD that displays
    real-time speech transcription and translation over other desktop applications.
    """
    restore_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = QPoint()
        self._font_size = 20

        # Window flags for floating transparent overlay
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(720, 150)
        self.setMinimumSize(450, 120)

        # Center towards the bottom third of the primary screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 100
        self.move(x, y)

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Card Container
        self.card = QFrame(self)
        self.card.setObjectName("hudCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 12, 18, 14)
        card_layout.setSpacing(6)

        # Top Control & Drag Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Drag handle icon & title
        self.drag_icon = QLabel("⠿ EchoBridge HUD")
        self.drag_icon.setObjectName("hudTitle")
        self.drag_icon.setCursor(Qt.SizeAllCursor)

        # Direction / Status pill
        self.status_pill = QLabel("🟢 AUTO LISTENING")
        self.status_pill.setObjectName("statusPill")

        # Font size adjustment buttons
        self.btn_font_dec = QPushButton("A-")
        self.btn_font_dec.setFixedSize(28, 24)
        self.btn_font_dec.clicked.connect(self._decrease_font)

        self.btn_font_inc = QPushButton("A+")
        self.btn_font_inc.setFixedSize(28, 24)
        self.btn_font_inc.clicked.connect(self._increase_font)

        # Restore main window button
        self.btn_restore = QPushButton("⤢ Expand")
        self.btn_restore.setObjectName("hudBtn")
        self.btn_restore.setFixedHeight(24)
        self.btn_restore.clicked.connect(self.restore_requested.emit)

        # Close / hide overlay
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("hudCloseBtn")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.close_requested.emit)

        top_bar.addWidget(self.drag_icon)
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_font_dec)
        top_bar.addWidget(self.btn_font_inc)
        top_bar.addWidget(self.btn_restore)
        top_bar.addWidget(self.btn_close)
        card_layout.addLayout(top_bar)

        # Original Spoken Text (compact)
        self.orig_label = QLabel("Listening for speech...")
        self.orig_label.setObjectName("origLabel")
        self.orig_label.setWordWrap(True)
        self.orig_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(self.orig_label)

        # Translated Text (prominent subtitle)
        self.trans_label = QLabel("Subtitles will appear here in real-time.")
        self.trans_label.setObjectName("transLabel")
        self.trans_label.setWordWrap(True)
        self.trans_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(self.trans_label)

        # Drop shadow for clean floating effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        main_layout.addWidget(self.card)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#hudCard {{
                background-color: rgba(11, 15, 25, 0.92);
                border: 1.5px solid #0284c7;
                border-radius: 14px;
            }}
            QLabel#hudTitle {{
                color: #94a3b8;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
            QLabel#statusPill {{
                background-color: #064e3b;
                color: #34d399;
                font-size: 10px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 8px;
                border: 1px solid #059669;
            }}
            QLabel#origLabel {{
                color: #94a3b8;
                font-size: 12px;
                font-weight: 500;
            }}
            QLabel#transLabel {{
                color: #ffffff;
                font-size: {self._font_size}px;
                font-weight: 700;
                line-height: 1.3;
            }}
            QPushButton {{
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #334155;
                color: #ffffff;
            }}
            QPushButton#hudBtn {{
                padding: 2px 10px;
                background-color: #0c4a6e;
                color: #38bdf8;
                border: 1px solid #0284c7;
            }}
            QPushButton#hudBtn:hover {{
                background-color: #0284c7;
                color: #ffffff;
            }}
            QPushButton#hudCloseBtn:hover {{
                background-color: #dc2626;
                color: #ffffff;
                border-color: #ef4444;
            }}
        """)

    def update_transcription(self, text: str, lang: str):
        """Update the original spoken transcription line."""
        lang_flag = "🇺🇸" if lang == "en" else "🇯🇵"
        self.orig_label.setText(f"{lang_flag} {text}")

    def update_translation(self, text: str):
        """Update the main translated subtitle text."""
        self.trans_label.setText(text)

    def set_active_state(self, is_active: bool, is_speaking: bool = False):
        """Update the visual status badge."""
        if not is_active:
            self.status_pill.setText("⚫ MIC IDLE")
            self.status_pill.setStyleSheet("""
                background-color: #1f2937;
                color: #64748b;
                font-size: 10px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 8px;
                border: 1px solid #374151;
            """)
        elif is_speaking:
            self.status_pill.setText("⚡ SPEAKING...")
            self.status_pill.setStyleSheet("""
                background-color: #92400e;
                color: #fbbf24;
                font-size: 10px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 8px;
                border: 1px solid #d97706;
            """)
        else:
            self.status_pill.setText("🟢 AUTO LISTENING")
            self.status_pill.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                font-size: 10px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 8px;
                border: 1px solid #059669;
            """)

    def _increase_font(self):
        if self._font_size < 34:
            self._font_size += 2
            self._apply_style()

    def _decrease_font(self):
        if self._font_size > 14:
            self._font_size -= 2
            self._apply_style()

    # --- Mouse Drag Support for Frameless Window ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
