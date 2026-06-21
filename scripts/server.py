"""
Forsaken Realms AI — Flask Server
Run: py server.py  (started automatically by app.py on launch)

Endpoints:
  GET  /health       — Status (no auth)
  GET  /search       — Raw semantic search
  POST /ask          — Q&A with lore context
  POST /suggest      — Writing suggestions
  POST /create_note  — Create note from template
  POST /index_note   — Re-index a single file
  POST /rebuild      — Full vault re-index
"""

import sys, os
from pathlib import Path

if getattr(sys, "frozen", False):
    _scripts_dir = Path(sys.executable).parent
else:
    _scripts_dir = Path(__file__).resolve().parent

os.chdir(_scripts_dir)
sys.path.insert(0, str(_scripts_dir))
from threading import Lock
import re
import requests
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify
from flask_cors import CORS
import config

# ── Load config ───────────────────────────────────────────────────────────────
cfg        = config.load()
API_KEY    = cfg["api_key"]
VAULT      = Path(cfg["vault"])
APP_DIR    = Path(cfg["app_dir"])
MEMORIES   = APP_DIR / "Memories"
INDEX_PATH = APP_DIR / "db" / "faiss_index"
TEMPLATES  = VAULT / "Templates"

OLLAMA_URL   = f"http://localhost:11434/api/generate"
OLLAMA_MODEL = cfg["ollama_model"]

MEMORIES.mkdir(parents=True, exist_ok=True)
INDEX_PATH.mkdir(parents=True, exist_ok=True)

# ── Load model + index ────────────────────────────────────────────────────────
print("Loading embedding model…")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

print("Loading FAISS index…")
index_file = INDEX_PATH / "index.faiss"
names_file = INDEX_PATH / "names.npy"

if index_file.exists():
    index = faiss.read_index(str(index_file))
    names = np.load(names_file, allow_pickle=True)
else:
    print("No index found — run ingest.py first or use /rebuild")
    index = faiss.IndexFlatL2(384)
    names = np.array([])

index_lock = Lock()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["app://obsidian.md", "http://localhost"]}})


# ── Auth ──────────────────────────────────────────────────────────────────────

def check_key():
    if request.headers.get("X-API-Key", "") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_filename(text: str, max_len=60) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", text)[:max_len].strip()


def semantic_search(query: str, k: int = 5):
    if index.ntotal == 0:
        return []
    k = min(k, index.ntotal)
    embedding = embed_model.encode([query], convert_to_numpy=True)
    with index_lock:
        distances, indices = index.search(embedding, k)
    return [(names[i], float(distances[0][j])) for j, i in enumerate(indices[0])]


def build_lore_packet(results, snippet_len=500) -> str:
    packet = ""
    for path, dist in results:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            packet += f"\n--- {Path(path).name} (relevance: {dist:.2f}) ---\n{content[:snippet_len]}\n"
        except FileNotFoundError:
            pass
    return packet


def ollama_generate(prompt: str) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"num_ctx": 4096},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def _index_single_note(note_path: Path):
    global index, names
    content   = note_path.read_text(encoding="utf-8", errors="ignore")
    embedding = embed_model.encode([content], convert_to_numpy=True)
    with index_lock:
        index.add(embedding)
        names = np.concatenate([names, [str(note_path)]])
        faiss.write_index(index, str(index_file))
        np.save(names_file, names)
    print(f"[index] {note_path.name}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": OLLAMA_MODEL,
        "indexed_notes": int(index.ntotal),
        "vault": str(VAULT),
    })


@app.route("/search", methods=["GET"])
def search_route():
    auth = check_key()
    if auth: return auth
    query = request.args.get("q", "").strip()
    k     = int(request.args.get("k", 5))
    if not query:
        return jsonify({"error": "Missing ?q="}), 400
    results = semantic_search(query, k=k)
    return jsonify([{"path": str(p), "distance": d} for p, d in results])


