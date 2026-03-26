from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional, Tuple

import numpy as np
from pathlib import Path

from app.layers.coding_layer.icd10_dataset import IcdRow, icd10_path, iter_descriptions, load_icd10_rows
from app.layers.coding_layer.services.embedding_service import (
    build_faiss_index,
    encode_text,
    encode_texts,
    normalize,
    normalize_single,
)


@dataclass(frozen=True)
class IcdSemanticHit:
    code: str
    description: str
    score: float


def _threshold() -> float:
    try:
        return float(os.getenv("ICD_SEMANTIC_THRESHOLD", "0.7"))
    except Exception:
        return 0.7


def _embeddings_cache_path() -> Path:
    base = Path.cwd() / ".tmp" / "icd"
    base.mkdir(parents=True, exist_ok=True)
    return base / "icd_embeddings.npy"


class IcdMapper:
    def __init__(self) -> None:
        path = icd10_path()
        version, rows = load_icd10_rows(path)
        self.dataset_version = version
        self._rows = rows
        self._descriptions = iter_descriptions(rows)
        self._by_description: Dict[str, IcdRow] = {r.description: r for r in rows}

        self._lock = Lock()
        self._semantic_failed = False
        self._embeddings: Optional[np.ndarray] = None
        self._index = None
        self.embed_model = os.getenv("ICD_EMBED_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"

        if os.getenv("ICD_PRECOMPUTE_ON_STARTUP", "0").strip() == "1":
            self._ensure_semantic_ready()

    def _ensure_semantic_ready(self) -> None:
        if self._index is not None:
            return
        with self._lock:
            if self._index is not None:
                return

            cache = _embeddings_cache_path()
            loaded: Optional[np.ndarray] = None
            try:
                if cache.exists():
                    loaded = np.load(str(cache))
            except Exception:
                loaded = None

            if loaded is None or loaded.size == 0:
                vecs = encode_texts(self._descriptions)
                if vecs is None or getattr(vecs, "size", 0) == 0:
                    self._semantic_failed = True
                    self._embeddings = np.zeros((0, 1), dtype=np.float32)
                    self._index = None
                    return
                embeddings = normalize(vecs.astype(np.float32))
                try:
                    np.save(str(cache), embeddings)
                except Exception:
                    pass
            else:
                embeddings = normalize(loaded.astype(np.float32))

            index = build_faiss_index(embeddings)
            if index is None:
                self._semantic_failed = True
                self._embeddings = embeddings
                self._index = None
                return

            self._embeddings = embeddings
            self._index = index

    def search(self, text: str, top_k: int = 3) -> List[IcdSemanticHit]:
        q = (text or "").strip()
        if not q:
            return []

        self._ensure_semantic_ready()
        if self._index is None or self._embeddings is None or self._embeddings.size == 0:
            return []

        q_vec = encode_text(q)
        if q_vec is None:
            return []
        q_vec = normalize_single(q_vec).astype(np.float32)

        try:
            import faiss

            D, I = self._index.search(q_vec.reshape(1, -1), max(1, top_k))
        except Exception:
            return []

        hits: List[IcdSemanticHit] = []
        for score, idx in zip(D[0].tolist(), I[0].tolist()):
            if idx < 0 or idx >= len(self._descriptions):
                continue
            desc = self._descriptions[idx]
            row = self._by_description.get(desc)
            if row is None:
                continue
            hits.append(IcdSemanticHit(code=row.code, description=row.description, score=float(score)))
        return hits

    def search_with_fallback(self, text: str, top_k: int = 3) -> Tuple[List[IcdSemanticHit], bool]:
        hits = self.search(text, top_k=top_k)
        if not hits:
            # Semantic unavailable or no hits: try fuzzy
            try:
                from rapidfuzz import fuzz
                from rapidfuzz import process as rf_process
            except Exception:
                return [], False
            fuzzy = rf_process.extract(text, self._descriptions, scorer=fuzz.WRatio, limit=top_k)
            out: List[IcdSemanticHit] = []
            for desc, score, _ in fuzzy:
                row = self._by_description.get(desc)
                if row is None:
                    continue
                out.append(IcdSemanticHit(code=row.code, description=row.description, score=float(score) / 100.0))
            return out, False
        # Prefer semantic hits; mark confidence flag relative to threshold
        return hits, bool(hits and hits[0].score >= _threshold())
