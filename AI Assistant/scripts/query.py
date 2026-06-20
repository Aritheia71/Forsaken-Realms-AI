"""
Forsaken Realms AI — Query
Semantic search against the FAISS index.
Used by server.py. Can also be run standalone for testing.
"""

from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import config

cfg        = config.load()
APP_DIR    = Path(cfg["app_dir"])
INDEX_PATH = APP_DIR / "db" / "faiss_index"

model = SentenceTransformer("all-MiniLM-L6-v2")

index = faiss.read_index(str(INDEX_PATH / "index.faiss"))
names = np.load(INDEX_PATH / "names.npy", allow_pickle=True)


def search(query, k=5):
    embedding = model.encode([query], convert_to_numpy=True)
    distances, indices = index.search(embedding, k)
    return [(names[i], distances[0][j]) for j, i in enumerate(indices[0])]


if __name__ == "__main__":
    results = search("Kaela Thorne backstory")
    for path, dist in results:
        print(f"{dist:.3f}  {path}")
