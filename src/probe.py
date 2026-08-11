"""Helpers de ffprobe para duração de áudio."""
import subprocess
import json
from .proc import run_hidden


def duration(path):
    try:
        out = run_hidden(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True,
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 0.0
