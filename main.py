"""Ponto de entrada do Rádio Hermes Desktop."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.config import load_config
from src.brain import Brain
from src.tts import TTS
from src.fetcher import Fetcher
from src.prepare import Preparer
from src.gui.main_window import MainWindow
from src.gui.styles import apply_theme


def find_config():
    """Procura config.toml: env var, diretório atual, ao lado do executável
    (funciona mesmo lançado de outro diretório) e dentro do pacote.
    Se não existir, cai para config.example.toml (roda zero-config, modo
    template — sem chave de API)."""
    candidates = [
        os.environ.get("RADIO_HERMES_CONFIG"),
        os.path.join(os.getcwd(), "config.toml"),
        os.path.join(os.path.dirname(sys.executable), "config.toml"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml"),
    ]
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "config.toml"))
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    # fallback: exemplo (sem chaves, modo template)
    fallback = [
        os.path.join(os.getcwd(), "config.example.toml"),
        os.path.join(os.path.dirname(sys.executable), "config.example.toml"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "config.example.toml"),
    ]
    if getattr(sys, "frozen", False):
        fallback.append(os.path.join(sys._MEIPASS, "config.example.toml"))
    for p in fallback:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError(
        "config.toml não encontrado. Copie config.example.toml para config.toml "
        "e ajuste suas chaves, ou defina RADIO_HERMES_CONFIG.")


def main():
    config_path = find_config()
    cfg = load_config(config_path)
    _resolve_relative_paths(cfg, os.path.dirname(os.path.abspath(config_path)))

    app = QApplication(sys.argv)
    app.setApplicationName(cfg.get("app", {}).get("name", "Rádio Hermes"))
    app.setStyle("Fusion")
    apply_theme(app)

    icon = _load_icon()
    if icon:
        app.setWindowIcon(icon)

    brain = Brain(cfg)
    tts = TTS(cfg)
    fetcher = Fetcher(cfg)
    preparer = Preparer(cfg, brain, tts, fetcher)

    win = MainWindow(cfg, preparer, fetcher, config_path=config_path)
    win.show()
    sys.exit(app.exec())


def _resolve_relative_paths(cfg, base):
    """Torna caminhos relativos do config absolutos em relação à pasta do
    config (assim o app não espalha cache pelo diretório onde for aberto)."""
    cache = cfg.get("cache", {})
    for key in ("dir", "prep_dir"):
        if cache.get(key) and not os.path.isabs(cache[key]):
            cache[key] = os.path.join(base, cache[key])


def _load_icon():
    """Carrega a logo (assets/logo.png) como ícone do app, inclusive quando
    empacotado (procura dentro de sys._MEIPASS)."""
    bases = [os.path.dirname(os.path.abspath(__file__))]
    if getattr(sys, "frozen", False):
        bases.insert(0, sys._MEIPASS)
    for base in bases:
        path = os.path.join(base, "assets", "logo.png")
        if os.path.exists(path):
            return QIcon(path)
    return None


if __name__ == "__main__":
    main()
