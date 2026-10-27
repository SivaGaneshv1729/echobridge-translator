"""Dynamic Soundwave Visualizer widget for EchoBridge."""
import math
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush

class SoundwaveVisualizer(QWidget):
    """
    Renders 32 reactive dynamic equalizer bars with decay physics and gentle idle breathing.
    """
    def __init__(self, num_bars: int = 36, parent=None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.bar_heights = np.zeros(num_bars, dtype=np.float32)
        self.target_heights = np.zeros(num_bars, dtype=np.float32)
        
        self.is_active = False
        self._phase = 0.0

        self.setFixedHeight(36)
        self.setMinimumWidth(200)

        # 60 FPS animation timer for smooth organic physics
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_tick)
        self.timer.start(16)

    def set_active(self, active: bool):
        """Set whether microphone is active."""
        self.is_active = active
        if not active:
            self.target_heights.fill(0.0)

    def set_level(self, level: float):
        """
        Feed live audio RMS level (0.0 to 1.0).
        Disperses amplitude across the frequency bars with a bell-curve distribution.
        """
        if not self.is_active:
            return

        level = max(0.0, min(1.0, level))
        center = self.num_bars / 2.0
        
        # Random turbulence to simulate multi-band frequency spectrum
        rand_noise = np.random.uniform(0.7, 1.3, size=self.num_bars)

        for i in range(self.num_bars):
            # Bell curve dispersion around the center
            dist = abs(i - center) / center
            falloff = math.exp(-2.5 * dist * dist)
            h = level * falloff * rand_noise[i]
            # Boost sensitivity
            self.target_heights[i] = max(self.target_heights[i], min(1.0, h * 1.6))

    def _animate_tick(self):
        """Physics update: decay bar heights smoothly and animate idle wave."""
        self._phase += 0.08
        decay_factor = 0.82

        for i in range(self.num_bars):
            # Decay towards target
            if self.target_heights[i] > self.bar_heights[i]:
                self.bar_heights[i] = self.bar_heights[i] * 0.4 + self.target_heights[i] * 0.6
            else:
                self.bar_heights[i] *= decay_factor

            self.target_heights[i] *= 0.88

            # Gentle idle wave when active but quiet
            if self.is_active and self.bar_heights[i] < 0.08:
                idle = 0.06 + 0.04 * math.sin(self._phase + i * 0.35)
                self.bar_heights[i] = max(self.bar_heights[i], idle)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        bar_spacing = 3
        total_spacing = bar_spacing * (self.num_bars - 1)
        bar_width = max(2.0, (width - total_spacing) / self.num_bars)

        min_bar_h = 3.0
        max_bar_h = height - 4.0
        cy = height / 2.0

        for i in range(self.num_bars):
            bh = min_bar_h + self.bar_heights[i] * (max_bar_h - min_bar_h)
            bx = i * (bar_width + bar_spacing)
            by = cy - (bh / 2.0)

            # Horizontal color progression: Emerald -> Cyan -> Amber
            ratio = i / float(self.num_bars)
            if ratio < 0.5:
                # Emerald (#10b981) to Cyan (#06b6d4)
                r = int(16 + (6 - 16) * (ratio * 2.0))
                g = int(185 + (182 - 185) * (ratio * 2.0))
                b = int(129 + (212 - 129) * (ratio * 2.0))
            else:
                # Cyan (#06b6d4) to Amber (#f59e0b)
                sub_r = (ratio - 0.5) * 2.0
                r = int(6 + (245 - 6) * sub_r)
                g = int(182 + (158 - 182) * sub_r)
                b = int(212 + (11 - 212) * sub_r)

            # Transparency based on activity
            alpha = 240 if self.is_active else 60
            color = QColor(r, g, b, alpha)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                QRectF(float(bx), float(by), float(bar_width), float(bh)),
                float(bar_width / 2.0),
                float(bar_width / 2.0)
            )

        painter.end()
