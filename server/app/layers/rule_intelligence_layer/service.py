from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.layers.rule_intelligence_layer.config import get_rule_confidence_config, get_rule_extraction_config
from app.layers.rule_intelligence_layer.email_ingestion import pull_gmail_policy_updates
from app.layers.rule_intelligence_layer.graph import RuleLangGraphPipeline
from app.layers.rule_intelligence_layer.pdf_ingestion import build_pdf_source_document
from app.layers.rule_intelligence_layer.types import RuleSourceDocument
from app.layers.rule_intelligence_layer.web_ingestion import build_web_source_document
from app.models.rule import InsuranceRule


class RuleIntelligenceService:
    def __init__(self) -> None:
        self._pipeline = RuleLangGraphPipeline()

    def ingest_documents(self, db: Session, *, docs: List[RuleSourceDocument]) -> Dict[str, Any]:
        return self._pipeline.run(db, docs=docs)

    def ingest_pdf(self, db: Session, *, tpa_name: str, filename: str, pdf_bytes: bytes) -> Dict[str, Any]:
        doc = build_pdf_source_document(tpa_name=tpa_name, filename=filename, pdf_bytes=pdf_bytes, meta={})
        return self.ingest_documents(db, docs=[doc])

    def ingest_email_text(self, db: Session, *, tpa_name: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        doc = RuleSourceDocument(source="email", tpa_name=str(tpa_name or "").strip(), text=str(text or ""), meta=meta or {})
        return self.ingest_documents(db, docs=[doc])

    def ingest_gmail(self, db: Session, *, query: str, label_ids: List[str], max_results: int) -> Dict[str, Any]:
        docs = pull_gmail_policy_updates(query=query, label_ids=label_ids, max_results=max_results)
        if not docs:
            return {"status": "ok", "candidates": 0, "stored": [], "detail": "no_messages_or_missing_credentials"}
        return self.ingest_documents(db, docs=docs)

    def ingest_web(self, db: Session, *, tpa_name: str, url: str) -> Dict[str, Any]:
        doc = build_web_source_document(tpa_name=tpa_name, url=url, meta={})
        return self.ingest_documents(db, docs=[doc])

    def validate_rule(self, db: Session, *, tpa: str, category: str, value: float, rule_type: Optional[str] = None) -> Dict[str, Any]:
        cfg = get_rule_confidence_config()
        min_use = float(cfg.get("min_use_confidence") or 1.0) if isinstance(cfg, dict) else 1.0

        q = db.query(InsuranceRule).filter(InsuranceRule.active == True)  # noqa: E712
        q = q.filter(InsuranceRule.tpa_name == str(tpa or "").strip(), InsuranceRule.category == str(category or "").strip())
        if str(rule_type or "").strip():
            q = q.filter(InsuranceRule.rule_type == str(rule_type or "").strip())
        q = q.filter(InsuranceRule.confidence >= float(min_use))
        q = q.order_by(desc(InsuranceRule.confidence), desc(InsuranceRule.effective_date), desc(InsuranceRule.updated_at))
        rule = q.first()

        if rule is None:
            return {"valid": False, "reason": "no_high_confidence_rule", "matched_rule": None, "escalate": True}

        eng = get_rule_extraction_config()
        rule_types = (eng.get("rule_types") or {}) if isinstance(eng, dict) else {}
        comparators = (rule_types.get("comparators") or {}) if isinstance(rule_types, dict) else {}
        mode = str(comparators.get(str(rule.rule_type or "").strip(), "") or "").strip().lower()

        ok = True
        reason = "ok"
        if mode == "max":
            if rule.value is None:
                ok = False
                reason = "rule_missing_numeric_value"
            else:
                ok = float(value or 0.0) <= float(rule.value or 0.0)
                if not ok:
                    reason = f"Exceeds {rule.value_text or rule.value} {rule.unit}".strip()
        elif mode == "min":
            if rule.value is None:
                ok = False
                reason = "rule_missing_numeric_value"
            else:
                ok = float(value or 0.0) >= float(rule.value or 0.0)
                if not ok:
                    reason = f"Below {rule.value_text or rule.value} {rule.unit}".strip()
        else:
            ok = False
            reason = "unknown_rule_type"

        return {
            "valid": bool(ok),
            "reason": str(reason),
            "escalate": bool(not ok and reason in {"unknown_rule_type", "rule_missing_numeric_value"}),
            "matched_rule": {
                "id": rule.id,
                "tpa_name": rule.tpa_name,
                "rule_type": rule.rule_type,
                "category": rule.category,
                "value": rule.value,
                "value_text": rule.value_text,
                "unit": rule.unit,
                "conditions": rule.conditions or {},
                "confidence": float(rule.confidence or 0.0),
                "source": rule.source,
                "version": int(rule.version or 0),
                "effective_date": rule.effective_date.isoformat() if rule.effective_date else None,
            },
        }
