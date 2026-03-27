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
from app.models.workflow import WorkflowRecord
from app.services.gemini import indian_payer_rules_fallback


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
        icd_items = [c for c in (coding.icd_codes or []) if isinstance(c, dict)]
        icd_codes = [str(c.get("code") or "").strip().upper() for c in icd_items]
        diagnoses = [str(d or "").strip().lower() for d in (clinical.diagnosis or [])]
        procedures = [str(p or "").strip().lower() for p in (clinical.procedures or [])]

        issues: List[dict] = []
        thr = rules.get("thresholds", {}) if isinstance(rules.get("thresholds"), dict) else {}
        flags = rules.get("flags", {}) if isinstance(rules.get("flags"), dict) else {}
        scoring = rules.get("scoring", {}) if isinstance(rules.get("scoring"), dict) else {}

        try:
            min_clinical_conf = float(thr.get("min_clinical_confidence", 0.4))
        except Exception:
            min_clinical_conf = 0.4
        try:
            min_icd_similarity = float(thr.get("min_icd_similarity", 0.65))
        except Exception:
            min_icd_similarity = 0.65
        if float(getattr(clinical, "confidence", 0.0) or 0.0) < min_clinical_conf:
            issues.append({"type": "ambiguous_diagnosis", "severity": "warning", "message": "Clinical extraction confidence is low; diagnosis may be ambiguous."})

        def _safe_score(item: dict) -> float:
            try:
                return float(item.get("score") or 0.0)
            except Exception:
                return 0.0

        def _category(code: str) -> str:
            c = (code or "").strip().upper().replace(".", "")
            if len(c) >= 3 and c[0].isalpha() and c[1:3].isdigit():
                return c[:3]
            return c

        best_by_source: Dict[str, dict] = {}
        for item in icd_items:
            code = str(item.get("code") or "").strip().upper()
            if not code:
                continue
            source = str(item.get("source_text") or "").strip().lower()
            key = source or _category(code)
            prev = best_by_source.get(key)
            if prev is None or _safe_score(item) > _safe_score(prev):
                best_by_source[key] = item

        primary_items = list(best_by_source.values())
        primary_categories = [_category(str(it.get("code") or "")) for it in primary_items if str(it.get("code") or "").strip()]
        primary_categories = [c for c in primary_categories if c]
        primary_set = set(primary_categories)

        ambiguous_terms = [str(x).strip().lower() for x in (rules.get("ambiguous_terms") or []) if str(x).strip()]
        if ambiguous_terms and bool(flags.get("flag_ambiguous_terms", True)):
            rec = db.query(WorkflowRecord).filter(WorkflowRecord.id == record_id).first()
            raw_text = (getattr(rec, "raw_text", "") or "").lower()
            for term in ambiguous_terms:
                if term and term in raw_text:
                    issues.append({"type": "ambiguous_terms", "severity": "warning", "message": f"Ambiguous language detected: '{term}'"})
                    break

        uncertain = [c for c in primary_items if bool(c.get("is_uncertain")) or _safe_score(c) < min_icd_similarity]
        if uncertain and bool(flags.get("flag_unknown_if_uncertain_code", True)):
            issues.append({"type": "unknown_condition", "severity": "warning", "message": "One or more ICD mappings are low-confidence; manual review recommended."})

        ruleset = rules.get("rules") or {}

        pairs = ruleset.get("incompatible_code_pairs", [])
        if isinstance(pairs, list):
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                codes = [str(c).strip().upper() for c in (pair.get("codes") or []) if str(c).strip()]
                severity = str(pair.get("severity") or "warning").lower()
                message = str(pair.get("message") or "").strip() or "Incompatible code pair"
                if len(codes) >= 2:
                    matched = [c for c in codes if any(cat.startswith(c) for cat in primary_categories)]
                    if len(matched) >= 2:
                        issues.append({"type": "incompatible_codes", "severity": severity, "codes": matched, "message": message})

        groups = ruleset.get("mutually_exclusive_groups", [])
        if isinstance(groups, list):
            for g in groups:
                if not isinstance(g, dict):
                    continue
                group = [str(x).strip().upper() for x in (g.get("group") or []) if str(x).strip()]
                sev = str(g.get("severity") or "critical").lower()
                msg = str(g.get("message") or "Mutually exclusive group violation")
                matched = [x for x in group if any(cat.startswith(x) for cat in primary_categories)]
                if len(matched) > 1:
                    issues.append({"type": "mutually_exclusive", "severity": sev, "codes": matched, "message": msg})

        supporting = ruleset.get("required_supporting_diagnosis", [])
        if isinstance(supporting, list):
            for rule in supporting:
                if not isinstance(rule, dict):
                    continue
                code = str(rule.get("code") or "").strip().upper()
                requires_any = [str(x).strip().upper() for x in (rule.get("requires_any_of") or []) if str(x).strip()]
                sev = str(rule.get("severity") or "critical").lower()
                msg = str(rule.get("message") or "")
                if not code or not requires_any:
                    continue
                if any(cat.startswith(code) for cat in primary_categories) and not any(any(cat.startswith(req) for cat in primary_categories) for req in requires_any):
                    issues.append({"type": "missing_supporting_diagnosis", "severity": sev, "codes": [code], "message": msg or f"{code} requires {requires_any}"})

        proc_links = ruleset.get("procedure_diagnosis_links", [])
        if isinstance(proc_links, list):
            for rule in proc_links:
                if not isinstance(rule, dict):
                    continue
                proc = str(rule.get("procedure") or "").strip().lower()
                req = [str(x).strip().upper() for x in (rule.get("requires") or []) if str(x).strip()]
                sev = str(rule.get("severity") or "critical").lower()
                msg = str(rule.get("message") or "")
                if not proc or not req:
                    continue
                if any(proc in p for p in procedures) and not any(any(cat.startswith(r) for cat in primary_categories) for r in req):
                    issues.append({"type": "procedure_requires_diagnosis", "severity": sev, "procedure": proc, "message": msg or f"{proc} requires codes {req}"})

        consistency = ruleset.get("clinical_consistency_rules", [])
        if isinstance(consistency, list):
            for rule in consistency:
                if not isinstance(rule, dict):
                    continue
                diag = str(rule.get("diagnosis") or "").strip().lower()
                expected = [str(x).strip().upper() for x in (rule.get("expected_codes") or []) if str(x).strip()]
                sev = str(rule.get("severity") or "warning").lower()
                msg = str(rule.get("message") or "")
                if not diag or not expected:
                    continue
                if any(diag in d for d in diagnoses) and not any(any(cat.startswith(prefix) for cat in primary_categories) for prefix in expected):
                    issues.append({"type": "diagnosis_code_mismatch", "severity": sev, "diagnosis": diag, "message": msg or f"{diag} expects codes {expected}"})

        chronic = ruleset.get("chronic_condition_requirements", [])
        if isinstance(chronic, list):
            for rule in chronic:
                if not isinstance(rule, dict):
                    continue
                prefix = str(rule.get("code_prefix") or "").strip().upper()
                sev = str(rule.get("severity") or "info").lower()
                msg = str(rule.get("message") or "")
                if prefix and any(cat.startswith(prefix) for cat in primary_categories):
                    issues.append({"type": "chronic_followup", "severity": sev, "code_prefix": prefix, "message": msg or f"Codes with prefix {prefix} may require follow-up"})

        dup_cfg = ruleset.get("duplicate_code_detection", {})
        if isinstance(dup_cfg, dict) and bool(dup_cfg.get("enabled", True)):
            seen = set()
            dups = set()
            for code in primary_categories:
                if code in seen:
                    dups.add(code)
                seen.add(code)
            if dups:
                issues.append({"type": "duplicate_codes", "severity": str(dup_cfg.get("severity", "warning")).lower(), "codes": sorted(list(dups)), "message": str(dup_cfg.get("message") or "Duplicate ICD codes detected")})

        unk_cfg = ruleset.get("unknown_code_handling", {})
        if isinstance(unk_cfg, dict) and bool(unk_cfg.get("enabled", True)):
            low = [c for c in primary_items if _safe_score(c) < min_icd_similarity]
            if low:
                issues.append({"type": "unknown_code", "severity": str(unk_cfg.get("severity", "warning")).lower(), "message": str(unk_cfg.get("message") or "Code could not be confidently mapped")})

        age_rules = ruleset.get("age_gender_rules", [])
        if isinstance(age_rules, list):
            for rule in age_rules:
                if not isinstance(rule, dict):
                    continue
                code = str(rule.get("code") or "").strip().upper()
                msg = str(rule.get("message") or "")
                if any(cat.startswith(code) for cat in primary_categories):
                    issues.append({"type": "demographic_rule_skipped", "severity": "info", "message": msg or "Demographic check skipped: age/gender not provided"})

        # Gemini fallback when local rules yield no issues
        if not issues:
            rec = db.query(WorkflowRecord).filter(WorkflowRecord.id == record_id).first()
            raw_text = getattr(rec, "raw_text", "") or ""
            try:
                g = indian_payer_rules_fallback(raw_text, diagnoses, procedures, icd_items)
            except Exception:
                g = None
            if g and isinstance(g.get("issues"), list) and g["issues"]:
                issues.extend(g["issues"])

        base_score = float(scoring.get("base_score", 1.0) or 1.0)
        pen_warn = float(scoring.get("penalty_per_warning", 0.05) or 0.05)
        pen_err = float(scoring.get("penalty_per_error", 0.15) or 0.15)
        pen_crit = float(scoring.get("critical_penalty", 0.4) or 0.4)
        min_ok = float(scoring.get("min_acceptable_score", 0.6) or 0.6)

        score = base_score
        has_crit = False
        for it in issues:
            sev = str(it.get("severity") or "warning").lower()
            if sev == "critical":
                score -= pen_crit
                has_crit = True
            elif sev == "warning":
                score -= pen_warn
            elif sev == "error":
                score -= pen_err
        score = max(0.0, min(1.0, score))

        is_valid = (not has_crit) and (score >= min_ok)
        confidence = score
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
