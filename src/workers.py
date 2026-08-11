"""Workers em threads para tarefas pesadas (preparação de faixas e busca)."""
import traceback
from PySide6.QtCore import QThread, Signal


class TrackWorker(QThread):
    status = Signal(str, str)   # item_id, rótulo de progresso
    done = Signal(str, dict)    # item_id, resultado
    failed = Signal(str, str)   # item_id, erro

    def __init__(self, item, preparer, parent=None):
        super().__init__(parent)
        self.item = item
        self.preparer = preparer

    def run(self):
        try:
            result = self.preparer.prepare(
                self.item.to_dict(), self._emit_status)
            self.done.emit(self.item.id, result)
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(self.item.id, str(e))

    def _emit_status(self, label):
        self.status.emit(self.item.id, label)


class SearchWorker(QThread):
    results = Signal(list)
    error = Signal(str)

    def __init__(self, fetcher, query, n=8, parent=None):
        super().__init__(parent)
        self.fetcher = fetcher
        self.query = query
        self.n = n

    def run(self):
        try:
            self.results.emit(self.fetcher.search(self.query, self.n))
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class PlaylistWorker(QThread):
    done = Signal(list)     # lista de entries
    error = Signal(str)

    def __init__(self, fetcher, url, parent=None):
        super().__init__(parent)
        self.fetcher = fetcher
        self.url = url

    def run(self):
        try:
            self.done.emit(self.fetcher.extract_playlist(self.url))
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class InfoWorker(QThread):
    done = Signal(dict)     # info do vídeo
    error = Signal(str)

    def __init__(self, fetcher, url, parent=None):
        super().__init__(parent)
        self.fetcher = fetcher
        self.url = url

    def run(self):
        try:
            self.done.emit(self.fetcher.info(self.url))
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))
