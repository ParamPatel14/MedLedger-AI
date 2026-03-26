from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np


def _model_name() -> str:
    return os.getenv("ICD_EMBED_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None
    try:
        # Ensure writable cache location to avoid OS restrictions
        base = os.path.abspath(os.path.join(os.getcwd(), ".tmp", "hf"))
        os.makedirs(base, exist_ok=True)
        os.environ.setdefault("HF_HOME", base)
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", base)
        return SentenceTransformer(_model_name(), cache_folder=base)
    except Exception:
        return None


def encode_texts(texts: List[str]) -> Optional[np.ndarray]:
    model = get_model()
    if model is None or not texts:
        return None
    vecs = model.encode(texts, normalize_embeddings=False)
    return np.asarray(vecs, dtype=np.float32)


def encode_text(text: str) -> Optional[np.ndarray]:
    arr = encode_texts([text])
    if arr is None:
        return None
    return arr[0]


def normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def normalize_single(vec: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(vec)
    if n <= 0:
        return vec
    return vec / n


def build_faiss_index(vectors: np.ndarray):
    try:
        import faiss
    except Exception:
        return None
    if vectors is None or vectors.size == 0:
        return None
    dim = int(vectors.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return index
