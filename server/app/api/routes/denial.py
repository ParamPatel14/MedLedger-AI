from __future__ import annotations

from datetime import datetime
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
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
    VapiOutboundCallIn,
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

def _extract_claim_id_from_text(text: str) -> str:
    t = str(text or "")
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", t)
    return str(m.group(0)) if m else ""


def _has_denial_details(ev: Optional[DenialEvent]) -> bool:
    if ev is None:
        return False
    if str(getattr(ev, "raw_reason_text", "") or "").strip():
        return True
    if isinstance(getattr(ev, "structured_reasons", None), list) and (ev.structured_reasons or []):
        return True
    if isinstance(getattr(ev, "rejection_codes", None), list) and (ev.rejection_codes or []):
        return True
    return False


def _denial_summary(claim: Claim, ev: Optional[DenialEvent]) -> Dict[str, Any]:
    cd = claim.claim_data or {}
    amount = _claim_amount(cd if isinstance(cd, dict) else {})
    out: Dict[str, Any] = {
        "claim_id": claim.id,
        "status": str(getattr(claim, "status", "") or ""),
        "amount": amount,
        "denial_event_id": getattr(ev, "id", None),
        "rejection_codes": list(getattr(ev, "rejection_codes", None) or []) if ev is not None else [],
        "raw_reason_text": str(getattr(ev, "raw_reason_text", "") or "") if ev is not None else "",
        "structured_reasons": list(getattr(ev, "structured_reasons", None) or []) if ev is not None else [],
        "updated_at": _safe_iso(getattr(claim, "updated_at", None)),
    }
    return out


def _vapi_cfg() -> Dict[str, str]:
    return {
        "api_key": str((os.getenv("VAPI_API_KEY") or "").strip()),
        "base_url": str((os.getenv("VAPI_BASE_URL") or "").strip() or "https://api.vapi.ai"),
        "assistant_id": str((os.getenv("VAPI_ASSISTANT_ID") or "").strip()),
        "phone_number_id": str((os.getenv("VAPI_PHONE_NUMBER_ID") or "").strip()),
        "webhook_url": str(_vapi_webhook_url() or "").strip(),
    }


def _vapi_webhook_url() -> str:
    explicit = str((os.getenv("VAPI_WEBHOOK_URL") or "").strip())
    if explicit:
        return explicit
    base = str((os.getenv("PUBLIC_BASE_URL") or "").strip())
    if not base:
        base = str((os.getenv("NGROK_URL") or "").strip())
    base = base.rstrip("/")
    if not base:
        return ""
    return base + "/denials/vapi/webhook"


@router.get("/denials/vapi/status")
def vapi_status() -> Dict[str, Any]:
    cfg = _vapi_cfg()
    return {
        "ready": bool(cfg["api_key"] and cfg["assistant_id"] and cfg["phone_number_id"]),
        "env": {
            "has_api_key": bool(cfg["api_key"]),
            "has_assistant_id": bool(cfg["assistant_id"]),
            "has_phone_number_id": bool(cfg["phone_number_id"]),
            "has_webhook_url": bool(cfg.get("webhook_url")),
            "webhook_url": cfg.get("webhook_url") or "",
            "base_url": cfg["base_url"],
        },
    }



def _vapi_post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _vapi_cfg()
    if not cfg["api_key"]:
        raise RuntimeError("Missing VAPI_API_KEY")
    url = cfg["base_url"].rstrip("/") + "/" + path.lstrip("/")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        raise RuntimeError(raw.strip() or f"Vapi request failed ({getattr(e, 'code', 0)})")
    except Exception as e:
        raise RuntimeError(str(e))
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {"raw": raw}


