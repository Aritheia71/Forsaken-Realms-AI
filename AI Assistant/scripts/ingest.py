"""
Forsaken Realms AI — Vault Ingest
Scans the entire vault, embeds every note, builds the FAISS index.
Run manually: py ingest.py
Also called automatically by app.py on first launch.
"""

from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import config

cfg        = config.load()
VAULT      = Path(cfg["vault"])
APP_DIR    = Path(cfg["app_dir"])
INDEX_PATH = APP_DIR / "db" / "faiss_index"

INDEX_PATH.mkdir(parents=True, exist_ok=True)


def run_ingest(progress_callback=None):
    cfg        = config.load()
    vault      = Path(cfg.get("vault", ""))
    app_dir    = Path(cfg.get("app_dir", ""))
    index_path = app_dir / "db" / "faiss_index"

    if not vault.exists():
        raise Exception(f"Vault path not found: {vault}")

    index_path.mkdir(parents=True, exist_ok=True)

    files = list(vault.rglob("*.md"))
    total = len(files)
    if total == 0:
        raise Exception("No .md files found in vault.")

    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts, names = [], []
    for i, f in enumerate(files):
        content = f.read_text(encoding="utf-8", errors="ignore")
        texts.append(content)
        names.append(str(f))
        if progress_callback:
            progress_callback(i + 1, total, f.name)

    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)

    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(index_path / "index.faiss"))
    np.save(index_path / "names.npy", np.array(names))

    print(f"Done — indexed {total} notes.")
    return total


if __name__ == "__main__":
    run_ingest()
