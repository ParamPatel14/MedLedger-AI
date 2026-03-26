from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

from rapidfuzz import fuzz
from rapidfuzz import process as rf_process

from app.layers.coding_layer.icd10_dataset import IcdRow, icd10_path, iter_descriptions, load_icd10_rows


@dataclass(frozen=True)
class IcdMatch:
    code: str
    description: str
    confidence: float
    method: str
    source_text: str


def _embed_model_name() -> str:
    return os.getenv("ICD_EMBED_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_dataset() -> Tuple[str, List[IcdRow], List[str]]:
    path = icd10_path()
    version, rows = load_icd10_rows(path)
    descriptions = iter_descriptions(rows)
    return version, rows, descriptions


@lru_cache(maxsize=1)
def _load_embedder():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None
    try:
        return SentenceTransformer(_embed_model_name())
    except Exception:
        return None


def _cosine(a, b) -> float:
    num = float((a * b).sum())
    den = float((a**2).sum() ** 0.5) * float((b**2).sum() ** 0.5)
    if den <= 0:
        return 0.0
    return num / den


class IcdCodingService:
    def __init__(self) -> None:
        version, rows, descriptions = _load_dataset()
        self.dataset_version = version
        self._rows = rows
        self._descriptions = descriptions
        self._by_description = {r.description: r for r in rows}
        self.embed_model = _embed_model_name()

    def match_diagnosis(self, diagnosis: str, top_k: int = 1) -> List[IcdMatch]:
        query = (diagnosis or "").strip()
        if not query:
            return []

        hits = rf_process.extract(
            query,
            self._descriptions,
            scorer=fuzz.WRatio,
            limit=max(25, top_k * 20),
        )

        candidates: List[Tuple[str, float]] = []
        for desc, score, _ in hits:
            candidates.append((str(desc), float(score) / 100.0))
        if not candidates:
            return []

        embedder = _load_embedder()
        if embedder is None:
            return self._materialize(query, candidates[:top_k], method="fuzzy")

        try:
            q_vec = embedder.encode([query], normalize_embeddings=False)[0]
            d_vecs = embedder.encode([c[0] for c in candidates], normalize_embeddings=False)
        except Exception:
            return self._materialize(query, candidates[:top_k], method="fuzzy")

        scored: List[Tuple[str, float]] = []
        for (desc, fuzzy_score), vec in zip(candidates, d_vecs):
            sim = max(0.0, min(1.0, (_cosine(q_vec, vec) + 1.0) / 2.0))
            final = 0.55 * fuzzy_score + 0.45 * sim
            scored.append((desc, final))

        scored.sort(key=lambda x: x[1], reverse=True)
        return self._materialize(query, scored[:top_k], method="hybrid")

    def _materialize(self, source_text: str, descriptions: List[Tuple[str, float]], method: str) -> List[IcdMatch]:
        out: List[IcdMatch] = []
        for desc, score in descriptions:
            row = self._find_by_description(desc)
            if row is None:
                continue
            out.append(
                IcdMatch(
                    code=row.code,
                    description=row.description,
                    confidence=float(score),
                    method=method,
                    source_text=source_text,
                )
            )
        return out

    def _find_by_description(self, description: str) -> Optional[IcdRow]:
        key = description.strip()
        if not key:
            return None
        return self._by_description.get(key)
