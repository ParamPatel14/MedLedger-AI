from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.denial_layer.config import get_denial_email, get_denial_thresholds
from app.layers.denial_layer.email_ingestion import DenialEmailIngestionService, DenialEmailParser
from app.layers.denial_layer.service import DenialManagementAgent
from app.models.denial import Claim, CorrectionApplied, DenialEvent, Resubmission
from app.schemas.denial import (
    ClaimCreateIn,
    ClaimOut,
    ClaimOutcomeIn,
    ClaimStatusUpdateIn,
    DenialEmailParseIn,
    DenialGmailPullIn,
    DenialAgentRunOut,
)
from app.services.gmail import GmailApiClient


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


def _safe_number(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _safe_iso(dt: Any) -> str:
    if isinstance(dt, datetime):
        try:
            return dt.isoformat()
        except Exception:
            return ""
    return ""


def _claim_amount(claim_data: dict) -> float:
    if not isinstance(claim_data, dict):
        return 0.0
    billing = claim_data.get("billing")
    if isinstance(billing, dict):
        return _safe_number(billing.get("amount"))
    return 0.0


def _timeline_steps(
    *,
    claim: Claim,
    denials: List[DenialEvent],
    corrections: List[CorrectionApplied],
    resubmissions: List[Resubmission],
) -> List[Dict[str, Any]]:
    events: List[Tuple[str, datetime]] = []
    if getattr(claim, "created_at", None) is not None:
        events.append(("submitted", claim.created_at))

    for d in denials:
        ts = getattr(d, "created_at", None)
        if isinstance(ts, datetime):
            events.append(("denied", ts))

    for c in corrections:
        ts = getattr(c, "created_at", None)
        if isinstance(ts, datetime):
            events.append(("fixed", ts))

    for r in resubmissions:
        ts = getattr(r, "created_at", None)
        if isinstance(ts, datetime):
            events.append(("resubmitted", ts))

    terminal = str(getattr(claim, "status", "") or "").strip().lower()
    if terminal == "approved" and getattr(claim, "updated_at", None) is not None:
        events.append(("approved", claim.updated_at))

    events_sorted = sorted(events, key=lambda x: x[1])
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for step, ts in events_sorted:
        if step in seen:
            continue
        seen.add(step)
        out.append({"step": step, "timestamp": _safe_iso(ts)})
    return out


def _progress_from_state(claim: Claim, *, denials: int, corrections: int, resubmits: int) -> Dict[str, Any]:
    status = str(getattr(claim, "status", "") or "").strip().lower()
    if status == "approved":
        stage = "approved"
    elif resubmits > 0 or status == "resubmitted":
        stage = "resubmitted"
    elif corrections > 0:
        stage = "fixed"
    elif denials > 0 or status in {"denied", "query"}:
        stage = "denied"
    else:
        stage = "submitted"

    order = ["submitted", "denied", "fixed", "resubmitted", "approved"]
    try:
        idx = order.index(stage)
    except Exception:
        idx = 0
    pct = int(round((idx / max(1, (len(order) - 1))) * 100.0))
    return {"stage": stage, "percent": pct}


@router.get("/denials/dashboard")
def denial_dashboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    thresholds_cfg = get_denial_thresholds()
    triggers = thresholds_cfg.get("triggers") or {}
    watched_statuses = [str(x).strip().lower() for x in (triggers.get("activate_on_status") or []) if str(x).strip()]
    if not watched_statuses:
        watched_statuses = ["denied", "query"]

    claims = db.query(Claim).order_by(Claim.updated_at.desc()).limit(200).all()

    total_claims = len(claims)
    denied_claims_count = 0
    recovered_claims = 0
    revenue_recovered = 0.0
    automated_claims = 0

    rows: List[Dict[str, Any]] = []
    for claim in claims:
        denials = db.query(DenialEvent).filter(DenialEvent.claim_id == claim.id).order_by(DenialEvent.created_at.asc()).all()
        corrections = (
            db.query(CorrectionApplied).filter(CorrectionApplied.claim_id == claim.id).order_by(CorrectionApplied.created_at.asc()).all()
        )
        resubs = db.query(Resubmission).filter(Resubmission.claim_id == claim.id).order_by(Resubmission.created_at.asc()).all()

        denials_count = len([d for d in denials if str(getattr(d, "status", "") or "").strip().lower() in watched_statuses])
        if denials_count > 0:
            denied_claims_count += 1

        amount = _claim_amount(claim.claim_data or {})
        status = str(getattr(claim, "status", "") or "").strip().lower()
        if status == "approved" and denials_count > 0:
            recovered_claims += 1
            revenue_recovered += amount

        last_denial = denials[-1] if denials else None
        last_corr = corrections[-1] if corrections else None
        last_resub = resubs[-1] if resubs else None

        timeline = _timeline_steps(claim=claim, denials=denials, corrections=corrections, resubmissions=resubs)
        progress = _progress_from_state(claim, denials=denials_count, corrections=len(corrections), resubmits=len(resubs))

        if denials_count > 0 or status in watched_statuses:
            if denials_count > 0 and (len(corrections) > 0 or len(resubs) > 0):
                automated_claims += 1
            denial_types: List[str] = []
            if last_denial is not None and isinstance(getattr(last_denial, "structured_reasons", None), list):
                denial_types = [str(x.get("type") or "").strip() for x in (last_denial.structured_reasons or []) if isinstance(x, dict)]
                denial_types = [t for t in denial_types if t]
            rows.append(
                {
                    "claim_id": claim.id,
                    "record_id": claim.record_id,
                    "status": claim.status,
                    "amount": amount,
                    "denial_types": denial_types,
                    "denials_count": denials_count,
                    "corrections_count": len(corrections),
                    "resubmissions_count": len(resubs),
                    "last_denial_event_id": getattr(last_denial, "id", None),
                    "last_correction_id": getattr(last_corr, "id", None),
                    "last_resubmission_id": getattr(last_resub, "id", None),
                    "last_confidence": float(getattr(last_corr, "confidence", 0.0) or 0.0) if last_corr is not None else 0.0,
                    "progress": progress,
                    "timeline": timeline,
                    "updated_at": _safe_iso(getattr(claim, "updated_at", None)),
                }
            )

    recovered_pct = float(recovered_claims / max(1, denied_claims_count) * 100.0) if denied_claims_count else 0.0
    denial_rate_pct = float(denied_claims_count / max(1, total_claims) * 100.0) if total_claims else 0.0
    automation_pct = float(automated_claims / max(1, denied_claims_count) * 100.0) if denied_claims_count else 0.0

    return {
        "metrics": {
            "total_claims": total_claims,
            "denied_claims": denied_claims_count,
            "recovered_claims": recovered_claims,
            "recovered_percent": recovered_pct,
            "revenue_recovered": revenue_recovered,
            "denial_rate_percent": denial_rate_pct,
            "denial_reduction_percent": recovered_pct,
            "automation_percent": automation_pct,
        },
        "denied_claims": rows,
    }


@router.post("/denials/email/parse")
def parse_denial_email(payload: DenialEmailParseIn) -> Dict[str, Any]:
    parser = DenialEmailParser.from_default()
    parsed = parser.parse_text(text=str(payload.text or ""), meta={"source": "manual"})
    return {"claim_id": parsed.claim_id, "rejection_codes": parsed.rejection_codes, "raw_reason_text": parsed.raw_reason_text, "meta": parsed.meta}


@router.post("/denials/gmail/pull")
def pull_denial_emails(payload: DenialGmailPullIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    svc = DenialEmailIngestionService()
    return svc.ingest_gmail(
        db,
        query=payload.query,
        label_ids=payload.label_ids,
        max_results=int(payload.max_results or 10),
        run_agent=bool(payload.run_agent),
    )


@router.get("/denials/gmail/status")
def gmail_status() -> Dict[str, Any]:
    cfg = get_denial_email()
    gmail_cfg = cfg.get("gmail") or {}
    enabled = bool(gmail_cfg.get("enabled"))

    client = GmailApiClient.from_env()
    ready = client is not None and enabled

    return {
        "enabled": enabled,
        "ready": ready,
        "gmail": {
            "default_query": str(gmail_cfg.get("default_query") or ""),
            "label_ids": gmail_cfg.get("label_ids") if isinstance(gmail_cfg.get("label_ids"), list) else [],
            "max_results": int(gmail_cfg.get("max_results") or 0),
        },
        "env": {
            "has_client_id": bool((__import__("os").getenv("GMAIL_CLIENT_ID") or "").strip()),
            "has_client_secret": bool((__import__("os").getenv("GMAIL_CLIENT_SECRET") or "").strip()),
            "has_refresh_token": bool((__import__("os").getenv("GMAIL_REFRESH_TOKEN") or "").strip()),
            "user_id": str((__import__("os").getenv("GMAIL_USER_ID") or "").strip() or "me"),
        },
    }