def _vapi_get_json(path: str) -> Dict[str, Any]:
    cfg = _vapi_cfg()
    if not cfg["api_key"]:
        raise RuntimeError("Missing VAPI_API_KEY")
    url = cfg["base_url"].rstrip("/") + "/" + path.lstrip("/")
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        raise RuntimeError(raw.strip() or f"Vapi request failed ({getattr(e, 'code', 0)})")
    except Exception as e:
        raise RuntimeError(str(e))
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {"raw": raw}


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    t = str(text or "").strip()
    if not t:
        return None
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None
    blob = t[start : end + 1]
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _coerce_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "yes", "y", "1"}:
        return True
    if s in {"false", "no", "n", "0"}:
        return False
    return None


def _normalize_vapi_output(obj: Dict[str, Any]) -> Dict[str, Any]:
    denial_reason = str(obj.get("denial_reason") or "").strip()
    root_cause = str(obj.get("root_cause") or "").strip()
    required_action = str(obj.get("required_action") or "").strip()
    resub_ok = _coerce_bool(obj.get("resubmission_possible"))
    conf = _safe_number(obj.get("confidence"))
    if conf < 0:
        conf = 0.0
    if conf > 1:
        conf = 1.0
    return {
        "denial_reason": denial_reason,
        "root_cause": root_cause,
        "required_action": required_action,
        "resubmission_possible": bool(resub_ok) if resub_ok is not None else False,
        "confidence": conf,
    }


def _find_denial_event_by_vapi_call_id(db: Session, call_id: str) -> Optional[DenialEvent]:
    if not call_id:
        return None
    rows = db.query(DenialEvent).order_by(DenialEvent.created_at.desc()).limit(500).all()
    for ev in rows:
        meta = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
        vapi = meta.get("vapi") if isinstance(meta.get("vapi"), dict) else {}
        if str(vapi.get("call_id") or "") == str(call_id):
            return ev
    return None


def _apply_vapi_structured_output_to_denial_event(db: Session, *, ev: DenialEvent, call_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
    candidates: List[str] = []
    summary = report.get("summary")
    transcript = report.get("transcript")
    if isinstance(summary, str) and summary.strip():
        candidates.append(summary)
    if isinstance(transcript, str) and transcript.strip():
        candidates.append(transcript)

    analysis = report.get("analysis") if isinstance(report.get("analysis"), dict) else {}
    if isinstance(analysis.get("summary"), str) and analysis.get("summary").strip():
        candidates.append(str(analysis.get("summary")))

    artifact = report.get("artifact") if isinstance(report.get("artifact"), dict) else {}
    msgs = artifact.get("messages")
    if isinstance(msgs, list):
        for m in reversed(msgs):
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "").strip().lower()
            txt = str(m.get("message") or m.get("content") or "").strip()
            if role == "assistant" and txt:
                candidates.append(txt)

    parsed_obj: Optional[Dict[str, Any]] = None
    for c in candidates:
        parsed_obj = _extract_json_object(c)
        if parsed_obj is not None:
            break

    normalized = _normalize_vapi_output(parsed_obj or {})

    meta = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
    vapi_meta = meta.get("vapi") if isinstance(meta.get("vapi"), dict) else {}
    vapi_meta["call_id"] = call_id
    vapi_meta["structured_output"] = normalized
    vapi_meta["last_report"] = report
    vapi_meta["updated_at"] = datetime.utcnow().isoformat()
    meta["vapi"] = vapi_meta
    ev.source_meta = meta

    if normalized.get("denial_reason"):
        ev.raw_reason_text = str(normalized.get("denial_reason") or "").strip()
    ev.structured_reasons = [
        {
            "type": "vapi_call",
            "denial_reason": normalized.get("denial_reason"),
            "root_cause": normalized.get("root_cause"),
            "required_action": normalized.get("required_action"),
            "resubmission_possible": bool(normalized.get("resubmission_possible")),
            "confidence": float(normalized.get("confidence") or 0.0),
        }
    ]
    db.commit()
    return normalized


