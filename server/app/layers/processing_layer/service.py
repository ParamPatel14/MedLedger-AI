from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from app.layers.processing_layer.rxnav import lookup_rxnorm


EntityType = Literal["diagnosis", "procedure", "medication"]


@dataclass(frozen=True)
class NormalizedEntity:
    type: EntityType
    value: str
    normalized_value: str
    ontology_id: str
    start: int
    end: int
    confidence: float


def _clean_text(text: str) -> str:
    t = (text or "").replace("\u0000", " ")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _unique_preserve_order(values: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = (v or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _try_load_spacy():
    try:
        import spacy

        return spacy
    except Exception:
        return None


def _resolve_model_candidates() -> List[str]:
    preferred = os.getenv("CLINICAL_NLP_MODEL") or os.getenv("SPACY_MODEL") or ""
    candidates = [preferred] if preferred else []
    candidates += [
        "en_ner_bc5cdr_md",
        "en_core_sci_md",
        "en_core_sci_sm",
        "en_core_web_sm",
    ]
    return [c for c in candidates if c]


def _label_to_type(label: str) -> Optional[EntityType]:
    l = (label or "").upper()
    if l in {"DISEASE", "DISORDER", "CONDITION", "PROBLEM", "DIAGNOSIS"}:
        return "diagnosis"
    if l in {"CHEMICAL", "DRUG", "MEDICATION"}:
        return "medication"
    if l in {"PROCEDURE", "TREATMENT"}:
        return "procedure"
    return None


def _fallback_patterns_path() -> Path:
    configured = (os.getenv("CLINICAL_FALLBACK_PATTERNS") or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / "clinical_fallback_patterns.json"


@lru_cache(maxsize=1)
def _load_fallback_patterns() -> List[dict]:
    path = _fallback_patterns_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: List[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        etype = str(item.get("type") or "").strip().lower()
        pattern = str(item.get("pattern") or "").strip()
        normalized_value = str(item.get("normalized_value") or item.get("normalized") or "").strip().lower()
        if etype not in {"diagnosis", "procedure", "medication"}:
            continue
        if not pattern or not normalized_value:
            continue
        confidence = item.get("confidence", 0.65)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.65
        out.append(
            {
                "type": etype,
                "pattern": pattern,
                "normalized_value": normalized_value,
                "confidence": max(0.0, min(1.0, confidence)),
            }
        )
    return out


def _keyword_fallback(cleaned: str) -> List[NormalizedEntity]:
    text = cleaned or ""
    low = text.lower()
    patterns = _load_fallback_patterns()
    if not patterns:
        return []

    hits: List[NormalizedEntity] = []
    for item in patterns:
        etype = item["type"]
        pat = item["pattern"]
        norm = item["normalized_value"]
        confidence = item["confidence"]
        m = re.search(pat, low, flags=re.IGNORECASE)
        if not m:
            continue
        start = int(m.start())
        end = int(m.end())
        value = text[start:end].strip().lower()
        if not value:
            continue

        hits.append(
            NormalizedEntity(
                type=etype,
                value=value,
                normalized_value=norm,
                ontology_id="",
                start=start,
                end=end,
                confidence=confidence,
            )
        )


    hits.sort(key=lambda e: (e.start, e.end))
    seen = set()
    out: List[NormalizedEntity] = []
    for e in hits:
        key = (e.type, e.normalized_value)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


class ClinicalNlpService:
    def __init__(self) -> None:
        self._nlp = None
        self.model_name = ""
        self.model_source = ""
        self._init_model()

    def _init_model(self) -> None:
        spacy = _try_load_spacy()
        if spacy is None:
            self._nlp = None
            return

        for name in _resolve_model_candidates():
            try:
                nlp = spacy.load(name)
                try:
                    if "abbreviation_detector" not in nlp.pipe_names:
                        nlp.add_pipe("abbreviation_detector")
                except Exception:
                    pass
                self._nlp = nlp
                self.model_name = name
                self.model_source = "spacy.load"
                return
            except Exception:
                continue

        try:
            nlp = spacy.blank("en")
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")
            self._nlp = nlp
            self.model_name = "blank_en"
            self.model_source = "spacy.blank"
        except Exception:
            self._nlp = None

    def extract(self, text: str) -> Tuple[str, List[NormalizedEntity]]:
        cleaned = _clean_text(text)
        if not cleaned:
            return "", []
        if self._nlp is None:
            return cleaned, []

        doc = self._nlp(cleaned)
        abbr_map: Dict[str, str] = {}
        try:
            abbrs = list(getattr(getattr(doc, "_", None), "abbreviations", []))
        except Exception:
            abbrs = []
        for a in abbrs:
            try:
                short = str(getattr(a, "text", "") or "").strip().lower()
                lf = getattr(getattr(a, "_", None), "long_form", None)
                long = str(getattr(lf, "text", lf) or "").strip().lower()
                if short and long and short != long:
                    abbr_map[short] = long
            except Exception:
                continue

        entities: List[NormalizedEntity] = []
        for ent in getattr(doc, "ents", []):
            etype = _label_to_type(getattr(ent, "label_", ""))
            if etype is None:
                continue
            value = (ent.text or "").strip().lower()
            if not value:
                continue
            normalized_value = abbr_map.get(value, value)
            ontology_id = ""
            conf = 0.85

            if etype == "medication":
                hit = lookup_rxnorm(normalized_value)
                if hit is not None:
                    normalized_value = hit.name.strip().lower()
                    ontology_id = f"RXCUI:{hit.rxcui}"
                    conf = max(conf, hit.score)

            entities.append(
                NormalizedEntity(
                    type=etype,
                    value=value,
                    normalized_value=normalized_value,
                    ontology_id=ontology_id,
                    start=int(ent.start_char),
                    end=int(ent.end_char),
                    confidence=float(conf),
                )
            )

        extra = _keyword_fallback(cleaned)
        if extra:
            entities = (entities or []) + extra
            entities.sort(key=lambda e: (e.start, e.end))
            seen = set()
            merged: List[NormalizedEntity] = []
            for e in entities:
                key = (e.type, e.normalized_value)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(e)
            entities = merged

        return cleaned, entities

    def summarize(self, text: str, entities: List[NormalizedEntity]) -> Tuple[List[str], List[str], List[str]]:
        cleaned = (text or "").strip()
        low = cleaned.lower()

        def _is_negated(e: NormalizedEntity) -> bool:
            try:
                start = int(getattr(e, "start", 0) or 0)
            except Exception:
                start = 0
            start = max(0, min(start, len(low)))
            window = low[max(0, start - 80) : start]
            window = re.sub(r"[^a-z0-9\s]+", " ", window).strip()
            if not window:
                return False
            return (
                re.search(
                    r"(?:\bno\b|\bwithout\b|\bdenies\b|\bdeny\b|\bnegative\s+for\b)(?:\s+\w+){0,3}\s*$",
                    window,
                    flags=re.IGNORECASE,
                )
                is not None
            )

        abbr_map = {
            "uti": "urinary tract infection",
            "htn": "hypertension",
            "ckd": "chronic kidney disease",
            "cad": "coronary artery disease",
            "copd": "chronic obstructive pulmonary disease",
            "dm": "diabetes mellitus",
            "t2dm": "type 2 diabetes mellitus",
            "t1dm": "type 1 diabetes mellitus",
            "type 2 diabetes": "type 2 diabetes mellitus",
            "type ii diabetes": "type 2 diabetes mellitus",
            "type 1 diabetes": "type 1 diabetes mellitus",
            "type i diabetes": "type 1 diabetes mellitus",
        }

        filtered = [e for e in (entities or []) if not _is_negated(e)]

        diagnosis = [abbr_map.get(e.normalized_value, e.normalized_value) for e in filtered if e.type == "diagnosis"]
        procedures = [abbr_map.get(e.normalized_value, e.normalized_value) for e in filtered if e.type == "procedure"]
        medications = [abbr_map.get(e.normalized_value, e.normalized_value) for e in filtered if e.type == "medication"]

        # Split spurious merged diagnoses (e.g., "type 2 diabetes, urinary tract infection") but keep stage qualifiers
        expanded: List[str] = []
        for d in diagnosis:
            if ("," in d or " and " in d) and ("stage" not in d):
                parts = re.split(r",|\\band\\b", d)
                for p in parts:
                    p = p.strip()
                    if not p:
                        continue
                    expanded.append(abbr_map.get(p, p))
            else:
                expanded.append(d)

        diagnosis = _unique_preserve_order(expanded)
        procedures = _unique_preserve_order(procedures)
        medications = _unique_preserve_order(medications)

        if any(d.startswith("type 1 diabetes") or d.startswith("type 2 diabetes") for d in diagnosis):
            diagnosis = [d for d in diagnosis if d != "diabetes mellitus"]
        if any("chronic kidney disease stage" in d for d in diagnosis):
            diagnosis = [d for d in diagnosis if d != "chronic kidney disease"]

        return diagnosis, procedures, medications
