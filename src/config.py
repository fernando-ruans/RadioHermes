"""Carrega config.toml (tomllib do Python 3.11+)."""
import tomllib


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def cfg_get(cfg, *keys, default=None):
    cur = cfg
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur
