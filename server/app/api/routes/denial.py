from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.denial_layer.config import get_denial_thresholds
from app.layers.denial_layer.service import DenialManagementAgent
from app.models.denial import Claim, DenialEvent
from app.schemas.denial import (
    ClaimCreateIn,
    ClaimOut,
    ClaimOutcomeIn,
    ClaimStatusUpdateIn,
    DenialAgentRunOut,
)


router = APIRouter(tags=["denials"])


@router.post("/claims", response_model=ClaimOut)
def create_claim(payload: ClaimCreateIn, db: Session = Depends(get_db)) -> ClaimOut:
    row = Claim(record_id=payload.record_id, status=str(payload.status or "pending"), claim_data=payload.claim_data or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return ClaimOut(id=row.id, record_id=row.record_id, status=row.status, claim_data=row.claim_data or {})


@router.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, db: Session = Depends(get_db)) -> ClaimOut:
    row = db.query(Claim).filter(Claim.id == claim_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ClaimOut(id=row.id, record_id=row.record_id, status=row.status, claim_data=row.claim_data or {})


@router.post("/claims/status", response_model=DenialAgentRunOut)
def post_claim_status_update(payload: ClaimStatusUpdateIn, db: Session = Depends(get_db)) -> DenialAgentRunOut:
    claim = db.query(Claim).filter(Claim.id == payload.claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    thresholds_cfg = get_denial_thresholds()
    triggers = thresholds_cfg.get("triggers") or {}
    activate = {str(x).strip().lower() for x in (triggers.get("activate_on_status") or []) if str(x).strip()}
    status = str(payload.status or "").strip()
    status_norm = status.lower()

    claim.status = status
    db.commit()

    if activate and status_norm not in activate:
        return DenialAgentRunOut(status="ignored", denial_reason=None, root_cause=None, action_taken=None, confidence=0.0, audit={})

    ev = DenialEvent(
        claim_id=claim.id,
        status=status_norm,
        raw_reason_text=str(payload.tpa_response_text or ""),
        rejection_codes=list(payload.rejection_codes or []),
        structured_reasons=[],
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    agent = DenialManagementAgent()
    out = agent.run_for_denial_event(db, claim_id=claim.id, denial_event_id=ev.id)
    return DenialAgentRunOut(**out)


@router.post("/claims/{claim_id}/denials/{denial_event_id}/run", response_model=DenialAgentRunOut)
def run_denial_agent(claim_id: str, denial_event_id: int, db: Session = Depends(get_db)) -> DenialAgentRunOut:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    ev = db.query(DenialEvent).filter(DenialEvent.id == int(denial_event_id)).first()
    if ev is None or ev.claim_id != claim.id:
        raise HTTPException(status_code=404, detail="Denial event not found")
    agent = DenialManagementAgent()
    out = agent.run_for_denial_event(db, claim_id=claim.id, denial_event_id=ev.id)
    return DenialAgentRunOut(**out)


@router.post("/claims/outcome", response_model=DenialAgentRunOut)
def post_claim_outcome(payload: ClaimOutcomeIn, db: Session = Depends(get_db)) -> DenialAgentRunOut:
    claim = db.query(Claim).filter(Claim.id == payload.claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    agent = DenialManagementAgent()
    agent.record_outcome(db, claim_id=claim.id, outcome_status=str(payload.outcome_status or ""))
    return DenialAgentRunOut(status="recorded", denial_reason=None, root_cause=None, action_taken=None, confidence=0.0, audit={})
