"""Preparação de uma faixa: baixa/normaliza a música, gera as locuções
(intro/meio/outro) e monta o MP3 final via concatenação.
"""
import asyncio
import datetime
import hashlib
import os
import random
import shutil
import tempfile

from .probe import duration
from . import mixer


def time_context():
    """Contexto temporal natural, sempre coerente com a hora real."""
    now = datetime.datetime.now()
    h = now.hour
    if 5 <= h < 12:
        period = "da manhã"
    elif 12 <= h < 18:
        period = "da tarde"
    elif 18 <= h < 24:
        period = "da noite"
    else:
        period = "da madrugada"
    return {
        "hour": str(h),
        "minute": f"{now.minute:02d}",
        "period": period,
        "weekday": ["segunda", "terça", "quarta", "quinta",
                    "sexta", "sábado", "domingo"][now.weekday()],
    }


class Preparer:
    def __init__(self, cfg, brain, tts, fetcher):
        self.cfg = cfg
        self.brain = brain
        self.tts = tts
        self.fetcher = fetcher
        cache = cfg["cache"]
        self.prep_dir = cache.get("prep_dir", os.path.join(cache["dir"], "prep"))
        os.makedirs(self.prep_dir, exist_ok=True)

    def cache_key(self, item):
        """Chave estável do preparado: vid do YouTube ou hash do caminho local.
        Assim, readicionar a mesma música reusa o MP3 já montado.
        Aceita dict (item.to_dict()) ou objeto Track."""
        def get(k):
            if isinstance(item, dict):
                return item.get(k)
            return getattr(item, k, None)
        if get("source") == "youtube" and get("vid"):
            return get("vid")
        if get("path"):
            return hashlib.sha256(str(get("path")).encode("utf-8")).hexdigest()[:16]
        title = get("title")
        return hashlib.sha256(str(title or "").encode("utf-8")).hexdigest()[:16]

    def prepared_file(self, item):
        return os.path.join(self.prep_dir, f"{self.cache_key(item)}.mp3")

    def prepare(self, item, status_cb):
        """Executa a preparação completa (síncrono — roda numa thread)."""
        return asyncio.run(self._prepare(item, status_cb))

    async def _prepare(self, item, status_cb):
        loc = self.cfg.get("locucao", {})
        audio = self.cfg["audio"]
        tc = time_context()
        max_dur = {
            "intro": loc.get("max_dur_intro_sec", 8),
            "mid": loc.get("max_dur_mid_sec", 5),
            "outro": loc.get("max_dur_outro_sec", 8),
        }
        tmp = tempfile.mkdtemp(prefix="rh_prep_")
        try:
            # 1) origem da música
            if item["source"] == "youtube":
                status_cb("baixando")
                raw = os.path.join(self.fetcher.cache_dir, f"{item['vid']}.mp3")
                if not os.path.exists(raw):
                    self.fetcher.download(item["url"], raw)
                music_in = raw
            else:
                music_in = item["path"]

            # 2) normalizar música
            status_cb("normalizando")
            music_norm = os.path.join(tmp, "music.mp3")
            mixer.normalize(music_in, music_norm, self.cfg)
            music_dur = duration(music_norm)

            # 3) locução de abertura (sempre, se habilitada)
            intro_norm = None
            if loc.get("intro_enabled", True):
                status_cb("locução de abertura")
                text = await self.brain.announce({
                    "kind": "intro", "title": item["title"],
                    "max_dur_sec": max_dur["intro"], **tc})
                intro_norm = await self._tts_to_canonical(text, tmp, "intro")

            # 4) locução no meio (às vezes, com ducking pre-processado)
            mid_parts = None
            mid_enabled = loc.get("mid_enabled", True)
            mid_chance = loc.get("mid_chance", 0.4)
            mid_min_sec = loc.get("mid_min_sec", 60)
            if (mid_enabled and music_dur >= mid_min_sec
                    and random.random() < mid_chance):
                status_cb("locução no meio")
                text = await self.brain.announce({
                    "kind": "mid", "title": item["title"],
                    "max_dur_sec": max_dur["mid"], **tc})
                mid_norm = await self._tts_to_canonical(text, tmp, "mid")
                mid_dur = duration(mid_norm)
                lo = max(mid_min_sec, music_dur * 0.3)
                hi = music_dur - mid_dur - 1.0
                mid_start = random.uniform(lo, hi) if hi > lo else lo
                seg_a = os.path.join(tmp, "m_a.mp3")
                mixer.segment(music_norm, 0, mid_start, seg_a, self.cfg)
                duck = os.path.join(tmp, "m_duck.mp3")
                mixer.mix_duck(music_norm, mid_start, mid_norm,
                               audio["duck_gain_db"], duck, self.cfg)
                seg_b = os.path.join(tmp, "m_b.mp3")
                mixer.segment(music_norm, mid_start + mid_dur,
                              music_dur - (mid_start + mid_dur), seg_b, self.cfg)
                mid_parts = [seg_a, duck, seg_b]

            # 5) locução de encerramento (sempre, se habilitada)
            outro_norm = None
            if loc.get("outro_enabled", True):
                status_cb("locução de encerramento")
                text = await self.brain.announce({
                    "kind": "outro", "title": item["title"],
                    "max_dur_sec": max_dur["outro"], **tc})
                outro_norm = await self._tts_to_canonical(text, tmp, "outro")

            # 6) montar arquivo final
            status_cb("montando")
            parts = []
            if intro_norm:
                parts.append(intro_norm)
            parts.extend(mid_parts if mid_parts else [music_norm])
            if outro_norm:
                parts.append(outro_norm)
            out = self.prepared_file(item)
            mixer.concat_segments(parts, out, self.cfg)
            total = duration(out)
            status_cb("pronto")
            return {"prepared_file": out, "total_duration": total,
                    "music_duration": music_dur}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def _tts_to_canonical(self, text, tmp, tag):
        raw = os.path.join(tmp, f"{tag}_raw.mp3")
        await self.tts.speak(text, raw)
        norm = os.path.join(tmp, f"{tag}.mp3")
        mixer.normalize(raw, norm, self.cfg)
        return norm
