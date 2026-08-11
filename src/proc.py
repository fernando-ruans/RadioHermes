"""Helpers de subprocesso: roda comandos SEM abrir janela de console
(no Windows empacotado isso evita terminais pipocando na tela)."""
import subprocess
import sys

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


def run_hidden(cmd, **kwargs):
    """subprocess.run() sem janela de console no Windows."""
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)
