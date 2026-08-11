"""Motor de playback: fila, reprodução via QMediaPlayer, preparo em background
e auto-avanço. O áudio de cada faixa é um MP3 final montado com as locuções
(intro + música [+ ducking no meio] + outro)."""
import os
import uuid
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from .workers import TrackWorker


class Track:
    def __init__(self, source, title, vid=None, url=None, path=None):
        self.id = uuid.uuid4().hex
        self.source = source          # "youtube" | "local"
        self.title = title
        self.vid = vid
        self.url = url
        self.path = path
        self.status = "queued"        # queued|working|ready|error
        self.progress = ""
        self.prepared_file = None
        self.total_duration = 0.0
        self.music_duration = 0.0
        self.error = ""

    def to_dict(self):
        return {
            "id": self.id, "source": self.source, "title": self.title,
            "vid": self.vid, "url": self.url, "path": self.path,
            "status": self.status, "progress": self.progress,
            "prepared_file": self.prepared_file,
            "total_duration": self.total_duration,
            "music_duration": self.music_duration, "error": self.error,
        }


class Engine(QObject):
    queue_changed = Signal()
    current_changed = Signal(int)             # índice ou -1
    state_changed = Signal(str)               # stopped|playing|paused
    position_changed = Signal(int, int)       # pos_ms, dur_ms
    track_status_changed = Signal(str, str)   # id, rótulo
    error = Signal(str)

    def __init__(self, cfg, preparer, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.preparer = preparer
        self.queue = []
        self.current = -1
        self._workers = {}
        self._auto_next = cfg["player"].get("auto_next", True)
        self._pending_index = None

        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(cfg["player"].get("volume", 0.8))

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_playback_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_player_error)

    # ---------- fila ----------
    def add_track(self, track):
        self.queue.append(track)
        self._schedule_preparation()
        self.queue_changed.emit()

    def add_tracks(self, tracks):
        self.queue.extend(tracks)
        self._schedule_preparation()
        self.queue_changed.emit()

    def remove_at(self, idx):
        if idx < 0 or idx >= len(self.queue):
            return
        track = self.queue.pop(idx)
        worker = self._workers.pop(track.id, None)
        if worker is not None:
            worker.wait(50)
        if self.current == idx:
            self.player.stop()
            self.current = -1
            self.current_changed.emit(-1)
        elif self.current > idx:
            self.current -= 1
        if self._pending_index is not None:
            if self._pending_index == idx:
                self._pending_index = None
            elif self._pending_index > idx:
                self._pending_index -= 1
        self._schedule_preparation()
        self.queue_changed.emit()

    def move(self, src, dst):
        if src < 0 or src >= len(self.queue) or dst < 0 or dst >= len(self.queue):
            return
        track = self.queue.pop(src)
        self.queue.insert(dst, track)
        if self.current == src:
            self.current = dst
        elif src < self.current <= dst:
            self.current -= 1
        elif dst <= self.current < src:
            self.current += 1
        if self._pending_index is not None:
            if self._pending_index == src:
                self._pending_index = dst
            elif src < self._pending_index <= dst:
                self._pending_index -= 1
            elif dst <= self._pending_index < src:
                self._pending_index += 1
        self.queue_changed.emit()

    def clear(self):
        for track in self.queue:
            worker = self._workers.pop(track.id, None)
            if worker is not None:
                worker.wait(50)
        self.player.stop()
        self.queue = []
        self.current = -1
        self._pending_index = None
        self.queue_changed.emit()
        self.current_changed.emit(-1)

    # ---------- preparação em background ----------
    def _schedule_preparation(self):
        """Prepara TODAS as faixas 'queued' da fila, até o limite de workers
        simultâneos. Prioriza: pendente > próximo do atual > resto da fila.
        Faixas cujo MP3 já existe no cache de preparados viram 'ready' na hora."""
        active = len(self._workers)
        limit = self.cfg["player"].get("prefetch", 2)

        def priority(i):
            if self._pending_index is not None and i == self._pending_index:
                return 0
            if self.current >= 0 and i == self.current + 1:
                return 1
            if self.current >= 0 and i > self.current:
                return 2 + (i - self.current)
            if i == 0 and self.current < 0:
                return 0
            return 10 + i

        indexes = sorted(range(len(self.queue)), key=priority)

        # 1) reaproveita arquivos já montados no cache
        for i in indexes:
            track = self.queue[i]
            if track.status != "queued":
                continue
            cached = self.preparer.prepared_file(track)
            if os.path.exists(cached):
                track.status = "ready"
                track.progress = "pronto (cache)"
                track.prepared_file = cached
                self.track_status_changed.emit(track.id, "pronto (cache)")
                self.queue_changed.emit()

        # 2) dispara workers para as queued restantes, até o limite
        for i in indexes:
            if active >= limit:
                break
            track = self.queue[i]
            if track.status == "queued":
                self._start_worker(track)
                active += 1

    def _start_worker(self, track):
        track.status = "working"
        worker = TrackWorker(track, self.preparer, self)
        worker.status.connect(self._on_worker_status)
        worker.done.connect(self._on_worker_done)
        worker.failed.connect(self._on_worker_failed)
        self._workers[track.id] = worker
        self._emit_status(track.id, "preparando...")
        worker.start()

    def _on_worker_status(self, item_id, label):
        self._emit_status(item_id, label)

    def _emit_status(self, item_id, label):
        track = self._find(item_id)
        if track:
            track.progress = label
            self.track_status_changed.emit(item_id, label)

    def _on_worker_done(self, item_id, result):
        track = self._find(item_id)
        worker = self._workers.pop(item_id, None)
        if track is None:
            return
        track.status = "ready"
        track.progress = "pronto"
        track.prepared_file = result["prepared_file"]
        track.total_duration = result["total_duration"]
        track.music_duration = result["music_duration"]
        self.track_status_changed.emit(item_id, "pronto")
        # se era o item pendente, inicia a reprodução
        if (self._pending_index is not None
                and self._pending_index < len(self.queue)
                and self.queue[self._pending_index].id == item_id):
            self._play_pending()
        # sempre encadeia a próxima faixa que esteja 'queued'
        self._schedule_preparation()
        self.queue_changed.emit()

    def _on_worker_failed(self, item_id, err):
        track = self._find(item_id)
        self._workers.pop(item_id, None)
        if track is None:
            return
        track.status = "error"
        track.progress = "erro"
        track.error = err
        self.track_status_changed.emit(item_id, "erro: " + err[:40])
        self.error.emit(f"Falha ao preparar '{track.title}': {err}")
        self._schedule_preparation()
        self.queue_changed.emit()

    def _find(self, item_id):
        for t in self.queue:
            if t.id == item_id:
                return t
        return None

    # ---------- controle ----------
    def play_index(self, idx):
        if idx < 0 or idx >= len(self.queue):
            return
        self._pending_index = idx
        self.current = idx
        track = self.queue[idx]
        self.current_changed.emit(idx)
        # se já existe MP3 montado no cache (mesma música readicionada),
        # usa direto sem esperar o worker
        cached = self.preparer.prepared_file(track)
        if track.status == "ready" and track.prepared_file and os.path.exists(track.prepared_file):
            self._play_file(track)
        elif os.path.exists(cached):
            track.status = "ready"
            track.progress = "pronto (cache)"
            track.prepared_file = cached
            self.track_status_changed.emit(track.id, "pronto (cache)")
            self._play_file(track)
        else:
            self.player.stop()
            self._emit_status(track.id, track.progress or "preparando...")
            self._schedule_preparation()
            self._pending_index = idx

    def _play_pending(self):
        if self._pending_index is None:
            return
        idx = self._pending_index
        if idx < 0 or idx >= len(self.queue):
            return
        track = self.queue[idx]
        if track.status == "ready" and track.prepared_file and os.path.exists(track.prepared_file):
            self._play_file(track)
        self._pending_index = None

    def _play_file(self, track):
        self.player.setSource(QUrl.fromLocalFile(track.prepared_file))
        self.player.play()
        self.current_changed.emit(self.current)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.current < 0 and self.queue:
                self.play_index(0)
            elif self.current >= 0 and (not self.player.source().isValid()):
                self.play_index(self.current)
            else:
                self.player.play()

    def next(self):
        if not self.queue:
            return
        idx = self.current + 1 if self.current >= 0 else 0
        if idx >= len(self.queue):
            if self._auto_next and self.cfg["player"].get("loop", True):
                idx = 0
            else:
                self.player.stop()
                return
        self.play_index(idx)

    def prev(self):
        if not self.queue:
            return
        if self.current < 0:
            return
        if self.player.position() > 5000:
            self.player.setPosition(0)
            return
        idx = self.current - 1
        if idx < 0:
            idx = len(self.queue) - 1 if self.cfg["player"].get("loop", True) else 0
        self.play_index(idx)

    def stop(self):
        self.player.stop()

    def seek(self, ms):
        self.player.setPosition(ms)

    def set_volume(self, v):
        self.audio_out.setVolume(v)

    # ---------- signals do player ----------
    def _on_position(self, pos):
        self.position_changed.emit(pos, self.player.duration())

    def _on_duration(self, dur):
        self.position_changed.emit(self.player.position(), dur)

    def _on_playback_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.state_changed.emit("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.state_changed.emit("paused")
        else:
            self.state_changed.emit("stopped")

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._auto_next:
                self.next()
            else:
                self.player.stop()

    def _on_player_error(self, error, error_string):
        self.error.emit(f"Erro de reprodução: {error_string}")
