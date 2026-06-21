"""
Forsaken Realms AI — Desktop App  v3.1
Run: py app.py
Requires: py -m pip install PySide6 requests flask flask-cors watchdog sentence-transformers faiss-cpu
"""

import sys, os, random, subprocess
import requests
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QStatusBar, QSplashScreen,
    QSystemTrayIcon, QMenu, QDialog, QLabel, QDialogButtonBox,
    QFileDialog, QWizard, QWizardPage, QProgressBar, QMessageBox
)
from PySide6.QtGui import (
    QIcon, QPixmap, QKeySequence, QShortcut, QColor, QPalette, QFont
)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
import config

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)


def _icon(name):
    p = SCRIPT_DIR / "icons" / name
    return QIcon(str(p)) if p.exists() else QIcon()


def _pixmap(name):
    p = SCRIPT_DIR / "icons" / name
    return QPixmap(str(p)) if p.exists() else None


# ── Background workers ────────────────────────────────────────────────────────

class AskWorker(QThread):
    done  = Signal(str, list)
    error = Signal(str)

    def __init__(self, question, server, headers):
        super().__init__()
        self.question = question
        self.server   = server
        self.headers  = headers

    def run(self):
        try:
            r = requests.post(self.server + "/ask",
                              json={"question": self.question},
                              headers=self.headers, timeout=300)
            r.raise_for_status()
            d = r.json()
            self.done.emit(d.get("answer", ""), d.get("sources", []))
        except Exception as e:
            self.error.emit(str(e))


class SuggestWorker(QThread):
    done  = Signal(str)
    error = Signal(str)

    def __init__(self, text, filename, server, headers):
        super().__init__()
        self.text     = text
        self.filename = filename
        self.server   = server
        self.headers  = headers

    def run(self):
        try:
            r = requests.post(self.server + "/suggest",
                              json={"active_text": self.text, "filename": self.filename},
                              headers=self.headers, timeout=300)
            r.raise_for_status()
            self.done.emit(r.json().get("suggestions", ""))
        except Exception as e:
            self.error.emit(str(e))


class RebuildWorker(QThread):
    done  = Signal(int)
    error = Signal(str)

    def __init__(self, server, headers):
        super().__init__()
        self.server  = server
        self.headers = headers

    def run(self):
        try:
            r = requests.post(self.server + "/rebuild",
                              headers=self.headers, timeout=300)
            r.raise_for_status()
            self.done.emit(r.json().get("indexed", 0))
        except Exception as e:
            self.error.emit(str(e))


# ── Ingest worker ─────────────────────────────────────────────────────────────

class IngestWorker(QThread):
    progress = Signal(int, int, str)
    done     = Signal(int)
    error    = Signal(str)

    def __init__(self, vault: str, app_dir: str):
        super().__init__()
        self.vault   = vault
        self.app_dir = app_dir

    def run(self):
        try:
            from sentence_transformers import SentenceTransformer
            import faiss, numpy as np

            vault      = Path(self.vault)
            index_path = Path(self.app_dir) / "db" / "faiss_index"
            index_path.mkdir(parents=True, exist_ok=True)

            if not vault.exists():
                raise Exception(f"Vault not found: {vault}")

            files = list(vault.rglob("*.md"))
            total = len(files)
            if total == 0:
                raise Exception("No .md files found in vault.")

            model        = SentenceTransformer("all-MiniLM-L6-v2")
            texts, names = [], []

            for i, f in enumerate(files):
                content = f.read_text(encoding="utf-8", errors="ignore")
                texts.append(content)
                names.append(str(f))
                self.progress.emit(i + 1, total, f.name)

            embeddings = model.encode(texts, convert_to_numpy=True)
            index      = faiss.IndexFlatL2(embeddings.shape[1])
            index.add(embeddings)

            faiss.write_index(index, str(index_path / "index.faiss"))
            np.save(index_path / "names.npy", np.array(names))

            self.done.emit(total)
        except Exception as e:
            self.error.emit(str(e))


# ── Setup Wizard pages ────────────────────────────────────────────────────────

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to Forsaken Realms AI")
        self.setSubTitle("Your personal lore assistant. Let's get set up.")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "This wizard will:\n\n"
            "  • Locate your Obsidian vault\n"
            "  • Set up the data folder\n"
            "  • Name your assistant\n"
            "  • Index your entire vault\n\n"
            "Indexing runs once and takes 1-3 minutes.\n"
            "After that, startup is instant.\n\n"
            "Click Next to begin."
        ))


class VaultPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Vault Location")
        self.setSubTitle("Where is your Obsidian vault folder?")
        self.vault_path = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select your Obsidian vault folder:"))

        row = QHBoxLayout()
        self.path_label = QLabel("No folder selected")
        self.path_label.setStyleSheet("color:#aaa;font-style:italic;")
        self.path_label.setWordWrap(True)
        row.addWidget(self.path_label, 1)

        btn = QPushButton("Browse…")
        btn.setFixedWidth(90)
        btn.clicked.connect(self._browse)
        row.addWidget(btn)
        layout.addLayout(row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault")
        if folder:
            self.vault_path = folder
            self.path_label.setText(folder)
            self.path_label.setStyleSheet("color:#ccc;")
            # Save vault path immediately so ingest can find it
            cfg = config.load()
            cfg["vault"] = folder
            config.save(cfg)
            self.completeChanged.emit()

    def isComplete(self):
        return bool(self.vault_path)


class AppDirPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Data Folder")
        self.setSubTitle("Where should Forsaken Realms AI store its data?")

        default = str(SCRIPT_DIR.parent)
        self.app_path = default

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "This folder holds your AI memories, vector index, and settings.\n"
            "The default is the AI Assistant folder included with this install."
        ))

        row = QHBoxLayout()
        self.path_label = QLabel(default)
        self.path_label.setStyleSheet("color:#ccc;")
        self.path_label.setWordWrap(True)
        row.addWidget(self.path_label, 1)

        btn = QPushButton("Change…")
        btn.setFixedWidth(90)
        btn.clicked.connect(self._browse)
        row.addWidget(btn)
        layout.addLayout(row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Data Folder")
        if folder:
            self.app_path = folder
            self.path_label.setText(folder)
            # Save app_dir immediately
            cfg = config.load()
            cfg["app_dir"] = folder
            config.save(cfg)
            self.completeChanged.emit()

    def isComplete(self):
        return bool(self.app_path)


class NamePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Name Your Assistant")
        self.setSubTitle("Accept the suggested name or choose your own.")
        self._suggested = random.choice(["Arise", "Nyvara", "Kaelith", "Solenne", "Eryndor"])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f'Suggested name:  <b>{self._suggested}</b>\n\n'
            "Leave blank to accept, or type your own:"
        ))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self._suggested)
        self.name_input.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.name_input)

    def get_name(self):
        return self.name_input.text().strip() or self._suggested


class IngestPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Indexing Your Vault")
        self.setSubTitle("Building the knowledge base — this runs once only.")
        self._complete = False
        self._worker   = None
        self.vault     = ""
        self.app_dir   = ""

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Starting…")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color:#aaa;font-size:11px;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

    def initializePage(self):
        self._worker = IngestWorker(self.vault, self.app_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current, total, filename):
        pct = int((current / total) * 100) if total else 0
        self.progress.setValue(pct)
        self.status_label.setText(f"Indexing note {current} of {total}…")
        self.file_label.setText(filename)

    def _on_done(self, total):
        self.progress.setValue(100)
        self.status_label.setText(f"✓ Done — {total} notes indexed. Click Next to continue.")
        self.file_label.setText("")
        self._complete = True
        self.completeChanged.emit()

    def _on_error(self, msg):
        self.status_label.setText(f"⚠ Error: {msg}")
        self.file_label.setText("You can continue but the assistant will have no lore context.")
        self._complete = True
        self.completeChanged.emit()

    def isComplete(self):
        return self._complete


# ── Setup Wizard ──────────────────────────────────────────────────────────────

class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Forsaken Realms AI — Setup")
        self.setMinimumSize(560, 420)
        self.setWindowIcon(_icon("icon.ico"))

        self.welcome_pg = WelcomePage()
        self.vault_pg   = VaultPage()
        self.dir_pg     = AppDirPage()
        self.name_pg    = NamePage()
        self.ingest_pg  = IngestPage()

        self.addPage(self.welcome_pg)
        self.addPage(self.vault_pg)
        self.addPage(self.dir_pg)
        self.addPage(self.name_pg)
        self.addPage(self.ingest_pg)

    def initializePage(self, page_id):
        if self.page(page_id) is self.ingest_pg:
            cfg                = config.load()
            cfg["vault"]       = self.vault_pg.vault_path
            cfg["app_dir"]     = self.dir_pg.app_path
            cfg["python_path"] = config.find_python()
            config.save(cfg)

            self.ingest_pg.vault   = self.vault_pg.vault_path
            self.ingest_pg.app_dir = self.dir_pg.app_path

            app_dir = Path(self.dir_pg.app_path)
            (app_dir / "db" / "faiss_index").mkdir(parents=True, exist_ok=True)
            (app_dir / "Memories").mkdir(parents=True, exist_ok=True)
            (app_dir / "data").mkdir(parents=True, exist_ok=True)
            (app_dir / "models").mkdir(parents=True, exist_ok=True)

        super().initializePage(page_id)

    def run_setup(self):
        if self.exec() != QWizard.Accepted:
            return None, None

        cfg  = config.load()
        name = self.name_pg.get_name()

        mem_dir = Path(self.dir_pg.app_path) / "Memories"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "assistant_name.txt").write_text(name, encoding="utf-8")

        return cfg, name


