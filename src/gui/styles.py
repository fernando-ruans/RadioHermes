"""Tema escuro da Rádio Hermes (QSS global)."""
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

C = {
    "bg":        "#0a0a0f",
    "card":      "#151524",
    "card2":     "#1b1b2e",
    "accent":    "#7c6cf0",
    "accent2":   "#00cec9",
    "text":      "#e8e8f0",
    "dim":       "#8a8a9e",
    "green":     "#00c896",
    "red":       "#ff6b6b",
    "amber":     "#fdcb6e",
    "border":    "#232338",
    "slider":    "#2b2b42",
    "hover":     "#26263f",
}


def build_stylesheet():
    return f"""
* {{
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
    color: {C['text']};
    outline: none;
}}
QMainWindow, QDialog {{
    background: {C['bg']};
}}
QWidget#playerBar {{
    background: {C['card']};
    border-bottom: 1px solid {C['border']};
    border-radius: 12px;
    margin: 8px;
    padding: 8px;
}}
QLabel#nowLabel {{
    font-size: 17px;
    font-weight: 600;
    color: {C['text']};
    padding: 2px 8px;
}}
QLabel#logoTitle {{
    font-size: 20px;
    font-weight: 800;
    color: {C['accent2']};
    letter-spacing: 1px;
}}
QLabel#timeLabel {{
    color: {C['dim']};
    font-size: 12px;
}}
QLabel#hintLabel {{
    color: {C['dim']};
    font-size: 11px;
}}
QGroupBox {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {C['accent2']};
}}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {C['bg']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 5px 8px;
    selection-background-color: {C['accent']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {C['accent']};
}}
QPushButton {{
    background: {C['card2']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {C['hover']};
    border-color: {C['accent']};
}}
QPushButton:pressed {{
    background: {C['accent']};
    color: white;
}}
QPushButton:disabled {{
    color: {C['dim']};
    background: {C['card']};
}}
QPushButton#btnPlay {{
    background: {C['accent']};
    border: none;
    border-radius: 22px;
    min-width: 44px;
    min-height: 44px;
    max-width: 44px;
    max-height: 44px;
    font-size: 18px;
}}
QPushButton#btnPlay:hover {{
    background: {C['accent2']};
}}
QPushButton#btnSide {{
    background: transparent;
    border: none;
    border-radius: 10px;
    min-width: 34px;
    min-height: 34px;
    max-width: 34px;
    max-height: 34px;
    font-size: 16px;
}}
QPushButton#btnSide:hover {{
    background: {C['hover']};
}}
QListWidget {{
    background: {C['bg']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 4px;
}}
QListWidget::item {{
    border-radius: 8px;
    padding: 4px;
    margin: 2px 0;
}}
QListWidget::item:hover {{
    background: {C['hover']};
}}
QListWidget::item:selected {{
    background: {C['accent']};
    color: white;
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: {C['slider']};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {C['accent']};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: {C['slider']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {C['accent2']};
    border: 2px solid {C['bg']};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    background: {C['card']};
}}
QTabBar::tab {{
    background: {C['card2']};
    border: 1px solid {C['border']};
    border-bottom: none;
    padding: 8px 18px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C['accent']};
    color: white;
}}
QStatusBar {{
    background: {C['card']};
    color: {C['dim']};
    border-top: 1px solid {C['border']};
}}
QMenuBar {{
    background: {C['card']};
    border-bottom: 1px solid {C['border']};
}}
QMenuBar::item {{
    padding: 5px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {C['hover']};
    border-radius: 6px;
}}
QMenu {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {C['accent']};
    color: white;
}}
QScrollBar:vertical {{
    background: {C['bg']};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {C['slider']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {C['card2']};
    color: {C['text']};
    border: 1px solid {C['border']};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""


def apply_theme(app):
    app.setStyleSheet(build_stylesheet())
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(C["bg"]))
    pal.setColor(QPalette.WindowText, QColor(C["text"]))
    pal.setColor(QPalette.Base, QColor(C["bg"]))
    pal.setColor(QPalette.AlternateBase, QColor(C["card"]))
    pal.setColor(QPalette.Text, QColor(C["text"]))
    pal.setColor(QPalette.Button, QColor(C["card"]))
    pal.setColor(QPalette.ButtonText, QColor(C["text"]))
    pal.setColor(QPalette.Highlight, QColor(C["accent"]))
    pal.setColor(QPalette.HighlightedText, Qt.white)
    pal.setColor(QPalette.ToolTipBase, QColor(C["card2"]))
    pal.setColor(QPalette.ToolTipText, QColor(C["text"]))
    app.setPalette(pal)
