"""
Forsaken Realms AI — Vault File Watcher
Watches your Obsidian vault and POSTs changed notes to the server.
Started automatically by app.py — can also run standalone: py watcher.py
"""

import sys, os
from pathlib import Path

if getattr(sys, "frozen", False):
    _scripts_dir = Path(sys.executable).parent
else:
    _scripts_dir = Path(__file__).resolve().parent

os.chdir(_scripts_dir)
sys.path.insert(0, str(_scripts_dir))

import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import config

cfg        = config.load()
VAULT      = Path(cfg["vault"])
API_KEY    = cfg["api_key"]
SERVER_URL = f"http://127.0.0.1:{cfg.get('server_port', 5000)}"
HEADERS    = {"X-API-Key": API_KEY}


class VaultHandler(FileSystemEventHandler):
    def on_modified(self, event):
        self._handle(event.src_path)
    def on_created(self, event):
        self._handle(event.src_path)

    def _handle(self, path: str):
        if not path.endswith(".md"):
            return
        print(f"[watcher] {Path(path).name}")
        try:
            resp = requests.post(
                f"{SERVER_URL}/index_note",
                json={"path": path},
                headers=HEADERS,
                timeout=30,
            )
            print("[watcher] indexed OK" if resp.ok else f"[watcher] error: {resp.text}")
        except requests.exceptions.ConnectionError:
            print("[watcher] server not reachable")


if __name__ == "__main__":
    print(f"Watching: {VAULT}\n")
    observer = Observer()
    observer.schedule(VaultHandler(), str(VAULT), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