@app.route("/ask", methods=["POST"])
def ask():
    auth = check_key()
    if auth: return auth
    data     = request.get_json(force=True)
    question = data.get("question", "").strip()
    k        = int(data.get("k", 5))
    if not question:
        return jsonify({"error": "Missing 'question'"}), 400

    results = semantic_search(question, k=k)
    packet  = build_lore_packet(results)

    prompt = f"""You are the lore archivist of Forsaken Realms.
Answer only using the lore packet below. Be concise and factual.
If the answer is not in the packet, say "Not found in the vault."

Lore Packet:
{packet}

Question:
{question}
"""
    answer = ollama_generate(prompt)

    mem_file = MEMORIES / (safe_filename(question) + ".md")
    mem_file.write_text(f"# {question}\n\n{answer}", encoding="utf-8")

    return jsonify({
        "answer": answer,
        "sources": [Path(p).name for p, _ in results],
    })


@app.route("/suggest", methods=["POST"])
def suggest():
    auth = check_key()
    if auth: return auth
    data        = request.get_json(force=True)
    active_text = data.get("active_text", "").strip()
    filename    = data.get("filename", "current note")
    k           = int(data.get("k", 5))
    if not active_text:
        return jsonify({"error": "Missing 'active_text'"}), 400

    results = semantic_search(active_text[-400:], k=k)
    packet  = build_lore_packet(results, snippet_len=400)

    prompt = f"""You are the creative writing assistant for Forsaken Realms.
The writer is currently working on: {filename}

Recent text:
---
{active_text[-800:]}
---

Related vault lore:
{packet}

Give 2-3 SHORT, specific suggestions — character details, plot threads,
lore connections, or consistency notes. Be brief. No preamble.
"""
    return jsonify({"suggestions": ollama_generate(prompt)})


@app.route("/create_note", methods=["POST"])
def create_note():
    auth = check_key()
    if auth: return auth
    data          = request.get_json(force=True)
    folder        = data.get("folder", "")
    template_name = data.get("template_name", "")
    replacements  = data.get("replacements", {})
    filename      = data.get("filename", "")
    if not all([folder, template_name, filename]):
        return jsonify({"error": "Missing folder, template_name, or filename"}), 400

    template_path = TEMPLATES / template_name
    if not template_path.exists():
        return jsonify({"error": "Template not found"}), 404

    template = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(f"{{{{{key}}}}}", value)

    target_folder = VAULT / folder
    target_folder.mkdir(parents=True, exist_ok=True)
    note_path = target_folder / f"{safe_filename(filename)}.md"
    note_path.write_text(template, encoding="utf-8")
    _index_single_note(note_path)

    return jsonify({"status": "created", "path": str(note_path), "indexed": True})


@app.route("/index_note", methods=["POST"])
def index_note():
    auth = check_key()
    if auth: return auth
    note_path = Path(request.get_json(force=True).get("path", ""))
    if not note_path.exists():
        return jsonify({"error": "File not found"}), 404
    _index_single_note(note_path)
    return jsonify({"status": "indexed", "path": str(note_path)})


@app.route("/rebuild", methods=["POST"])
def rebuild():
    """Full vault re-index — replaces the whole FAISS index."""
    auth = check_key()
    if auth: return auth
    global index, names

    print("[rebuild] scanning vault…")
    texts, paths = [], []
    for f in VAULT.rglob("*.md"):
        texts.append(f.read_text(encoding="utf-8", errors="ignore"))
        paths.append(str(f))

    embeddings = embed_model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    new_index  = faiss.IndexFlatL2(embeddings.shape[1])
    new_index.add(embeddings)

    with index_lock:
        index = new_index
        names = np.array(paths)
        faiss.write_index(index, str(index_file))
        np.save(names_file, names)

    print(f"[rebuild] indexed {len(texts)} notes.")
    return jsonify({"status": "ok", "indexed": len(texts)})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = cfg.get("server_port", 5000)
    print(f"\nForsaken Realms AI server → http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
