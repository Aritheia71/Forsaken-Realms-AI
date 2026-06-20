"""
Forsaken Realms AI — Shared Config
All scripts import from here. On first run, app.py writes config.json.
Every script reads it automatically after that.
"""

import json
from pathlib import Path

# Config file lives next to the scripts
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULTS = {
    "vault":        "",
    "app_dir":      "",
    "api_key":      "forsaken-realms-local-key",
    "ollama_model": "qwen3:8b",
    "server_port":  5000,
}


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def is_configured() -> bool:
    cfg = load()
    return bool(cfg.get("vault")) and bool(cfg.get("app_dir"))


def get_path(key: str) -> Path:
    return Path(load()[key])
