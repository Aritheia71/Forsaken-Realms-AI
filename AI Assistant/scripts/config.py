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
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULTS = {
    "vault":        "",
    "app_dir":      "",
    "api_key":      "forsaken-realms-local-key",
    "ollama_model": "qwen3:8b",
    "server_port":  5000,
}


def find_python() -> str:
    """
    Return a usable python executable path. Preference order:
      1) sys.executable (if it exists)
      2) the 'py' launcher on Windows
      3) 'python3' or 'python' from PATH
    Returns a string suitable for subprocess calls.
    """
    # Prefer the currently running interpreter if the path exists
    if getattr(sys, "executable", None):
        exe = Path(sys.executable)
        if exe.exists():
            return str(exe)

    # Then common launchers
    for exe_name in ("py", "python3", "python"):
        path = shutil.which(exe_name)
        if path:
            return path

    # Fallback
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
