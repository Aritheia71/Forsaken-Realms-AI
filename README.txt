========================================
  FORSAKEN REALMS AI  —  READ ME FIRST
========================================

Before launching the app you need two things installed:

──────────────────────────────────────────
1. OLLAMA  (the local AI engine)
──────────────────────────────────────────
Download from: https://ollama.com
Install it, then open PowerShell and run:

    ollama pull qwen3:8b

This downloads the AI model (about 5GB).
It only needs to be done once.

──────────────────────────────────────────
2. PYTHON 3.10 or newer
──────────────────────────────────────────
Download from: https://www.python.org/downloads/
During install tick "Add Python to PATH".

Then open PowerShell and run:

    py -m pip install flask flask-cors watchdog sentence-transformers faiss-cpu

──────────────────────────────────────────
FIRST LAUNCH
──────────────────────────────────────────
Double-click the Forsaken Realms AI shortcut.
A setup wizard will appear asking you to:
  - Point to your Obsidian vault folder
  - Choose a name for your assistant

The assistant will then index your entire vault.
This takes 1-3 minutes and only happens once.
After that, startup is instant.

──────────────────────────────────────────
QUESTIONS / ISSUES
──────────────────────────────────────────
If the assistant says "Server not reachable",
make sure Ollama is running:
  Open PowerShell and type:  ollama serve

========================================