# ── Process launcher ──────────────────────────────────────────────────────────

class ProcessManager:
    def __init__(self):
        self._procs = []

    def launch(self):
        python = config.find_python()
        NO_WIN = 0x08000000

        for script in ["server.py", "watcher.py"]:
            path = SCRIPT_DIR / script
            if not path.exists():
                print(f"[launcher] {script} not found at {path}")
                continue
            proc = subprocess.Popen(
                [python, str(path)],
                creationflags=NO_WIN,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._procs.append(proc)
            print(f"[launcher] {script} started (pid {proc.pid})")

    def stop(self):
        for proc in self._procs:
            try:
                proc.terminate()
            except Exception:
                pass
        self._procs.clear()


# ── Main window ───────────────────────────────────────────────────────────────

class ForsakenRealmsAI(QMainWindow):
    def __init__(self, cfg, name, proc_manager):
        super().__init__()
        self.cfg       = cfg
        self.assistant = name
        self.procs     = proc_manager
        self.worker    = None
        self.server    = f"http://127.0.0.1:{cfg.get('server_port', 5000)}"
        self.headers   = {
            "X-API-Key":    cfg["api_key"],
            "Content-Type": "application/json",
        }

        self.setWindowTitle(f"Forsaken Realms AI — {name}")
        self.setMinimumSize(740, 540)
        self.setWindowIcon(_icon("icon.ico"))
        self._apply_dark_theme()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setPlaceholderText("Answers and suggestions appear here…")
        root.addWidget(self.output)

        row = QHBoxLayout()
        row.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText(f"Ask {name} something… (Enter to send)")
        self.input.setFont(QFont("Segoe UI", 11))
        self.input.returnPressed.connect(self.on_ask)
        row.addWidget(self.input)

        self.ask_btn = QPushButton("Ask")
        self.ask_btn.setFixedWidth(70)
        self.ask_btn.clicked.connect(self.on_ask)
        row.addWidget(self.ask_btn)

        self.suggest_btn = QPushButton("Suggest")
        self.suggest_btn.setFixedWidth(80)
        self.suggest_btn.setToolTip("Paste writing into the box then click Suggest")
        self.suggest_btn.clicked.connect(self.on_suggest)
        row.addWidget(self.suggest_btn)

        root.addLayout(row)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.on_ask)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("⟳ Starting server…")

        self._startup_attempts = 0
        self._startup_timer = QTimer()
        self._startup_timer.timeout.connect(self._poll_startup)
        self._startup_timer.start(2000)

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self.refresh_status)

        tray = QSystemTrayIcon(_icon("icon.ico"), self)
        menu = QMenu()
        menu.addAction("Open",           self.showNormal)
        menu.addAction("Rebuild Index",  self.rebuild_index)
        menu.addAction("Open Vault",     self.open_vault)
        menu.addAction("Restart Ollama", self.restart_ollama)
        menu.addSeparator()
        menu.addAction("Exit",           self._quit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None
        )
        tray.show()
        self.tray = tray

        self._print(f"✦ Starting {name}…")
        self._print("⟳ Launching server and vault watcher in the background…")

    def _poll_startup(self):
        self._startup_attempts += 1
        try:
            r = requests.get(self.server + "/health", timeout=2).json()
            self._startup_timer.stop()
            self._status_timer.start(30000)
            notes = r.get("indexed_notes", 0)
            self._print(f"✓ Server ready — {notes} notes indexed.\n")
            if notes == 0:
                self._print(
                    "⚠  No notes found in the index.\n"
                    "   Use Tray → Rebuild Index to index your vault."
                )
            self.status.showMessage(
                f"✓ {r.get('model','?')}   Notes: {notes}   Ready"
            )
        except Exception:
            if self._startup_attempts >= 30:
                self._startup_timer.stop()
                self._print(
                    "⚠  Server did not start after 60s.\n"
                    "   Make sure Python is installed and server.py is in the scripts folder."
                )
                self.status.showMessage("⚠ Server not responding")
            else:
                self.status.showMessage(
                    f"⟳ Waiting for server… ({self._startup_attempts * 2}s)"
                )

    def _print(self, text):
        self.output.append(text)
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum()
        )

    def _set_busy(self, busy):
        self.ask_btn.setEnabled(not busy)
        self.suggest_btn.setEnabled(not busy)
        self.input.setEnabled(not busy)
        if busy:
            self.status.showMessage(f"⟳ {self.assistant} is thinking…")
        else:
            self.refresh_status()

    def refresh_status(self):
        try:
            r = requests.get(self.server + "/health", timeout=3).json()
            self.status.showMessage(
                f"✓ {r.get('model','?')}   Notes: {r.get('indexed_notes',0)}   Ready"
            )
        except Exception:
            self.status.showMessage("⚠ Server not reachable")

    def on_ask(self):
        q = self.input.text().strip()
        if not q:
            return
        self.input.clear()
        self._print(f"\n▶ You: {q}")
        self._print(f"⟳ {self.assistant} is searching the vault…")
        self._set_busy(True)
        self.worker = AskWorker(q, self.server, self.headers)
        self.worker.done.connect(self._on_ask_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_ask_done(self, answer, sources):
        self._print(f"\n✦ {self.assistant}:\n{answer}")
        if sources:
            self._print(f"\n📄 Sources: {', '.join(sources)}\n")
        self._set_busy(False)

    def on_suggest(self):
        text = self.input.text().strip()
        if not text:
            self._print("⚠  Paste some writing into the input box first, then click Suggest.")
            return
        self._print("\n⟳ Getting suggestions…")
        self._set_busy(True)
        self.worker = SuggestWorker(text, "Desktop", self.server, self.headers)
        self.worker.done.connect(self._on_suggest_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_suggest_done(self, suggestions):
        self._print(f"\n✦ Suggestions:\n{suggestions}\n")
        self._set_busy(False)

    def _on_error(self, msg):
        self._print(f"\n⚠ Error: {msg}")
        self._set_busy(False)

    def rebuild_index(self):
        self._print("\n⟳ Rebuilding vault index — this may take a minute…")
        self.worker = RebuildWorker(self.server, self.headers)
        self.worker.done.connect(
            lambda n: self._print(f"✓ Rebuilt — {n} notes indexed.\n")
        )
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def open_vault(self):
        vault = Path(self.cfg.get("vault", ""))
        if vault.exists():
            os.startfile(str(vault))
        else:
            self._print("⚠  Vault path not found.")

    def restart_ollama(self):
        self._print("⟳ Restarting Ollama…")
        os.system("taskkill /f /im ollama.exe >nul 2>&1")
        QTimer.singleShot(2000, lambda: subprocess.Popen(
            ["ollama", "serve"], creationflags=0x08000000
        ))
        self._print("✓ Ollama restart requested.")

    def _quit(self):
        self.procs.stop()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Still running",
            f"{self.assistant} is in the system tray.",
            QSystemTrayIcon.Information, 2000
        )

    def _apply_dark_theme(self):
        p = QPalette()
        p.setColor(QPalette.Window,          QColor(28, 28, 34))
        p.setColor(QPalette.WindowText,      QColor(220, 210, 200))
        p.setColor(QPalette.Base,            QColor(20, 20, 26))
        p.setColor(QPalette.AlternateBase,   QColor(36, 36, 44))
        p.setColor(QPalette.Text,            QColor(220, 210, 200))
        p.setColor(QPalette.Button,          QColor(44, 38, 56))
        p.setColor(QPalette.ButtonText,      QColor(220, 210, 200))
        p.setColor(QPalette.Highlight,       QColor(88, 58, 120))
        p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        QApplication.setPalette(p)


# ── Splash ────────────────────────────────────────────────────────────────────

def run_splash(app, name):
    pm = _pixmap("splash.png")
    if pm is None or pm.isNull():
        pm = QPixmap(480, 220)
        pm.fill(QColor(28, 28, 34))

    splash = QSplashScreen(pm, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    msgs = [
        f"{name} is awakening…",
        "Initializing neural pathways…",
        "Accessing memories…",
        "Synchronizing with vault…",
        "Online.",
    ]

    def tick(i=0):
        if i < len(msgs):
            splash.showMessage(
                msgs[i], Qt.AlignHCenter | Qt.AlignBottom, QColor(180, 140, 220)
            )
            QTimer.singleShot(900, lambda: tick(i + 1))
        else:
            splash.close()

    tick()
    return splash


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Forsaken Realms AI")

    if not config.is_configured():
        wizard = SetupWizard()
        cfg, name = wizard.run_setup()
        if cfg is None:
            sys.exit(0)
    else:
        cfg  = config.load()
        mem  = Path(cfg["app_dir"]) / "Memories" / "assistant_name.txt"
        name = mem.read_text(encoding="utf-8").strip() if mem.exists() else "Arise"

    procs = ProcessManager()
    procs.launch()

    splash = run_splash(app, name)
    window = ForsakenRealmsAI(cfg, name, procs)
    QTimer.singleShot(4600, lambda: (splash.close(), window.show()))

    sys.exit(app.exec())
