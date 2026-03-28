from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.rule_intelligence_layer.service import RuleIntelligenceService
from app.models.rule import InsuranceRule, InsuranceRuleHistory
from app.schemas.rules import (
    RuleConflictsOut,
    RuleHistoryEventOut,
    RuleHistoryOut,
    RuleIngestEmailIn,
    RuleIngestGmailIn,
    RuleIngestOut,
    RuleListOut,
    RuleOut,
    RuleSummaryOut,
    RuleIngestWebIn,
    RuleUpdatesOut,
    RuleUpdateOut,
    ValidateRuleIn,
    ValidateRuleOut,
)


router = APIRouter(tags=["rules"])
_svc = RuleIntelligenceService()


@router.post("/rules/ingest/email", response_model=RuleIngestOut)
def ingest_email(payload: RuleIngestEmailIn, db: Session = Depends(get_db)) -> RuleIngestOut:
    out = _svc.ingest_email_text(db, tpa_name=payload.tpa_name, text=payload.text, meta={"source": "manual"})
    return RuleIngestOut(**out)


@router.post("/rules/ingest/gmail/pull", response_model=RuleIngestOut)
def ingest_gmail(payload: RuleIngestGmailIn, db: Session = Depends(get_db)) -> RuleIngestOut:
    out = _svc.ingest_gmail(db, query=payload.query, label_ids=payload.label_ids, max_results=int(payload.max_results or 10))
    return RuleIngestOut(**out)


@router.post("/rules/ingest/web", response_model=RuleIngestOut)
def ingest_web(payload: RuleIngestWebIn, db: Session = Depends(get_db)) -> RuleIngestOut:
    out = _svc.ingest_web(db, tpa_name=payload.tpa_name, url=payload.url)
    return RuleIngestOut(**out)


@router.post("/rules/ingest/pdf", response_model=RuleIngestOut)
async def ingest_pdf(tpa_name: str, file: UploadFile = File(...), db: Session = Depends(get_db)) -> RuleIngestOut:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    out = _svc.ingest_pdf(db, tpa_name=tpa_name, filename=str(file.filename or ""), pdf_bytes=data)
    return RuleIngestOut(**out)


@router.post("/validate_rule", response_model=ValidateRuleOut)
def validate_rule(payload: ValidateRuleIn, db: Session = Depends(get_db)) -> ValidateRuleOut:
    out = _svc.validate_rule(db, tpa=payload.tpa, category=payload.category, value=float(payload.value or 0.0), rule_type=payload.rule_type)
    return ValidateRuleOut(**out)


@router.get("/rules", response_model=RuleListOut)
def list_rules(
    tpa: str = "",
    category: str = "",
    rule_type: str = "",
    active: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> RuleListOut:
    q = db.query(InsuranceRule)
    if active:
        q = q.filter(InsuranceRule.active == True)  # noqa: E712
    if str(tpa or "").strip():
        q = q.filter(InsuranceRule.tpa_name == str(tpa).strip())
    if str(category or "").strip():
        q = q.filter(InsuranceRule.category == str(category).strip())
    if str(rule_type or "").strip():
        q = q.filter(InsuranceRule.rule_type == str(rule_type).strip())

    total = int(q.with_entities(func.count(InsuranceRule.id)).scalar() or 0)
    rows = q.order_by(InsuranceRule.updated_at.desc()).limit(int(limit or 50)).offset(int(offset or 0)).all()
    items = [
        RuleOut(
            id=r.id,
            tpa_name=r.tpa_name,
            rule_type=r.rule_type,
            category=r.category,
            value=r.value,
            value_text=r.value_text,
            unit=r.unit,
            conditions=r.conditions or {},
            confidence=float(r.confidence or 0.0),
            source=r.source,
            version=int(r.version or 0),
            effective_date=r.effective_date,
        )
        for r in rows
    ]
    return RuleListOut(items=items, total=total)


@router.get("/rules/{rule_id}/history", response_model=RuleHistoryOut)
def rule_history(rule_id: str, db: Session = Depends(get_db)) -> RuleHistoryOut:
    rid = str(rule_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="Missing rule_id")
    events = (
        db.query(InsuranceRuleHistory)
        .filter(InsuranceRuleHistory.rule_id == rid)
        .order_by(InsuranceRuleHistory.id.desc())
        .all()
    )
    return RuleHistoryOut(
        rule_id=rid,
        events=[
            RuleHistoryEventOut(
                id=int(e.id),
                rule_id=str(e.rule_id),
                from_version=int(e.from_version or 0),
                to_version=int(e.to_version or 0),
                diff=e.diff if isinstance(e.diff, dict) else {},
                changed_at=e.changed_at,
            )
            for e in events
        ],
    )


@router.get("/rules/summary", response_model=RuleSummaryOut)
def rule_summary(db: Session = Depends(get_db)) -> RuleSummaryOut:
    out = _svc.summary(db)
    return RuleSummaryOut(**out)


@router.get("/rules/updates", response_model=RuleUpdatesOut)
def rule_updates(limit: int = 25, db: Session = Depends(get_db)) -> RuleUpdatesOut:
    items = _svc.recent_updates(db, limit=int(limit or 25))
    return RuleUpdatesOut(items=[RuleUpdateOut(**x) for x in items])


@router.get("/rules/conflicts", response_model=RuleConflictsOut)
def rule_conflicts(limit_groups: int = 25, db: Session = Depends(get_db)) -> RuleConflictsOut:
    items = _svc.conflicts(db, limit_groups=int(limit_groups or 25))
    return RuleConflictsOut(items=items)
