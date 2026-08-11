"""Painel da fila de reprodução com suporte a drag & drop, remoção e duplo clique."""
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem,
                               QMenu)

from ..engine import Track
from .styles import C

_STATUS_ICON = {
    "queued": "·",
    "working": "⏳",
    "ready": "▶",
    "error": "✕",
}


class PlaylistWidget(QListWidget):
    play_requested = Signal(int)
    remove_requested = Signal(int)
    files_dropped = Signal(list)   # lista de paths locais

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.itemDoubleClicked.connect(self._on_double)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)

    def refresh(self, queue):
        self.blockSignals(True)
        self.clear()
        for i, t in enumerate(queue):
            item = QListWidgetItem(self._fmt(t))
            item.setData(Qt.UserRole, i)
            if t.status == "error":
                item.setForeground(QBrush(QColor(C["red"])))
            elif t.status == "ready":
                item.setForeground(QBrush(QColor(C["green"])))
            elif t.status == "working":
                item.setForeground(QBrush(QColor(C["amber"])))
            else:
                item.setForeground(QBrush(QColor(C["dim"])))
            self.addItem(item)
        self.blockSignals(False)

    def _fmt(self, t):
        icon = _STATUS_ICON.get(t.status, "·")
        base = f"{icon}  {t.title}"
        if t.status == "working":
            return f"{base}  — {t.progress}"
        if t.status == "error":
            return f"{base}  — {t.error[:40]}"
        if t.status == "ready":
            dur = t.total_duration or t.music_duration
            mins = int(dur) // 60
            secs = int(dur) % 60
            return f"{base}   ({mins}:{secs:02d})"
        return base

    def _on_double(self, item):
        self.play_requested.emit(item.data(Qt.UserRole))

    def _on_context(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        menu = QMenu(self)
        play = menu.addAction("Tocar")
        remove = menu.addAction("Remover")
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == play:
            self.play_requested.emit(idx)
        elif action == remove:
            self.remove_requested.emit(idx)

    def _drop_urls(self, mime):
        urls = [u for u in mime.urls() if u.isLocalFile()]
        return [u.toLocalFile() for u in urls]

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            files = self._drop_urls(e.mimeData())
            if files:
                self.files_dropped.emit(files)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)
