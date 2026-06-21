"""
Forsaken Realms AI — Shared Config
All scripts import from here. On first run, app.py writes config.json.
Every script reads it automatically after that.
"""

import json
from pathlib import Path
import sys
import shutil

# Config file lives next to the scripts
if getattr(sys, "frozen", False):
    CONFIG_FILE = Path(sys.executable).parent / "config.json"
else:
    CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

DEFAULTS = {
    "vault":        "",
    "app_dir":      "",
    "api_key":      "forsaken-realms-local-key",
    "ollama_model": "qwen3:8b",
    "server_port":  5000,
}


def find_python() -> str:
    # If frozen, sys.executable is app.exe — skip it
    if not getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        if exe.exists():
            return str(exe)

    # Known install path for this machine
    known = [
        r"C:\Users\ariel\AppData\Local\Python\pythoncore-3.14-64\python.exe",
        r"C:\Python314\python.exe",
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
    ]
    for path in known:
        if Path(path).exists():
            return path

    # Search PATH, skip Windows Store stubs
    for exe_name in ("py", "python3", "python"):
        path = shutil.which(exe_name)
        if path and "WindowsApps" not in path:
            return path

    return "python"
    
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