"""Mixagem com ffmpeg: normalização, cortes, ducking e concatenação."""
import subprocess
import os
from .probe import duration
from .proc import run_hidden


def _run(cmd):
    r = run_hidden(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + r.stderr[-500:])
    return r


def _audio_args(cfg):
    a = cfg["audio"]
    return str(a["sample_rate"]), str(a["channels"]), a["bitrate"]


def normalize(in_path, out_path, cfg):
    """Transcoda pra MP3 canônico (44100Hz/2ch/bitrate, SEM tags)."""
    ar, ac, br = _audio_args(cfg)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", in_path,
           "-map_metadata", "-1", "-write_id3v1", "0", "-id3v2_version", "0",
           "-ar", ar, "-ac", ac, "-b:a", br, "-f", "mp3", out_path]
    _run(cmd)
    return out_path


def segment(music_path, start, dur, out_path, cfg):
    """Corta um trecho da música (canônico)."""
    ar, ac, br = _audio_args(cfg)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", music_path,
           "-map_metadata", "-1", "-write_id3v1", "0", "-id3v2_version", "0",
           "-ar", ar, "-ac", ac, "-b:a", br, "-f", "mp3", out_path]
    _run(cmd)
    return out_path


def mix_duck(music_path, music_offset, tts_path, duck_gain_db, out_path, cfg):
    """Música abaixada em duck_gain_db + locução, pela duração da voz.
    Retorna (out_path, tts_dur)."""
    ar, ac, br = _audio_args(cfg)
    tts_dur = duration(tts_path)
    bed = (f"[0:a]atrim=start={music_offset:.3f}:duration={tts_dur:.3f},"
           f"volume={duck_gain_db:.1f}dB[bed]")
    filt = (bed + ";" +
            f"[1:a]volume=1[sp];" +
            f"[bed][sp]amix=inputs=2:duration=shortest:dropout_transition=0[aout]")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", music_path, "-i", tts_path,
           "-filter_complex", filt,
           "-map", "[aout]", "-map_metadata", "-1",
           "-write_id3v1", "0", "-id3v2_version", "0",
           "-ar", ar, "-ac", ac, "-b:a", br, "-f", "mp3", out_path]
    _run(cmd)
    return out_path, tts_dur


def concat_segments(paths, out_path, cfg):
    """Concatena vários MP3 canônicos com -c copy (rápido)."""
    ar, ac, br = _audio_args(cfg)
    list_path = out_path + ".txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            esc = p.replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{esc}'\n")
    try:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "concat", "-safe", "0", "-i", list_path,
               "-map_metadata", "-1", "-write_id3v1", "0", "-id3v2_version", "0",
               "-ar", ar, "-ac", ac, "-b:a", br, "-c", "copy",
               "-f", "mp3", out_path]
        _run(cmd)
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass
    return out_path
