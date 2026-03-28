from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.layers.rule_intelligence_layer.extraction_engine import RuleCandidate
from app.layers.rule_intelligence_layer.normalization import NormalizedRuleValue
from app.models.rule import InsuranceRule, InsuranceRuleHistory


def _stable_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        return json.dumps({}, sort_keys=True)


def compute_rule_key_hash(*, tpa_name: str, rule_type: str, category: str, conditions: Dict[str, Any]) -> str:
    payload = {"tpa_name": str(tpa_name or ""), "rule_type": str(rule_type or ""), "category": str(category or ""), "conditions": conditions or {}}
    raw = _stable_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _diff_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    keys = set(a.keys()) | set(b.keys())
    out: Dict[str, Any] = {}
    for k in sorted(keys):
        if a.get(k) != b.get(k):
            out[k] = {"from": a.get(k), "to": b.get(k)}
    return out


class RuleStorageService:
    def upsert(
        self,
        db: Session,
        *,
        candidate: RuleCandidate,
        normalized: NormalizedRuleValue,
        confidence: float,
        effective_date: Optional[date] = None,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Tuple[InsuranceRule, bool]:
        key_hash = compute_rule_key_hash(
            tpa_name=candidate.tpa_name,
            rule_type=candidate.rule_type,
            category=candidate.category,
            conditions=candidate.conditions,
        )

        existing = db.query(InsuranceRule).filter(InsuranceRule.key_hash == key_hash, InsuranceRule.active == True).first()  # noqa: E712

        new_payload: Dict[str, Any] = {
            "tpa_name": candidate.tpa_name,
            "rule_type": candidate.rule_type,
            "category": candidate.category,
            "value": normalized.value,
            "value_text": normalized.value_text,
            "unit": normalized.unit,
            "conditions": candidate.conditions,
            "confidence": float(confidence or 0.0),
            "source": candidate.source,
            "source_ref": candidate.source_ref,
            "source_excerpt": candidate.source_excerpt,
            "effective_date": effective_date.isoformat() if effective_date else None,
        }

        if existing is None:
            row = InsuranceRule(
                tpa_name=candidate.tpa_name,
                rule_type=candidate.rule_type,
                category=candidate.category,
                key_hash=key_hash,
                value=normalized.value,
                value_text=normalized.value_text,
                unit=normalized.unit,
                conditions=candidate.conditions,
                confidence=float(confidence or 0.0),
                source=candidate.source,
                source_ref=candidate.source_ref,
                source_excerpt=candidate.source_excerpt,
                version=1,
                effective_date=effective_date,
                active=True,
                meta={
                    "candidate": asdict(candidate),
                    "extra": extra_meta or {},
                },
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row, True

        prev_payload: Dict[str, Any] = {
            "tpa_name": existing.tpa_name,
            "rule_type": existing.rule_type,
            "category": existing.category,
            "value": existing.value,
            "value_text": existing.value_text,
            "unit": existing.unit,
            "conditions": existing.conditions or {},
            "confidence": float(existing.confidence or 0.0),
            "source": existing.source,
            "source_ref": existing.source_ref,
            "source_excerpt": existing.source_excerpt,
            "effective_date": existing.effective_date.isoformat() if existing.effective_date else None,
        }

        if prev_payload == new_payload:
            if float(existing.confidence or 0.0) != float(confidence or 0.0):
                existing.confidence = float(confidence or 0.0)
                existing.meta = {**(existing.meta or {}), "last_seen_candidate": asdict(candidate), "extra": extra_meta or {}}
                db.commit()
                db.refresh(existing)
            return existing, False

        from_version = int(existing.version or 1)
        to_version = from_version + 1
        hist = InsuranceRuleHistory(
            rule_id=existing.id,
            from_version=from_version,
            to_version=to_version,
            previous=prev_payload,
            current=new_payload,
            diff=_diff_dict(prev_payload, new_payload),
        )
        db.add(hist)

        existing.value = normalized.value
        existing.value_text = normalized.value_text
        existing.unit = normalized.unit
        existing.conditions = candidate.conditions
        existing.confidence = float(confidence or 0.0)
        existing.source = candidate.source
        existing.source_ref = candidate.source_ref
        existing.source_excerpt = candidate.source_excerpt
        existing.version = to_version
        existing.effective_date = effective_date or existing.effective_date
        existing.meta = {**(existing.meta or {}), "last_change": {"from_version": from_version, "to_version": to_version}, "last_seen_candidate": asdict(candidate), "extra": extra_meta or {}}

        db.commit()
        db.refresh(existing)
        return existing, True
