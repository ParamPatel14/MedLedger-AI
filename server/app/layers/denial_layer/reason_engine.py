from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.layers.coding_layer.services.embedding_service import encode_text, encode_texts, normalize, normalize_single


@dataclass(frozen=True)
class DenialReason:
    type: str
    raw_reason: str
    confidence: float
    matched_mapping_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "raw_reason": self.raw_reason,
            "confidence": float(self.confidence),
            "matched_mapping_id": self.matched_mapping_id,
        }


def _compile(pattern: str) -> Optional[re.Pattern[str]]:
    try:
        return re.compile(pattern, flags=re.IGNORECASE)
    except Exception:
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    num = float((a * b).sum())
    den = float((a**2).sum() ** 0.5) * float((b**2).sum() ** 0.5)
    if den <= 0:
        return 0.0
    return num / den


class DenialReasonEngine:
    def __init__(self) -> None:
        self._compiled: Dict[str, List[re.Pattern[str]]] = {}
        self._phrase_embeddings: Dict[str, np.ndarray] = {}

    def _prepare(self, mappings_cfg: Dict[str, Any]) -> None:
        mappings = mappings_cfg.get("mappings") or []
        if not isinstance(mappings, list):
            return
        for m in mappings:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "")
            if not mid:
                continue
            match = m.get("match") or {}
            regexes = match.get("regex") or []
            patterns: List[re.Pattern[str]] = []
            if isinstance(regexes, list):
                for r in regexes:
                    rx = _compile(str(r or ""))
                    if rx is not None:
                        patterns.append(rx)
            self._compiled[mid] = patterns

            phrases = match.get("semantic_phrases") or []
            if isinstance(phrases, list) and phrases:
                key = f"phrases::{mid}"
                if key in self._phrase_embeddings:
                    continue
                vecs = encode_texts([str(p or "") for p in phrases if str(p or "").strip()])
                if vecs is None or vecs.size == 0:
                    continue
                self._phrase_embeddings[key] = normalize(vecs)

    def extract(
        self,
        *,
        mappings_cfg: Dict[str, Any],
        raw_reason_text: str,
        rejection_codes: List[str],
    ) -> List[DenialReason]:
        self._prepare(mappings_cfg)
        text = str(raw_reason_text or "").strip()
        codes = [str(c or "").strip() for c in (rejection_codes or []) if str(c or "").strip()]

        semantic_cfg = mappings_cfg.get("semantic_matching") or {}
        enabled = bool(semantic_cfg.get("enabled", True))
        min_similarity = float(semantic_cfg.get("min_similarity", 0.0) or 0.0)
        w_phrase = float(semantic_cfg.get("phrase_weight", 0.0) or 0.0)
        w_regex = float(semantic_cfg.get("regex_weight", 0.0) or 0.0)
        w_code = float(semantic_cfg.get("code_weight", 0.0) or 0.0)

        text_vec = None
        if enabled and text:
            vec = encode_text(text)
            if vec is not None and getattr(vec, "size", 0) > 0:
                text_vec = normalize_single(vec)

        out: List[DenialReason] = []
        mappings = mappings_cfg.get("mappings") or []
        if not isinstance(mappings, list):
            mappings = []

        for m in mappings:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "").strip()
            dtype = str(m.get("type") or "").strip() or "unknown"
            base = float(m.get("base_confidence", 0.0) or 0.0)
            match = m.get("match") or {}
            mapping_codes = {str(x or "").strip() for x in (match.get("codes") or []) if str(x or "").strip()}

            regex_score = 0.0
            patterns = self._compiled.get(mid) or []
            if text and patterns:
                matched = any(bool(rx.search(text)) for rx in patterns)
                regex_score = 1.0 if matched else 0.0

            code_score = 0.0
            if codes and mapping_codes:
                code_score = 1.0 if bool(set(codes).intersection(mapping_codes)) else 0.0

            phrase_score = 0.0
            if enabled and text_vec is not None:
                emb_key = f"phrases::{mid}"
                phrase_emb = self._phrase_embeddings.get(emb_key)
                if phrase_emb is not None and phrase_emb.size > 0:
                    sims = phrase_emb @ text_vec
                    try:
                        phrase_score = float(np.max(sims))
                    except Exception:
                        phrase_score = 0.0

            combined = (w_regex * regex_score) + (w_code * code_score) + (w_phrase * phrase_score)
            confidence = max(base, min(1.0, base + combined * (1.0 - base)))
            if enabled and phrase_score < min_similarity and regex_score <= 0.0 and code_score <= 0.0:
                continue
            if not enabled and regex_score <= 0.0 and code_score <= 0.0:
                continue
            out.append(DenialReason(type=dtype, raw_reason=text, confidence=confidence, matched_mapping_id=mid))

        if not out:
            out.append(DenialReason(type="unknown", raw_reason=text, confidence=0.0, matched_mapping_id=""))
            return out

        best_by_type: Dict[str, DenialReason] = {}
        for it in out:
            prev = best_by_type.get(it.type)
            if prev is None or it.confidence > prev.confidence:
                best_by_type[it.type] = it
        return sorted(best_by_type.values(), key=lambda r: float(r.confidence), reverse=True)
