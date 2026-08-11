"""Visualizador de ondas sonoras animadas (barras que reagem ao playback)."""
import math
import random

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .styles import C


class Visualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self._playing = False
        self._bars = [0.0] * 64
        self._target = [0.0] * 64
        self._timer = QTimer(self)
        self._timer.setInterval(33)          # ~30fps
        self._timer.timeout.connect(self._tick)

    def set_playing(self, playing):
        self._playing = bool(playing)
        if playing:
            if not self._timer.isActive():
                self._timer.start()
        else:
            # congela suavemente
            for i in range(len(self._target)):
                self._target[i] *= 0.3
            if not self._timer.isActive():
                self._timer.start()

    def _tick(self):
        n = len(self._bars)
        if self._playing:
            # gera alvos orgânicos: senoide suave + ruído
            t = self._timer_elapsed()
            for i in range(n):
                x = i / n
                wave = (math.sin(x * math.pi * 2 + t * 0.6) + 1.0) / 2.0
                wave *= 0.55
                wave += 0.25 + 0.2 * math.sin(x * math.pi * 7 + t * 1.3)
                noise = random.uniform(0, 0.3)
                self._target[i] = min(1.0, wave + noise)
        # interpola para suavizar
        for i in range(n):
            self._bars[i] += (self._target[i] - self._bars[i]) * 0.25
        if not self._playing and max(self._bars) < 0.02:
            self._timer.stop()
        self.update()

    def _timer_elapsed(self):
        # avanço contínuo (só reseta ao trocar de música)
        if not hasattr(self, "_t0"):
            self._t0 = 0.0
        self._t0 += 0.033
        return self._t0

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._bars)
        slot = w / n
        bar_w = max(2, slot * 0.55)
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(C["accent"]))
        grad.setColorAt(0.5, QColor(C["accent2"]))
        grad.setColorAt(1.0, QColor(C["accent"]))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        for i, v in enumerate(self._bars):
            x = i * slot + (slot - bar_w) / 2
            bh = max(3, v * (h - 8))
            y = (h - bh) / 2
            p.drawRoundedRect(int(x), int(y), int(bar_w), int(bh), 2, 2)
        p.end()

    def reset(self):
        self._bars = [0.0] * len(self._bars)
        self._target = [0.0] * len(self._target)
        if hasattr(self, "_t0"):
            self._t0 = 0.0
        self.update()