@router.post("/denials/vapi/call")
def vapi_start_outbound_call(payload: VapiOutboundCallIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    insurer_number = str(payload.insurer_number or "").strip()
    if not insurer_number or not insurer_number.startswith("+"):
        raise HTTPException(status_code=400, detail="insurer_number must be E.164 format (example: +14155552671)")

    cfg = _vapi_cfg()
    assistant_id = str(payload.assistant_id or "").strip() or cfg["assistant_id"]
    phone_number_id = str(payload.phone_number_id or "").strip() or cfg["phone_number_id"]
    if not assistant_id:
        raise HTTPException(status_code=500, detail="Missing VAPI_ASSISTANT_ID")
    if not phone_number_id:
        raise HTTPException(status_code=500, detail="Missing VAPI_PHONE_NUMBER_ID")

    claim = db.query(Claim).filter(Claim.id == payload.claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    ev: Optional[DenialEvent] = None
    if payload.denial_event_id is not None:
        ev = db.query(DenialEvent).filter(DenialEvent.id == int(payload.denial_event_id)).first()
        if ev is not None and ev.claim_id != claim.id:
            ev = None
    if ev is None:
        ev = db.query(DenialEvent).filter(DenialEvent.claim_id == claim.id).order_by(DenialEvent.created_at.desc()).first()
    if ev is not None and _has_denial_details(ev):
        return {
            "ok": True,
            "skipped": True,
            "reason": "denial_details_already_present",
            "claim_id": claim.id,
            "denial_event_id": ev.id,
        }
    if ev is None:
        ev = DenialEvent(
            claim_id=claim.id,
            status=str(getattr(claim, "status", "") or "denied").strip().lower() or "denied",
            raw_reason_text="",
            rejection_codes=[],
            structured_reasons=[],
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

    variable_values = payload.variable_values if isinstance(payload.variable_values, dict) else {}
    base_vars = {
        "claim_id": claim.id,
        "denial_event_id": str(ev.id),
        "record_id": str(getattr(claim, "record_id", "") or ""),
    }
    merged_vars = {**base_vars, **variable_values}

    call_payload: Dict[str, Any] = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": {"number": insurer_number},
        "assistantOverrides": {"variableValues": merged_vars},
    }
    if cfg.get("webhook_url"):
        call_payload["webhookUrl"] = cfg["webhook_url"]

    try:
        created = _vapi_post_json("/call", call_payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    call_id = str((created or {}).get("id") or "").strip()
    meta = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
    meta["vapi"] = {
        "call_id": call_id,
        "insurer_number": insurer_number,
        "assistant_id": assistant_id,
        "phone_number_id": phone_number_id,
        "requested_at": datetime.utcnow().isoformat(),
        "call_create_response": created,
    }
    ev.source_meta = meta
    db.commit()

    return {
        "ok": True,
        "claim_id": claim.id,
        "denial_event_id": ev.id,
        "call_id": call_id,
        "status": str((created or {}).get("status") or ""),
        "monitor": (created or {}).get("monitor") if isinstance((created or {}).get("monitor"), dict) else {},
    }


@router.post("/denials/vapi/sync")
def vapi_sync_call(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    call_id = str((payload or {}).get("call_id") or "").strip()
    if not call_id:
        raise HTTPException(status_code=400, detail="Missing call_id")

    try:
        call_obj = _vapi_get_json(f"/call/{call_id}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    ev = _find_denial_event_by_vapi_call_id(db, call_id)
    claim_id = str((payload or {}).get("claim_id") or "").strip()
    denial_event_id = (payload or {}).get("denial_event_id")
    if ev is None and claim_id:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if claim is not None:
            if isinstance(denial_event_id, int):
                ev = db.query(DenialEvent).filter(DenialEvent.id == int(denial_event_id)).first()
                if ev is not None and ev.claim_id != claim.id:
                    ev = None
            if ev is None:
                ev = db.query(DenialEvent).filter(DenialEvent.claim_id == claim.id).order_by(DenialEvent.created_at.desc()).first()

    if ev is None:
        return {"ok": True, "synced": False, "reason": "no_matching_denial_event", "call_id": call_id, "call": call_obj}

    meta = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
    vapi_meta = meta.get("vapi") if isinstance(meta.get("vapi"), dict) else {}
    vapi_meta["synced_at"] = datetime.utcnow().isoformat()
    vapi_meta["call_get_response"] = call_obj
    meta["vapi"] = vapi_meta
    ev.source_meta = meta
    db.commit()

    status = str((call_obj or {}).get("status") or "").strip().lower()
    if status and status not in {"ended", "completed", "finished"}:
        return {"ok": True, "synced": True, "call_id": call_id, "status": status, "stored": False}

    normalized = _apply_vapi_structured_output_to_denial_event(db, ev=ev, call_id=call_id, report=call_obj)

    ran_agent = False
    agent_out: Optional[Dict[str, Any]] = None
    if _has_denial_details(ev):
        try:
            agent = DenialManagementAgent()
            agent_out = agent.run_for_denial_event(db, claim_id=ev.claim_id, denial_event_id=ev.id)
            ran_agent = True
        except Exception as e:
            meta2 = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
            vapi2 = meta2.get("vapi") if isinstance(meta2.get("vapi"), dict) else {}
            vapi2["agent_error"] = str(e)
            meta2["vapi"] = vapi2
            ev.source_meta = meta2
            db.commit()

    if ran_agent:
        meta3 = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
        vapi3 = meta3.get("vapi") if isinstance(meta3.get("vapi"), dict) else {}
        vapi3["agent_run"] = agent_out
        meta3["vapi"] = vapi3
        ev.source_meta = meta3
        db.commit()

    return {
        "ok": True,
        "synced": True,
        "call_id": call_id,
        "stored": True,
        "claim_id": ev.claim_id,
        "denial_event_id": ev.id,
        "structured_output": normalized,
        "ran_agent": ran_agent,
    }


@router.post("/denials/vapi/webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = payload.get("message") if isinstance(payload, dict) else None
    message = message if isinstance(message, dict) else {}
    msg_type = str(message.get("type") or "").strip()

    if msg_type != "end-of-call-report":
        return {"ok": True, "ignored": True, "type": msg_type}

    call = message.get("call") if isinstance(message.get("call"), dict) else {}
    call_id = str(call.get("id") or "").strip()
    ev = _find_denial_event_by_vapi_call_id(db, call_id)

    if ev is None:
        transcript = str(message.get("transcript") or "").strip()
        claim_id = _extract_claim_id_from_text(transcript)
        if claim_id:
            claim = db.query(Claim).filter(Claim.id == claim_id).first()
            if claim is not None:
                ev = db.query(DenialEvent).filter(DenialEvent.claim_id == claim.id).order_by(DenialEvent.created_at.desc()).first()

    if ev is None:
        return {"ok": True, "stored": False, "reason": "no_matching_denial_event", "call_id": call_id}

    normalized = _apply_vapi_structured_output_to_denial_event(db, ev=ev, call_id=call_id, report=message)

    ran_agent = False
    agent_out: Optional[Dict[str, Any]] = None
    if _has_denial_details(ev):
        try:
            agent = DenialManagementAgent()
            agent_out = agent.run_for_denial_event(db, claim_id=ev.claim_id, denial_event_id=ev.id)
            ran_agent = True
        except Exception as e:
            meta2 = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
            vapi2 = meta2.get("vapi") if isinstance(meta2.get("vapi"), dict) else {}
            vapi2["agent_error"] = str(e)
            meta2["vapi"] = vapi2
            ev.source_meta = meta2
            db.commit()

    if ran_agent:
        meta3 = ev.source_meta if isinstance(getattr(ev, "source_meta", None), dict) else {}
        vapi3 = meta3.get("vapi") if isinstance(meta3.get("vapi"), dict) else {}
        vapi3["agent_run"] = agent_out
        meta3["vapi"] = vapi3
        ev.source_meta = meta3
        db.commit()

    return {"ok": True, "stored": True, "call_id": call_id, "claim_id": ev.claim_id, "denial_event_id": ev.id, "ran_agent": ran_agent}
