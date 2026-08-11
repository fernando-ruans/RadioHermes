"""Busca e download via yt-dlp com cache em disco."""
import subprocess
import json
import os
from .proc import run_hidden


def extract_video_id(url):
    """Extrai o ID de um vídeo do YouTube a partir de qualquer formato de URL."""
    for marker in ("youtu.be/", "v=", "/shorts/"):
        idx = url.find(marker)
        if idx != -1:
            start = idx + len(marker)
            end = url.find("&", start)
            if end == -1:
                end = url.find("?", start)
            if end == -1:
                end = len(url)
            return url[start:end]
    return None


def clean_video_url(url):
    """Remove parâmetros de playlist (list/index) de uma URL de vídeo,
    mantendo só o essencial (v= ou youtu.be/). Evita que o yt-dlp confunda
    uma recomendação ('&list=RD...') com uma playlist real."""
    vid = extract_video_id(url)
    if not vid:
        return url
    if "youtu.be/" in url:
        return f"https://youtu.be/{vid}"
    return f"https://www.youtube.com/watch?v={vid}"


def extract_playlist_id(url):
    """Extrai o ID de uma playlist (list=...) da URL, se houver."""
    for marker in ("list=",):
        idx = url.find(marker)
        if idx != -1:
            start = idx + len(marker)
            end = url.find("&", start)
            if end == -1:
                end = len(url)
            pid = url[start:end]
            if pid:
                return pid
    return None


class Fetcher:
    def __init__(self, cfg):
        cache = cfg["cache"]
        self.cache_dir = cache["dir"]
        self.max_duration = cache.get("max_duration_sec", 900)
        self.min_duration = cache.get("min_duration_sec", 15)
        self.dl_timeout = cache.get("download_timeout_sec", 240)
        os.makedirs(self.cache_dir, exist_ok=True)

    def search(self, query, n=8):
        """Pesquisa no YouTube e devolve [{id,title,duration,url,thumbnail}]."""
        out = run_hidden(
            ["yt-dlp", "-J", "--no-playlist", "--flat-playlist",
             "--match-filter", "live_status != is_live",
             f"ytsearch{n}:{query}"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            raise RuntimeError("yt-dlp falhou: " + out.stderr[-300:])
        data = json.loads(out.stdout)
        res = []
        for e in (data.get("entries") or []):
            if e.get("id"):
                th = e.get("thumbnails") or []
                # pega a thumbnail de melhor resolução
                thumb = th[-1].get("url", "") if th else ""
                res.append({
                    "id": e["id"],
                    "title": e.get("title") or "sem título",
                    "duration": e.get("duration") or 0,
                    "url": f"https://www.youtube.com/watch?v={e['id']}",
                    "thumbnail": thumb,
                })
        return res

    def extract_playlist(self, url):
        """Extrai as músicas de uma playlist do YouTube.
        Devolve [{id,title,duration,url}]. Entradas com duration <= 0 ou
        desconhecida são incluídas (o download aplica o filtro de duração)."""
        out = run_hidden(
            ["yt-dlp", "-J", "--flat-playlist", "--no-playlist",
             "--match-filter", "live_status != is_live", url],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            raise RuntimeError("yt-dlp falhou: " + out.stderr[-300:])
        data = json.loads(out.stdout)
        res = []
        for e in (data.get("entries") or []):
            if e.get("id") and e.get("_type") != "playlist":
                res.append({
                    "id": e["id"],
                    "title": e.get("title") or "sem título",
                    "duration": e.get("duration") or 0,
                    "url": f"https://www.youtube.com/watch?v={e['id']}",
                })
        return res

    def info(self, url):
        """Pega metadados de uma URL direta (título/duração/id)."""
        out = run_hidden(
            ["yt-dlp", "-J", "--no-playlist", url],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            raise RuntimeError("yt-dlp falhou: " + out.stderr[-300:])
        d = json.loads(out.stdout)
        return {
            "id": d.get("id"),
            "title": d.get("title") or "sem título",
            "duration": d.get("duration") or 0,
            "url": d.get("webpage_url") or url,
        }

    def download(self, url, out_path):
        """Baixa o áudio de um vídeo e converte pra MP3 em out_path."""
        run_hidden(
            ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
             "--no-playlist", "--force-overwrites", "-o", out_path,
             "--match-filter",
             f"duration < {self.max_duration} & duration > {self.min_duration}",
             url],
            capture_output=True, text=True, timeout=self.dl_timeout,
        )
        if not os.path.exists(out_path):
            raise RuntimeError("yt-dlp não gerou o áudio (live/restrito?)")
        return out_path
