"""Barra do player: logo, agora tocando, ondas, progresso, controles e volume."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget, QStyle)

from .visualizer import Visualizer
from .styles import C


def _fmt(ms):
    s = max(0, ms // 1000)
    return f"{s // 60:02d}:{s % 60:02d}"


def _find_logo():
    bases = ["."]
    import sys
    if getattr(sys, "frozen", False):
        bases.append(sys._MEIPASS)
    for base in bases:
        for name in ("logo.png", "logo.jpg"):
            path = os.path.join(base, "assets", name)
            if os.path.exists(path):
                return path
    return None


class PlayerBar(QWidget):
    toggle = Signal()
    next_track = Signal()
    prev_track = Signal()
    seek = Signal(int)
    volume_changed = Signal(float)
    voice_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBar")

        # --- logo ---
        self.logo_label = QLabel()
        logo_path = _find_logo()
        if logo_path:
            pm = QPixmap(logo_path).scaled(64, 72, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation)
            self.logo_label.setPixmap(pm)
            self.logo_label.setFixedSize(72, 72)
        else:
            self.logo_label.setText("♫")
            self.logo_label.setAlignment(Qt.AlignCenter)
            self.logo_label.setStyleSheet(
                f"color: {C['accent2']}; font-size: 34px; "
                f"background: {C['card2']}; border-radius: 24px; "
                f"border: 2px solid {C['border']};")
            self.logo_label.setFixedSize(48, 48)

        # --- título / agora tocando ---
        title_box = QVBoxLayout()
        self.station_label = QLabel("RÁDIO HERMES")
        self.station_label.setObjectName("logoTitle")
        self.now_label = QLabel("Nada tocando")
        self.now_label.setObjectName("nowLabel")
        self.now_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_box.addWidget(self.station_label)
        title_box.addWidget(self.now_label)

        # --- visualizador ---
        self.visualizer = Visualizer()

        # --- controles ---
        self.btn_prev = QPushButton("⏮")
        self.btn_toggle = QPushButton("▶")
        self.btn_next = QPushButton("⏭")
        for b, obj in ((self.btn_prev, "btnSide"),
                       (self.btn_next, "btnSide"),
                       (self.btn_toggle, "btnPlay")):
            b.setObjectName(obj)
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_toggle.clicked.connect(self.toggle)
        self.btn_next.clicked.connect(self.next_track)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addStretch(1)
        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_toggle)
        controls.addWidget(self.btn_next)
        controls.addStretch(1)

        # --- progresso ---
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.seek)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("timeLabel")
        self.time_label.setAlignment(Qt.AlignRight)

        prog_row = QHBoxLayout()
        prog_row.addWidget(self.slider, 1)
        prog_row.addWidget(self.time_label)

        # --- volume + voz ---
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(110)
        self.vol_slider.valueChanged.connect(
            lambda v: self.volume_changed.emit(v / 100.0))
        self.vol_icon = QLabel("🔊")
        self.vol_icon.setFixedWidth(24)

        self.btn_voice = QPushButton("Voz: ♀")
        self.btn_voice.setFixedWidth(110)
        self.btn_voice.setToolTip("Trocar voz pt-BR (Francisca ♀ / Antonio ♂)")
        self.btn_voice.clicked.connect(self.voice_toggled)

        side_row = QHBoxLayout()
        side_row.addStretch(1)
        side_row.addWidget(self.vol_icon)
        side_row.addWidget(self.vol_slider)
        side_row.addWidget(self.btn_voice)

        # --- montagem ---
        top = QHBoxLayout()
        top.addWidget(self.logo_label)
        top.addSpacing(12)
        top.addLayout(title_box, 1)
        top.addWidget(self.visualizer, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(controls)
        layout.addLayout(prog_row)
        layout.addLayout(side_row)

    def set_playing(self, playing):
        self.btn_toggle.setText("⏸" if playing else "▶")
        self.visualizer.set_playing(playing)

    def set_voice(self, voice_name):
        fem = "Francisca" in voice_name
        self.btn_voice.setText("Voz: ♀" if fem else "Voz: ♂")

    def set_track(self, title):
        self.now_label.setText(title or "Nada tocando")
        self.visualizer.reset()

    def set_progress(self, pos, dur):
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(1, int(dur)))
        self.slider.setValue(int(pos))
        self.slider.blockSignals(False)
        self.time_label.setText(f"{_fmt(pos)} / {_fmt(dur)}")
