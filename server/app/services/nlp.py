from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from app.models.schemas import ExtractedEntity, ProcessResponse
from app.utils.terminology import TerminologyStore, load_terminology_store
from app.services.gemini import extract_with_gemini


logger = logging.getLogger("app.services.nlp")


EntityType = Literal["diagnosis", "procedure", "medication"]


def _clean_text(text: str) -> str:
    text = text.replace("\u0000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _unique_preserve_order(values: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = v.strip().lower()
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


@dataclass(frozen=True)
class ModelInfo:
    name: str
    source: str


class ClinicalNlpPipeline:
    def __init__(self) -> None:
        self._nlp = None
        self._model_info: Optional[ModelInfo] = None
        self._terminology: TerminologyStore = load_terminology_store()
        self._init_model()

    def _reload_terminology(self) -> None:
        self._terminology = load_terminology_store(self._terminology)

    def _init_model(self) -> None:
        spacy = _try_load_spacy()
        if spacy is None:
            logger.warning("spaCy is not installed")
            return

        preferred = os.getenv("SPACY_MODEL")
        candidates = [preferred] if preferred else []
        candidates += [
            "en_core_sci_md",
            "en_core_sci_sm",
            "en_ner_bc5cdr_md",
            "en_core_web_sm",
        ]

        for name in [c for c in candidates if c]:
            try:
                nlp = spacy.load(name)
                try:
                    if "abbreviation_detector" not in nlp.pipe_names:
                        nlp.add_pipe("abbreviation_detector")
                except Exception:
                    pass
                self._nlp = nlp
                self._model_info = ModelInfo(name=name, source="spacy.load")
                return
            except Exception:
                continue

        try:
            nlp = spacy.blank("en")
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")
            self._nlp = nlp
            self._model_info = ModelInfo(name="blank_en", source="spacy.blank")
        except Exception:
            self._nlp = None
            self._model_info = None

    def _abbr_entities(self, text: str) -> List[ExtractedEntity]:
        self._reload_terminology()
        diag = self._terminology.payload["diagnosis_abbrev"]
        meds = self._terminology.payload["medication_abbrev"]
        entities: List[ExtractedEntity] = []
        for abbr, canonical in diag.items():
            pattern = re.compile(rf"\b{re.escape(abbr)}\b", flags=re.IGNORECASE)
            for m in pattern.finditer(text):
                entities.append(
                    ExtractedEntity(
                        type="diagnosis",
                        value=canonical,
                        start=m.start(),
                        end=m.end(),
                        confidence=0.75,
                    )
                )
        for abbr, canonical in meds.items():
            pattern = re.compile(rf"\b{re.escape(abbr)}\b", flags=re.IGNORECASE)
            for m in pattern.finditer(text):
                entities.append(
                    ExtractedEntity(
                        type="medication",
                        value=canonical,
                        start=m.start(),
                        end=m.end(),
                        confidence=0.75,
                    )
                )
        return entities

    def _keyword_procedures(self, text: str) -> List[ExtractedEntity]:
        procedure_terms = (
            "therapy",
            "surgery",
            "biopsy",
            "injection",
            "transfusion",
            "dialysis",
            "intubation",
            "ventilation",
            "imaging",
            "scan",
            "mri",
            "ct",
            "x-ray",
            "ultrasound",
        )
        pattern = re.compile(
            rf"\b(?:[a-z][a-z0-9\-]{{1,25}}\s+){{0,2}}(?:{'|'.join(map(re.escape, procedure_terms))})\b",
            flags=re.IGNORECASE,
        )
        entities: List[ExtractedEntity] = []
        for m in pattern.finditer(text):
            value = m.group(0).strip().lower()
            value = re.sub(
                r"^(?:started|start|begin|began|initiated|initiate|underwent|received|given|on)\s+",
                "",
                value,
            ).strip()
            if not value:
                continue
            entities.append(
                ExtractedEntity(
                    type="procedure",
                    value=value,
                    start=m.start(),
                    end=m.end(),
                    confidence=0.6,
                )
            )
        return entities

    def _spacy_entities(self, text: str) -> List[ExtractedEntity]:
        if self._nlp is None:
            return []

        doc = self._nlp(text)
        entities: List[ExtractedEntity] = []

        for ent in getattr(doc, "ents", []):
            label = (ent.label_ or "").upper()
            value = ent.text.strip().lower()
            if not value:
                continue

            etype: Optional[EntityType] = None
            if label in {"DISEASE", "DISORDER", "CONDITION", "PROBLEM"}:
                etype = "diagnosis"
            elif label in {"CHEMICAL", "DRUG", "MEDICATION"}:
                etype = "medication"
            elif label in {"PROCEDURE", "TREATMENT"}:
                etype = "procedure"

            if etype is None:
                continue

            entities.append(
                ExtractedEntity(
                    type=etype,
                    value=value,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=0.85,
                )
            )

        keywords = {
            "therapy",
            "surgery",
            "biopsy",
            "injection",
            "transfusion",
            "dialysis",
            "intubation",
            "ventilation",
            "imaging",
            "mri",
            "ct",
            "x-ray",
            "ultrasound",
            "scan",
        }
        try:
            noun_chunks = list(getattr(doc, "noun_chunks", []))
        except Exception:
            noun_chunks = []

        for chunk in noun_chunks:
            text_chunk = chunk.text.strip().lower()
            if not text_chunk or len(text_chunk) > 80:
                continue
            if any(k in text_chunk.split() or k in text_chunk for k in keywords):
                entities.append(
                    ExtractedEntity(
                        type="procedure",
                        value=text_chunk,
                        start=chunk.start_char,
                        end=chunk.end_char,
                        confidence=0.55,
                    )
                )

        return entities

    def _normalize_and_fuzzy(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        self._reload_terminology()
        diag_terms = self._terminology.payload["diagnosis_terms"]
        med_terms = self._terminology.payload["medication_terms"]

        try:
            from rapidfuzz import fuzz
            from rapidfuzz import process as rf_process
        except Exception:
            return entities

        def _best(query: str, choices: List[str]) -> Optional[tuple[str, float]]:
            if not query or not choices:
                return None
            hit = rf_process.extractOne(query, choices, scorer=fuzz.WRatio)
            if not hit:
                return None
            choice, score, _ = hit
            if score < 88:
                return None
            return str(choice), float(score) / 100.0

        out: List[ExtractedEntity] = []
        for e in entities:
            q = e.value.strip().lower()
            if not q:
                continue
            if e.type == "diagnosis":
                best = _best(q, diag_terms)
                if best:
                    out.append(
                        ExtractedEntity(
                            type=e.type,
                            value=best[0],
                            start=e.start,
                            end=e.end,
                            confidence=max(e.confidence, best[1]),
                        )
                    )
                else:
                    out.append(e)
            elif e.type == "medication":
                best = _best(q, med_terms)
                if best:
                    out.append(
                        ExtractedEntity(
                            type=e.type,
                            value=best[0],
                            start=e.start,
                            end=e.end,
                            confidence=max(e.confidence, best[1]),
                        )
                    )
                else:
                    out.append(e)
            else:
                out.append(e)
        return out

    def process(self, text: str, include_entities: bool = True) -> ProcessResponse:
        cleaned = _clean_text(text)
        if not cleaned:
            return ProcessResponse(diagnosis=[], procedures=[], medications=[], entities=[] if include_entities else None)

        entities = self._abbr_entities(cleaned) + self._keyword_procedures(cleaned) + self._spacy_entities(cleaned)
        entities = self._normalize_and_fuzzy(entities)
        diagnosis = _unique_preserve_order([e.value for e in entities if e.type == "diagnosis"])
        procedures = _unique_preserve_order([e.value for e in entities if e.type == "procedure"])
        medications = _unique_preserve_order([e.value for e in entities if e.type == "medication"])

        if not diagnosis and not procedures and not medications:
            fallback = extract_with_gemini(cleaned)
            if fallback is not None:
                return fallback

        return ProcessResponse(
            diagnosis=diagnosis,
            procedures=procedures,
            medications=medications,
            entities=entities if include_entities else None,
        )


pipeline = ClinicalNlpPipeline()
