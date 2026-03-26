from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

from rapidfuzz import fuzz
from rapidfuzz import process as rf_process

from app.layers.coding_layer.icd10_dataset import IcdRow
from app.layers.coding_layer.services.icd_mapper import IcdMapper


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
        self._mapper = IcdMapper()
        self.dataset_version = self._mapper.dataset_version
        self.embed_model = self._mapper.embed_model

    def match_diagnosis(self, diagnosis: str, top_k: int = 1) -> List[IcdMatch]:
        query = (diagnosis or "").strip()
        if not query:
            return []

        # Ensure semantic index is ready (retry-safe)
        self._mapper._ensure_semantic_ready()

        # Prefer semantic search via FAISS index
        hits, confident = self._mapper.search_with_fallback(query, top_k=max(1, top_k))
        method = "semantic" if confident else "fuzzy_fallback"
        out: List[IcdMatch] = []
        for h in hits[:top_k]:
            out.append(IcdMatch(code=h.code, description=h.description, confidence=h.score, method=method, source_text=query))
        return out

    def _find_by_description(self, description: str) -> Optional[IcdRow]:
        return None
