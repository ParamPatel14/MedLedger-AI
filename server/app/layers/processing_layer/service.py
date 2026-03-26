from __future__ import annotations

import os
import re
from dataclasses import dataclass
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


def _keyword_fallback(cleaned: str) -> List[NormalizedEntity]:
    text = cleaned or ""
    low = text.lower()
    patterns: List[Tuple[EntityType, str, str]] = [
        ("diagnosis", r"\bdiabetes\b", "type 2 diabetes mellitus"),
        ("diagnosis", r"\b(high\s+)?blood\s+sugar(\s+levels)?\b", "hyperglycemia"),
        ("diagnosis", r"\bhyperglyc(e|a)mi(a|e)\b", "hyperglycemia"),
        ("diagnosis", r"\bhtn\b", "hypertension"),
        ("diagnosis", r"\bhypertension\b", "hypertension"),
        ("diagnosis", r"\bchest\s+pain\b", "chest pain"),
        ("diagnosis", r"\b(difficulty\s+breathing|shortness\s+of\s+breath|dyspnea)\b", "shortness of breath"),
        ("diagnosis", r"\basthma\b", "asthma"),
        ("diagnosis", r"\bkidney\s+failure(\s+stage\s*(\d+))?\b", "kidney failure"),
        ("diagnosis", r"\b(heart\s+attack|myocardial\s+infarction)\b", "myocardial infarction"),
        ("diagnosis", r"\b(urinary\s+tract\s+infection|urinary\s+infection|uti)\b", "urinary tract infection"),
    ]

    hits: List[NormalizedEntity] = []
    for etype, pat, norm in patterns:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if not m:
            continue
        start = int(m.start())
        end = int(m.end())
        value = text[start:end].strip().lower()
        if not value:
            continue

        normalized_value = norm
        if pat.startswith(r"\bkidney\s+failure"):
            stage = ""
            try:
                stage = (m.group(2) or "").strip()
            except Exception:
                stage = ""
            if stage:
                normalized_value = f"chronic kidney disease stage {stage}"
        hits.append(
            NormalizedEntity(
                type=etype,
                value=value,
                normalized_value=normalized_value,
                ontology_id="",
                start=start,
                end=end,
                confidence=0.65,
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

    def summarize(self, entities: List[NormalizedEntity]) -> Tuple[List[str], List[str], List[str]]:
        diagnosis = _unique_preserve_order([e.normalized_value for e in entities if e.type == "diagnosis"])
        procedures = _unique_preserve_order([e.normalized_value for e in entities if e.type == "procedure"])
        medications = _unique_preserve_order([e.normalized_value for e in entities if e.type == "medication"])
        return diagnosis, procedures, medications
