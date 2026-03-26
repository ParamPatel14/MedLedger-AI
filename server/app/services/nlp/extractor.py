from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.term import ClinicalTerm
from app.schemas.nlp import ExtractedEntity, NlpExtractResponse


EntityType = Literal["diagnosis", "procedure"]


@dataclass(frozen=True)
class TermPattern:
    entity_type: EntityType
    canonical: str
    phrase: str
    pattern: re.Pattern[str]
    confidence: float


def _split_synonyms(raw: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[\n,;|]+", raw)
    return [p.strip() for p in parts if p and p.strip()]


def _compile_phrase_pattern(phrase: str) -> re.Pattern[str]:
    tokens = [t for t in phrase.strip().split() if t]
    if not tokens:
        return re.compile(r"(?!x)x")
    token_pattern = r"\s+".join(re.escape(t) for t in tokens)
    return re.compile(rf"\b{token_pattern}\b", flags=re.IGNORECASE)


def _is_negated(text: str, start: int) -> bool:
    window = text[max(0, start - 80) : start].lower()
    cues = ["no", "denies", "without", "negative for", "not"]
    for cue in cues:
        idx = window.rfind(cue)
        if idx != -1 and idx >= len(window) - 35:
            return True
    return False


def _build_patterns(db: Session) -> List[TermPattern]:
    rows = db.execute(select(ClinicalTerm).where(ClinicalTerm.enabled.is_(True))).scalars().all()
    patterns: List[TermPattern] = []
    for row in rows:
        entity_type: EntityType = "diagnosis" if row.type == "diagnosis" else "procedure"
        canonical = row.canonical.strip().lower()
        if not canonical:
            continue
        phrases = [row.canonical.strip()] + _split_synonyms(row.synonyms)
        for phrase in phrases:
            phrase_clean = phrase.strip()
            if not phrase_clean:
                continue
            patterns.append(
                TermPattern(
                    entity_type=entity_type,
                    canonical=canonical,
                    phrase=phrase_clean,
                    pattern=_compile_phrase_pattern(phrase_clean),
                    confidence=0.8 if phrase_clean.lower() == canonical else 0.75,
                )
            )
    return patterns


def extract_entities(db: Session, text: str) -> NlpExtractResponse:
    if not text or not text.strip():
        return NlpExtractResponse(diagnosis=[], procedures=[], entities=[])

    patterns = _build_patterns(db)
    entities: List[ExtractedEntity] = []
    diagnoses: List[str] = []
    procedures: List[str] = []

    for tp in patterns:
        for m in tp.pattern.finditer(text):
            start, end = m.start(), m.end()
            negated = _is_negated(text, start)
            entities.append(
                ExtractedEntity(
                    type=tp.entity_type,
                    value=tp.canonical,
                    start=start,
                    end=end,
                    confidence=tp.confidence,
                    negated=negated,
                )
            )
            if not negated:
                if tp.entity_type == "diagnosis" and tp.canonical not in diagnoses:
                    diagnoses.append(tp.canonical)
                if tp.entity_type == "procedure" and tp.canonical not in procedures:
                    procedures.append(tp.canonical)

    entities_sorted = sorted(entities, key=lambda e: (e.start, e.end, e.type, e.value))
    return NlpExtractResponse(diagnosis=diagnoses, procedures=procedures, entities=entities_sorted)

