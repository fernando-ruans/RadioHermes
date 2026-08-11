"""Painel de busca do YouTube com cards (thumbnail + título + duração),
campo de URL direta e botão de arquivo local."""
import traceback

import httpx
from PySide6.QtCore import QSize, Qt, Signal, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from .styles import C


class ThumbnailWorker(QThread):
    loaded = Signal(int, QPixmap)   # índice, pixmap

    def __init__(self, url, idx, parent=None):
        super().__init__(parent)
        self.url = url
        self.idx = idx

    def run(self):
        try:
            r = httpx.get(self.url, timeout=10, follow_redirects=True)
            r.raise_for_status()
            pm = QPixmap()
            if pm.loadFromData(r.content):
                self.loaded.emit(self.idx, pm)
        except Exception:
            traceback.print_exc()


class ResultCard(QWidget):
    """Card de resultado de busca: thumbnail + título + duração + botão."""
    add_clicked = Signal(int)

    def __init__(self, entry, idx, parent=None):
        super().__init__(parent)
        self.idx = idx
        dur = entry.get("duration") or 0

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(120, 68)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(
            f"background: {C['card2']}; border-radius: 6px; color: {C['dim']};")
        self.thumb_label.setText("⋯")

        title = QLabel(entry["title"])
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600; color: %s;" % C["text"])

        dur_label = QLabel(f"⏱ {int(dur)//60}:{int(dur)%60:02d}")
        dur_label.setStyleSheet(f"color: {C['dim']}; font-size: 11px;")

        self.btn_add = QPushButton("＋")
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setObjectName("btnSide")
        self.btn_add.setToolTip("Adicionar à fila")
        self.btn_add.clicked.connect(lambda: self.add_clicked.emit(self.idx))

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(title)
        text_col.addWidget(dur_label)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)
        row.addWidget(self.thumb_label)
        row.addLayout(text_col, 1)
        row.addWidget(self.btn_add, 0, Qt.AlignTop)


class SearchPanel(QWidget):
    search_requested = Signal(str)
    add_result = Signal(int)
    url_submitted = Signal(str)
    files_selected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_workers = []

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar música no YouTube...")
        self.search_edit.returnPressed.connect(self._on_search)
        self.btn_search = QPushButton("Buscar")
        self.btn_search.clicked.connect(self._on_search)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.btn_search)

        self.results = QListWidget()
        self.results.setSpacing(4)
        self.results.itemDoubleClicked.connect(self._on_item_double)

        self.btn_add_result = QPushButton("＋ Adicionar selecionada à fila")
        self.btn_add_result.clicked.connect(self._on_add_selected)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Colar URL do YouTube (vídeo ou playlist)...")
        self.url_edit.returnPressed.connect(self._on_url)
        self.btn_url = QPushButton("Adicionar URL")
        self.btn_url.clicked.connect(self._on_url)

        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.btn_url)

        self.btn_local = QPushButton("＋ Arquivos locais...")
        self.btn_local.clicked.connect(self._on_files)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addLayout(search_row)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.btn_add_result)
        layout.addLayout(url_row)
        layout.addWidget(self.btn_local)
        self.results.setMinimumWidth(360)

    # ---------- sinais ----------
    def _on_search(self):
        q = self.search_edit.text().strip()
        if q:
            self.search_requested.emit(q)

    def _on_item_double(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.add_result.emit(idx)

    def _on_add_selected(self):
        item = self.results.currentItem()
        if item is not None:
            idx = item.data(Qt.UserRole)
            if idx is not None:
                self.add_result.emit(idx)

    def _on_url(self):
        u = self.url_edit.text().strip()
        if u:
            self.url_submitted.emit(u)
            self.url_edit.clear()

    def _on_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Escolher arquivos de áudio", "",
            "Áudio (*.mp3 *.wav *.ogg *.m4a *.flac *.opus *.aac);;Todos (*)")
        if files:
            self.files_selected.emit(files)

    # ---------- resultados ----------
    def show_results(self, entries):
        for w in self._thumb_workers:
            w.wait(20)
        self._thumb_workers = []
        self.results.clear()
        for i, e in enumerate(entries):
            card = ResultCard(e, i)
            card.add_clicked.connect(self.add_result)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, i)
            item.setSizeHint(card.minimumSizeHint().expandedTo(QSize(0, 76)))
            self.results.addItem(item)
            self.results.setItemWidget(item, card)
            thumb = e.get("thumbnail") or ""
            if thumb:
                worker = ThumbnailWorker(thumb, i, self)
                worker.loaded.connect(self._on_thumb)
                self._thumb_workers.append(worker)
                worker.start()

    def _on_thumb(self, idx, pixmap):
        item = self.results.item(idx)
        if item is None:
            return
        widget = self.results.itemWidget(item)
        if widget is not None and hasattr(widget, "thumb_label"):
            widget.thumb_label.setPixmap(
                pixmap.scaled(120, 68, Qt.KeepAspectRatio,
                              Qt.SmoothTransformation))

    def set_searching(self, on):
        self.btn_search.setEnabled(not on)
        self.btn_search.setText("Buscando..." if on else "Buscar")

    def set_status(self, msg):
        self.search_edit.setPlaceholderText(msg)
