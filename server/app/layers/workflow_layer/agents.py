from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.layers.coding_layer.service import IcdCodingService
from app.layers.processing_layer.service import ClinicalNlpService
from app.models.workflow import AgentOutput


def _clamp01(v: float) -> float:
    try:
        v = float(v)
    except Exception:
        return 0.0
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


@dataclass(frozen=True)
class ClinicalUnderstandingOut:
    diagnosis: List[str]
    procedures: List[str]
    confidence: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            "diagnosis": self.diagnosis,
            "procedures": self.procedures,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class CodingOut:
    icd_codes: List[dict]
    mapping_reason: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "icd_codes": self.icd_codes,
            "mapping_reason": self.mapping_reason,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PayerValidationOut:
    is_valid: bool
    issues: List[dict]
    confidence: float

    def to_dict(self) -> dict:
        return {"is_valid": self.is_valid, "issues": self.issues, "confidence": self.confidence}


class ClinicalUnderstandingAgent:
    name = "clinical_understanding"

    def __init__(self) -> None:
        self._nlp = ClinicalNlpService()

    def run(self, db: Session, *, record_id: str, raw_text: str) -> ClinicalUnderstandingOut:
        text = (raw_text or "").strip()
        if not text:
            raise ValueError("Missing input text")

        cleaned, entities = self._nlp.extract(text)
        diagnosis, procedures, _medications = self._nlp.summarize(entities)
        entity_conf = [float(getattr(e, "confidence", 0.0) or 0.0) for e in entities]
        avg_entity_conf = sum(entity_conf) / len(entity_conf) if entity_conf else 0.0

        found = len(diagnosis) + len(procedures)
        confidence = _clamp01(0.35 + 0.65 * avg_entity_conf) if found > 0 else 0.15
        explanation = f"Extracted {len(diagnosis)} diagnoses and {len(procedures)} procedures using {self._nlp.model_name or 'unknown'}."

        out = ClinicalUnderstandingOut(
            diagnosis=diagnosis,
            procedures=procedures,
            confidence=confidence,
            explanation=explanation,
        )

        db.add(
            AgentOutput(
                record_id=record_id,
                agent_name=self.name,
                input={"raw_text_len": len(text)},
                output=out.to_dict(),
                confidence=out.confidence,
            )
        )
        db.commit()
        return out


class CodingAgent:
    name = "coding"

    def __init__(self) -> None:
        self._coder = IcdCodingService()

    def _threshold(self) -> float:
        try:
            return float(os.getenv("ICD_MATCH_THRESHOLD") or 0.7)
        except Exception:
            return 0.7

    def run(self, db: Session, *, record_id: str, clinical: ClinicalUnderstandingOut, top_k: int = 3) -> CodingOut:
        if clinical is None:
            raise ValueError("Missing clinical data")
        diagnoses = [d for d in (clinical.diagnosis or []) if (d or "").strip()]
        if not diagnoses:
            out = CodingOut(icd_codes=[], mapping_reason="No diagnoses found to code.", confidence=0.1)
            db.add(
                AgentOutput(
                    record_id=record_id,
                    agent_name=self.name,
                    input={"diagnosis": clinical.diagnosis, "procedures": clinical.procedures},
                    output=out.to_dict(),
                    confidence=out.confidence,
                )
            )
            db.commit()
            return out

        threshold = self._threshold()
        icd_codes: List[dict] = []
        confidences: List[float] = []
        uncertain_diagnoses: List[str] = []
        for d in diagnoses:
            matches = self._coder.match_diagnosis(d, top_k=max(1, int(top_k)))
            best = max([float(getattr(m, "confidence", 0.0) or 0.0) for m in matches], default=0.0)
            if best < threshold:
                uncertain_diagnoses.append(d)
            for m in matches:
                score = float(m.confidence)
                icd_codes.append(
                    {
                        "system": "ICD10",
                        "code": m.code,
                        "description": m.description,
                        "score": score,
                        "source_text": m.source_text,
                        "method": m.method,
                        "is_uncertain": bool(score < threshold),
                    }
                )
                confidences.append(score)

        base = (sum(confidences) / len(confidences)) if confidences else 0.1
        penalty = (0.2 * len(uncertain_diagnoses) / max(1, len(diagnoses))) if uncertain_diagnoses else 0.0
        confidence = _clamp01(base - penalty)
        mapping_reason = "Mapped diagnoses to ICD-10 using semantic similarity against the ICD dataset embeddings."
        if uncertain_diagnoses:
            mapping_reason += f" Low-confidence/unknown diagnoses: {', '.join(uncertain_diagnoses)}."
        out = CodingOut(icd_codes=icd_codes, mapping_reason=mapping_reason, confidence=confidence)

        db.add(
            AgentOutput(
                record_id=record_id,
                agent_name=self.name,
                input={"diagnosis": clinical.diagnosis, "procedures": clinical.procedures},
                output=out.to_dict(),
                confidence=out.confidence,
            )
        )
        db.commit()
        return out


def _payer_rules_path() -> Path:
    configured = (os.getenv("PAYER_RULES_PATH") or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / "payer_rules.json"


def _load_payer_rules() -> Dict[str, Any]:
    path = _payer_rules_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


class PayerRuleAgent:
    name = "payer_rules"

    def run(self, db: Session, *, record_id: str, clinical: ClinicalUnderstandingOut, coding: CodingOut) -> PayerValidationOut:
        if coding is None:
            raise ValueError("Missing coding data")
        rules = _load_payer_rules()
        icd_codes = [str(c.get("code") or "").strip().upper() for c in (coding.icd_codes or []) if isinstance(c, dict)]
        diagnoses = [str(d or "").strip().lower() for d in (clinical.diagnosis or [])]

        issues: List[dict] = []
        try:
            min_clinical_conf = float(rules.get("min_clinical_confidence", 0.4))
        except Exception:
            min_clinical_conf = 0.4
        if float(getattr(clinical, "confidence", 0.0) or 0.0) < min_clinical_conf:
            issues.append({"type": "ambiguous_diagnosis", "message": "Clinical extraction confidence is low; diagnosis may be ambiguous."})

        uncertain = [c for c in (coding.icd_codes or []) if isinstance(c, dict) and bool(c.get("is_uncertain"))]
        if uncertain and bool(rules.get("flag_unknown_if_uncertain_code", True)):
            issues.append({"type": "unknown_condition", "message": "One or more ICD mappings are low-confidence; manual review recommended."})

        pairs = rules.get("incompatible_code_pairs", [])
        if isinstance(pairs, list):
            s = set(icd_codes)
            for pair in pairs:
                a = b = ""
                if isinstance(pair, dict):
                    a = str(pair.get("a") or "").strip().upper()
                    b = str(pair.get("b") or "").strip().upper()
                elif isinstance(pair, list) and len(pair) >= 2:
                    a = str(pair[0] or "").strip().upper()
                    b = str(pair[1] or "").strip().upper()
                if not a or not b:
                    continue
                if a in s and b in s:
                    issues.append({"type": "incompatible_codes", "codes": [a, b], "message": f"Codes {a} and {b} are incompatible per payer rules."})

        supporting = rules.get("required_supporting_diagnosis", [])
        if isinstance(supporting, list):
            for rule in supporting:
                if not isinstance(rule, dict):
                    continue
                target = str(rule.get("target_code") or "").strip().upper()
                if not target or target not in icd_codes:
                    continue
                required_terms = rule.get("required_terms", [])
                if isinstance(required_terms, str):
                    required_terms = [required_terms]
                required_terms = [str(t or "").strip().lower() for t in required_terms if str(t or "").strip()]
                if required_terms and not any(any(rt in d for d in diagnoses) for rt in required_terms):
                    msg = str(rule.get("message") or f"Code {target} requires supporting diagnosis terms: {', '.join(required_terms)}.")
                    issues.append({"type": "missing_supporting_diagnosis", "codes": [target], "message": msg})

        is_valid = len(issues) == 0
        confidence = 0.95 if is_valid else 0.7
        out = PayerValidationOut(is_valid=is_valid, issues=issues, confidence=_clamp01(confidence))

        db.add(
            AgentOutput(
                record_id=record_id,
                agent_name=self.name,
                input={"icd_codes": icd_codes, "diagnosis": clinical.diagnosis, "procedures": clinical.procedures},
                output=out.to_dict(),
                confidence=out.confidence,
            )
        )
        db.commit()
        return out
