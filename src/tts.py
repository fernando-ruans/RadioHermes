"""Locução via edge-tts (pt-BR natural, grátis, sem chave).
Se a rede do TTS cair, degrada para um tom placeholder."""
import asyncio
import subprocess
import edge_tts
from .probe import duration
from .proc import run_hidden


class TTS:
    def __init__(self, cfg):
        v = cfg["voice"]
        self.voice = v["voice"]
        self.rate = v.get("rate", "+0%")
        self.volume = v.get("volume", "+0%")

    async def speak(self, text, out_path):
        try:
            comm = edge_tts.Communicate(
                text, self.voice, rate=self.rate, volume=self.volume
            )
            await comm.save(out_path)
            return out_path, duration(out_path)
        except Exception as e:
            print(f"[tts] edge-tts falhou ({e}); usando tom placeholder.")
            secs = max(3.0, min(12.0, len(text) * 0.07))
            run_hidden(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i", f"sine=frequency=220:duration={secs:.1f}",
                 "-ar", "44100", "-ac", "2", "-b:a", "128k", out_path],
                capture_output=True,
            )
            return out_path, duration(out_path)
