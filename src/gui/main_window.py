"""Janela principal: junta player, fila, busca e configurações."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMainWindow, QSplitter, QStatusBar,
                               QVBoxLayout, QWidget)

from .player_bar import PlayerBar
from .playlist import PlaylistWidget
from .search import SearchPanel
from .settings import SettingsDialog
from ..engine import Engine, Track
from ..fetcher import (clean_video_url, extract_playlist_id, extract_video_id)
from ..brain import Brain
from ..prepare import Preparer
from ..workers import InfoWorker, PlaylistWorker, SearchWorker

# Vozes pt-BR do edge-tts
PT_BR_VOICES = ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"]


class MainWindow(QMainWindow):
    def __init__(self, cfg, preparer, fetcher, config_path=None):
        super().__init__()
        self.cfg = cfg
        self.preparer = preparer
        self.fetcher = fetcher
        self._config_path = config_path
        self.search_worker = None
        self.playlist_worker = None
        self.last_search = []

        self.engine = Engine(cfg, preparer, self)
        self._build_ui()
        self._connect_engine()
        self._connect_actions()

    # ---------- UI ----------
    def _build_ui(self):
        self.setWindowTitle(self.cfg.get("app", {}).get("name", "Rádio Hermes"))
        self.resize(1000, 620)

        self.player_bar = PlayerBar()
        self.playlist = PlaylistWidget()
        self.search = SearchPanel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.search)
        splitter.addWidget(self.playlist)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 640])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.player_bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        if self._config_path and os.path.basename(self._config_path) == "config.example.toml":
            self.statusBar.showMessage(
                "Modo exemplo (sem chaves): copie config.example.toml para "
                "config.toml e configure sua IA nas Configurações.", 8000)
        else:
            self.statusBar.showMessage("Pronto")

        # menu
        m = self.menuBar()
        cfg_menu = m.addMenu("Configurações")
        act_settings = cfg_menu.addAction("Configurações...")
        act_settings.triggered.connect(self._open_settings)
        act_quit = cfg_menu.addAction("Sair")
        act_quit.triggered.connect(self.close)

        self.player_bar.set_voice(
            self.cfg["voice"].get("voice", PT_BR_VOICES[0]))

    # ---------- engine ----------
    def _connect_engine(self):
        self.player_bar.toggle.connect(self.engine.toggle_play)
        self.player_bar.next_track.connect(self.engine.next)
        self.player_bar.prev_track.connect(self.engine.prev)
        self.player_bar.seek.connect(self.engine.seek)
        self.player_bar.volume_changed.connect(self.engine.set_volume)
        self.player_bar.voice_toggled.connect(self._toggle_voice)

        self.engine.position_changed.connect(self.player_bar.set_progress)
        self.engine.state_changed.connect(self._on_state)
        self.engine.queue_changed.connect(self._on_queue_changed)
        self.engine.current_changed.connect(self._on_current)
        self.engine.track_status_changed.connect(self._on_track_status)
        self.engine.error.connect(self._on_error)

    def _connect_actions(self):
        self.playlist.play_requested.connect(self.engine.play_index)
        self.playlist.remove_requested.connect(self.engine.remove_at)
        self.playlist.files_dropped.connect(self._add_local_files)

        self.search.search_requested.connect(self._on_search)
        self.search.add_result.connect(self._on_add_result)
        self.search.url_submitted.connect(self._on_url)
        self.search.files_selected.connect(self._add_local_files)

    # ---------- handlers ----------
    def _toggle_voice(self):
        """Alterna entre as vozes pt-BR e aplica imediatamente no TTS."""
        current = self.cfg["voice"].get("voice", PT_BR_VOICES[0])
        nxt = PT_BR_VOICES[1] if current == PT_BR_VOICES[0] else PT_BR_VOICES[0]
        self.cfg["voice"]["voice"] = nxt
        self.preparer.tts.voice = nxt
        self.player_bar.set_voice(nxt)
        label = "Francisca ♀" if "Francisca" in nxt else "Antonio ♂"
        self.statusBar.showMessage(f"Voz alterada para {label} "
                                   "(vale para as próximas locuções).", 4000)

    def _on_search(self, query):
        self.search.set_searching(True)
        self.search.set_status(f"Buscando '{query}'...")
        if self.search_worker is not None and self.search_worker.isRunning():
            self.search_worker.wait(100)
        self.search_worker = SearchWorker(self.fetcher, query, 8, self)
        self.search_worker.results.connect(self._on_search_results)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_results(self, entries):
        self.search.set_searching(False)
        self.search.set_status("Buscar música no YouTube...")
        self.last_search = entries
        self.search.show_results(entries)
        if not entries:
            self.statusBar.showMessage("Nenhum resultado encontrado.", 4000)

    def _on_search_error(self, err):
        self.search.set_searching(False)
        self.search.set_status("Buscar música no YouTube...")
        self._on_error(f"Busca falhou: {err}")

    def _on_add_result(self, idx):
        if 0 <= idx < len(self.last_search):
            e = self.last_search[idx]
            self._add_youtube(e["url"], e["title"])

    def _on_url(self, url):
        # URL com v= (vídeo avulso) é SEMPRE vídeo, mesmo que venha com
        # &list=...&index=... (recomendações coladas da barra do navegador).
        # Só vira playlist quando tem list= sem v= (ex: youtube.com/playlist).
        if extract_video_id(url):
            self._add_youtube(url, None)
        elif extract_playlist_id(url):
            self._add_playlist(url)
        else:
            self._on_error("Não reconheci essa URL do YouTube.")

    def _add_playlist(self, url):
        if self.playlist_worker is not None and self.playlist_worker.isRunning():
            self.statusBar.showMessage("Já estou lendo uma playlist, aguarde...", 3000)
            return
        self.statusBar.showMessage("Lendo playlist do YouTube...", 4000)
        self.playlist_worker = PlaylistWorker(self.fetcher, url, self)
        self.playlist_worker.done.connect(self._on_playlist_done)
        self.playlist_worker.error.connect(self._on_playlist_error)
        self.playlist_worker.start()

    def _on_playlist_done(self, entries):
        if not entries:
            self.statusBar.showMessage("Playlist vazia ou sem faixas válidas.", 4000)
            return
        tracks = [Track("youtube", e["title"], vid=e["id"], url=e["url"])
                  for e in entries]
        self.engine.add_tracks(tracks)
        self.statusBar.showMessage(
            f"Playlist adicionada: {len(tracks)} faixa(s) na fila.", 5000)

    def _on_playlist_error(self, err):
        self.statusBar.showMessage(f"Falha ao ler playlist: {err}", 6000)

    def _add_youtube(self, url, title):
        """Adiciona um vídeo do YouTube sem travar a UI: já extrai o vid da
        URL na hora (o cache funciona de imediato) e o título/duração exatos
        chegam em background pelo InfoWorker."""
        url = clean_video_url(url)
        vid = extract_video_id(url)
        track = Track("youtube", title or "Carregando...",
                      vid=vid or None, url=url)
        self.engine.add_track(track)
        self.statusBar.showMessage(f"Adicionada: {track.title}", 4000)
        if title is None:
            self._fetch_info(track)

    def _fetch_info(self, track):
        worker = InfoWorker(self.fetcher, track.url, self)
        worker.done.connect(lambda info, t=track: self._on_info_done(t, info))
        worker.error.connect(
            lambda err, t=track: self._on_error(f"Falha ao ler a URL: {err}"))
        worker.start()

    def _on_info_done(self, track, info):
        track.title = info["title"] or track.title
        if not track.vid:
            track.vid = info["id"]
        if info["url"]:
            track.url = info["url"]
        # reavalia cache/preparação (vid agora pode bater com arquivo existente)
        self.engine._schedule_preparation()
        self.queue_changed_refresh()

    def queue_changed_refresh(self):
        self.playlist.refresh(self.engine.queue)
        if 0 <= self.engine.current < len(self.engine.queue):
            cur = self.engine.queue[self.engine.current]
            self.player_bar.set_track(cur.title)

    def _add_local_files(self, paths):
        added = 0
        for p in paths:
            if not os.path.isfile(p):
                continue
            name = os.path.basename(p)
            track = Track("local", name, path=p)
            self.engine.add_track(track)
            added += 1
        if added:
            self.statusBar.showMessage(f"{added} arquivo(s) adicionado(s).", 4000)

    # ---------- engine callbacks ----------
    def _on_state(self, state):
        self.player_bar.set_playing(state == "playing")

    def _on_queue_changed(self):
        self.playlist.refresh(self.engine.queue)

    def _on_current(self, idx):
        if 0 <= idx < len(self.engine.queue):
            self.player_bar.set_track(self.engine.queue[idx].title)

    def _on_track_status(self, item_id, label):
        for i, t in enumerate(self.engine.queue):
            if t.id == item_id:
                item = self.playlist.item(i)
                if item is not None:
                    item.setText(self.playlist._fmt(t))
                break

    def _on_error(self, msg):
        self.statusBar.showMessage(msg, 6000)
        print("[app]", msg)

    # ---------- settings ----------
    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            dlg.apply()
            import tomli_w
            with open(self._config_path or "config.toml", "wb") as f:
                tomli_w.dump(self.cfg, f)
            self.engine.set_volume(self.cfg["player"].get("volume", 0.8))
            # recria brain/preparer com a nova config (vale pras próximas faixas)
            brain = Brain(self.cfg)
            self.preparer.brain = brain
            self.statusBar.showMessage(
                "Configurações salvas. Aplicam-se às próximas faixas.", 5000)

    def closeEvent(self, e):
        self.engine.player.stop()
        for t in self.engine.queue:
            w = self.engine._workers.get(t.id)
            if w is not None and w.isRunning():
                w.wait(200)
        super().closeEvent(e)
