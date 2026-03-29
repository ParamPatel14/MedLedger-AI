from __future__ import annotations

import threading
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, ensure_db_initialized, get_db
from app.layers.explainability_layer.service import ExplainabilityService
from app.layers.governance_layer.service import GovernanceLayer
from app.layers.svm_layer.service import SvmMiddleware
from app.layers.workflow_layer.agents import ClinicalUnderstandingAgent, CodingAgent, PayerRuleAgent
from app.layers.workflow_layer.orchestrator import LangGraphOrchestrator
from app.models.denial import Claim, DenialEvent
from app.models.workflow import WorkflowRecord, WorkflowState
from app.models.explainability import ExplainabilityAuditTrail
from app.schemas.denial import VapiOutboundCallIn
from app.schemas.process import (
    AgentFlowStepOut,
    ClinicalAgentOut,
    CodingAgentOut,
    ExplainabilityAuditOut,
    OneClickStartIn,
    OneClickStartOut,
    OneClickStatusOut,
    ProcessExplainOut,
    GovernanceOut,
    PayerAgentOut,
    ProcessIn,
    ProcessOut,
    ProcessTraceOut,
    ValidationOut,
)


router = APIRouter(tags=["process"])
_explain = ExplainabilityService()

_oneclick_lock = threading.Lock()
_oneclick_runs: dict[str, dict] = {}


def _oneclick_snapshot(run_id: str) -> dict:
    with _oneclick_lock:
        return dict(_oneclick_runs.get(run_id) or {})


def _oneclick_set(run_id: str, **updates: dict) -> None:
    with _oneclick_lock:
        cur = dict(_oneclick_runs.get(run_id) or {})
        cur.update(updates)
        _oneclick_runs[run_id] = cur


def _oneclick_event(run_id: str, step: str, message: str, extra: dict | None = None) -> None:
    ev = {
        "ts": time.time(),
        "step": str(step or ""),
        "message": str(message or ""),
    }
    if isinstance(extra, dict) and extra:
        ev.update(extra)
    with _oneclick_lock:
        cur = dict(_oneclick_runs.get(run_id) or {})
        events = list(cur.get("events") or [])
        events.append(ev)
        cur["events"] = events[-200:]
        _oneclick_runs[run_id] = cur


def _needs_human_review(*, svm_status: str, governance: dict | None, payer: dict | None) -> tuple[bool, str]:
    gov = governance if isinstance(governance, dict) else {}
    decision = str(gov.get("decision") or "").strip().upper() or "APPROVE"
    if decision in {"BLOCK", "ESCALATE"}:
        return True, decision
    if str(svm_status or "").strip().lower() != "pass":
        return True, decision
    p = payer if isinstance(payer, dict) else {}
    if bool(p.get("is_valid")) is False:
        return True, decision
    return False, decision


def _build_claim_data(*, record_id: str, text: str, clinical: dict, coding: dict) -> dict:
    return {
        "record_id": record_id,
        "raw_text": text,
        "clinical": clinical if isinstance(clinical, dict) else {},
        "coding": {"icd_codes": list((coding or {}).get("icd_codes") or [])},
        "billing": {"amount": 5000.0, "currency": "INR"},
        "available_documents": ["discharge_summary", "operative_notes", "lab_reports"],
        "attachments": [],
    }


def _simulate_denial_reason(claim_data: dict) -> str:
    docs = (claim_data or {}).get("attachments")
    if not isinstance(docs, list) or not docs:
        return "Missing document: please attach discharge summary."
    return ""


def _run_oneclick_background(*, run_id: str, payload: OneClickStartIn) -> None:
    ensure_db_initialized()
    if SessionLocal is None:
        _oneclick_set(run_id, status="error", step="db")
        _oneclick_event(run_id, "db", "Database session is not initialized")
        return

    from app.api.routes.denial import vapi_start_outbound_call, vapi_sync_call
    from app.layers.denial_layer.service import DenialManagementAgent

    _oneclick_set(run_id, status="running", step="analysis")
    _oneclick_event(run_id, "analysis", "Running agent workflow (clinical → coding → rules → verification → governance)")

    db = SessionLocal()
    try:
        text = str(payload.text or "").strip()
        record = WorkflowRecord(raw_text=text)
        db.add(record)
        db.commit()

        db.add(WorkflowState(record_id=record.id, current_step="clinical", status="pending", errors={}))
        db.commit()

        orchestrator = LangGraphOrchestrator(
            clinical_agent=ClinicalUnderstandingAgent(),
            coding_agent=CodingAgent(),
            payer_rule_agent=PayerRuleAgent(),
            svm=SvmMiddleware(),
            governance=GovernanceLayer(),
        )
        state = orchestrator.run(db, record_id=record.id, raw_text=text)

        clinical = state.get("clinical") or {}
        coding = state.get("coding") or {}
        validation = state.get("validation") or {}
        errors = state.get("errors") or {}
        svm = state.get("svm") or {}
        governance = state.get("governance") or {}
        svm_status = SvmMiddleware.overall_status(svm if isinstance(svm, dict) else {})
        override_guardrails = bool(getattr(payload, "override_guardrails", False))

        if errors:
            _oneclick_set(run_id, status="error", step="analysis", record_id=str(record.id), output={"errors": errors})
            _oneclick_event(run_id, "analysis", "Agent workflow failed", {"errors": errors})
            return

        needs_review, decision = _needs_human_review(
            svm_status=svm_status,
            governance=governance if isinstance(governance, dict) else None,
            payer=validation if isinstance(validation, dict) else None,
        )
        _oneclick_set(
            run_id,
            record_id=str(record.id),
            decision=decision,
            output={
                "svm_status": svm_status,
                "svm": svm,
                "governance": governance,
                "payer": validation,
                "clinical": clinical,
                "coding": coding,
                "override_guardrails": override_guardrails,
            },
        )

        if needs_review:
            if not override_guardrails:
                _oneclick_set(run_id, status="needs_review", step="review")
                _oneclick_event(run_id, "review", "Stopped for human review (verification/guardrails did not pass)")
                return
            _oneclick_event(run_id, "override", "Override enabled; continuing despite verification/guardrails")

        _oneclick_set(run_id, step="submit")
        _oneclick_event(run_id, "submit", "Submitting claim to insurer (simulated)")

        claim = Claim(record_id=str(record.id), status="submitted", claim_data=_build_claim_data(record_id=str(record.id), text=text, clinical=clinical, coding=coding))
        db.add(claim)
        db.commit()
        db.refresh(claim)
        _oneclick_set(run_id, claim_id=str(claim.id))

        _oneclick_set(run_id, step="denial_check")
        _oneclick_event(run_id, "denial_check", "Checking for denial (simulated)")

        denial_text = _simulate_denial_reason(claim.claim_data or {})
        if not denial_text:
            claim.status = "approved"
            db.commit()
            _oneclick_set(run_id, status="done", step="approved")
            _oneclick_event(run_id, "approved", "Claim approved")
            return

        claim.status = "denied"
        db.commit()

        ev = DenialEvent(
            claim_id=str(claim.id),
            status="denied",
            raw_reason_text=str(denial_text),
            rejection_codes=[],
            structured_reasons=[],
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        _oneclick_set(run_id, denial_event_id=int(ev.id), step="denial_recovery")
        _oneclick_event(run_id, "denial_recovery", "Denial detected; starting recovery workflow")

        if not str(ev.raw_reason_text or "").strip() and bool(payload.auto_call_if_needed):
            num = str(payload.insurer_number or "").strip()
            if num:
                _oneclick_set(run_id, step="call")
                _oneclick_event(run_id, "call", "Calling insurer to collect denial details")
                out = vapi_start_outbound_call(
                    VapiOutboundCallIn(claim_id=str(claim.id), denial_event_id=int(ev.id), insurer_number=num, force=True),
                    db,
                )
                call_id = str((out or {}).get("call_id") or "").strip()
                if call_id:
                    _oneclick_set(run_id, call_id=call_id)
                    _oneclick_event(run_id, "call", "Call started", {"call_id": call_id})
                    for _ in range(80):
                        res = vapi_sync_call({"call_id": call_id, "claim_id": str(claim.id), "denial_event_id": int(ev.id)}, db)
                        if bool((res or {}).get("stored")):
                            _oneclick_event(run_id, "call", "Call transcript synced; denial details stored")
                            break
                        time.sleep(6)
            else:
                _oneclick_set(run_id, status="needs_review", step="call")
                _oneclick_event(run_id, "call", "Insurer phone number missing; cannot auto-call")
                return

        agent = DenialManagementAgent()
        out = agent.run_for_denial_event(db, claim_id=str(claim.id), denial_event_id=int(ev.id))
        _oneclick_set(run_id, output={**_oneclick_snapshot(run_id).get("output", {}), "denial_agent": out})

        if str((out or {}).get("status") or "").strip().lower() == "escalated":
            _oneclick_set(run_id, status="needs_review", step="denial_recovery")
            _oneclick_event(run_id, "denial_recovery", "Recovery escalated to human review")
            return

        _oneclick_set(run_id, step="outcome")
        _oneclick_event(run_id, "outcome", "Resubmitted; marking outcome as approved (simulated)")
        agent.record_outcome(db, claim_id=str(claim.id), outcome_status="approved")
        _oneclick_set(run_id, status="done", step="approved")
        _oneclick_event(run_id, "approved", "Claim approved after resubmission")
    except Exception as e:
        _oneclick_set(run_id, status="error", step=_oneclick_snapshot(run_id).get("step") or "error")
        _oneclick_event(run_id, "error", str(e))
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.post("/process", response_model=ProcessOut)
def process(payload: ProcessIn, db: Session = Depends(get_db)) -> ProcessOut:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    record = WorkflowRecord(raw_text=text)
    db.add(record)
    db.commit()

    db.add(WorkflowState(record_id=record.id, current_step="clinical", status="pending", errors={}))
    db.commit()

    orchestrator = LangGraphOrchestrator(
        clinical_agent=ClinicalUnderstandingAgent(),
        coding_agent=CodingAgent(),
        payer_rule_agent=PayerRuleAgent(),
        svm=SvmMiddleware(),
        governance=GovernanceLayer(),
    )
    state = orchestrator.run(db, record_id=record.id, raw_text=text)

    clinical = state.get("clinical") or {}
    coding = state.get("coding") or {}
    validation = state.get("validation") or {}
    errors = state.get("errors") or {}
    svm = state.get("svm") or {}
    governance = state.get("governance") or {}
    status = SvmMiddleware.overall_status(svm)

    if errors:
        raise HTTPException(status_code=422, detail={"record_id": record.id, "errors": errors})

    out = ProcessOut(
        status=status,
        decision=str((governance or {}).get("decision") or "APPROVE"),
        issues=list((governance or {}).get("issues") or []),
        audit_id=str((governance or {}).get("audit_id") or ""),
        diagnosis=list(clinical.get("diagnosis") or []),
        icd_codes=list(coding.get("icd_codes") or []),
        validation=ValidationOut(
            is_valid=bool(validation.get("is_valid")),
            issues=list(validation.get("issues") or []),
            confidence=float(validation.get("confidence") or 0.0),
        ),
        confidence=float((governance or {}).get("confidence") or 0.0),
        svm=svm,
        governance=GovernanceOut(
            decision=str((governance or {}).get("decision") or "APPROVE"),
            confidence=float((governance or {}).get("confidence") or 0.0),
            reason=str((governance or {}).get("reason") or ""),
            issues=list((governance or {}).get("issues") or []),
            audit_id=str((governance or {}).get("audit_id") or ""),
            refusal=(governance or {}).get("refusal"),
            escalation=(governance or {}).get("escalation"),
        )
        if isinstance(governance, dict) and governance
        else None,
    )
    return out


@router.post("/process/trace", response_model=ProcessTraceOut)
def process_trace(payload: ProcessIn, db: Session = Depends(get_db)) -> ProcessTraceOut:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    record = WorkflowRecord(raw_text=text)
    db.add(record)
    db.commit()

    db.add(WorkflowState(record_id=record.id, current_step="clinical", status="pending", errors={}))
    db.commit()

    orchestrator = LangGraphOrchestrator(
        clinical_agent=ClinicalUnderstandingAgent(),
        coding_agent=CodingAgent(),
        payer_rule_agent=PayerRuleAgent(),
        svm=SvmMiddleware(),
        governance=GovernanceLayer(),
    )
    state = orchestrator.run(db, record_id=record.id, raw_text=text)

    clinical = state.get("clinical") or {}
    coding = state.get("coding") or {}
    validation = state.get("validation") or {}
    errors = state.get("errors") or {}
    svm = state.get("svm") or {}
    governance = state.get("governance") or {}
    status = SvmMiddleware.overall_status(svm)
    if errors:
        raise HTTPException(status_code=422, detail={"record_id": record.id, "errors": errors})

    flow = [
        AgentFlowStepOut(agent="clinical", status="ok" if clinical else "skipped"),
        AgentFlowStepOut(agent="svm_after_clinical", status="ok" if (svm.get("svm_after_clinical") if isinstance(svm, dict) else None) else "skipped"),
        AgentFlowStepOut(agent="coding", status="ok" if coding else "skipped"),
        AgentFlowStepOut(agent="svm_after_coding", status="ok" if (svm.get("svm_after_coding") if isinstance(svm, dict) else None) else "skipped"),
        AgentFlowStepOut(agent="rule", status="ok" if validation else "skipped"),
        AgentFlowStepOut(agent="svm_after_rules", status="ok" if (svm.get("svm_after_rules") if isinstance(svm, dict) else None) else "skipped"),
        AgentFlowStepOut(agent="governance", status="ok" if governance else "skipped"),
    ]

    return ProcessTraceOut(
        record_id=record.id,
        flow=flow,
        clinical=ClinicalAgentOut(
            diagnosis=list(clinical.get("diagnosis") or []),
            procedures=list(clinical.get("procedures") or []),
            confidence=float(clinical.get("confidence") or 0.0),
            explanation=str(clinical.get("explanation") or ""),
        ),
        coding=CodingAgentOut(
            icd_codes=list(coding.get("icd_codes") or []),
            mapping_reason=str(coding.get("mapping_reason") or ""),
            confidence=float(coding.get("confidence") or 0.0),
        ),
        payer=PayerAgentOut(
            is_valid=bool(validation.get("is_valid")),
            issues=list(validation.get("issues") or []),
            confidence=float(validation.get("confidence") or 0.0),
        ),
        confidence=float(state.get("confidence") or 0.0),
        status=status,
        svm=svm,
        governance=GovernanceOut(
            decision=str((governance or {}).get("decision") or "APPROVE"),
            confidence=float((governance or {}).get("confidence") or 0.0),
            reason=str((governance or {}).get("reason") or ""),
            issues=list((governance or {}).get("issues") or []),
            audit_id=str((governance or {}).get("audit_id") or ""),
            refusal=(governance or {}).get("refusal"),
            escalation=(governance or {}).get("escalation"),
        )
        if isinstance(governance, dict) and governance
        else None,
    )


@router.post("/process/explain", response_model=ProcessExplainOut)
def process_explain(payload: ProcessIn, db: Session = Depends(get_db)) -> ProcessExplainOut:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    record = WorkflowRecord(raw_text=text)
    db.add(record)
    db.commit()

    db.add(WorkflowState(record_id=record.id, current_step="clinical", status="pending", errors={}))
    db.commit()

    orchestrator = LangGraphOrchestrator(
        clinical_agent=ClinicalUnderstandingAgent(),
        coding_agent=CodingAgent(),
        payer_rule_agent=PayerRuleAgent(),
        svm=SvmMiddleware(),
        governance=GovernanceLayer(),
    )
    state = orchestrator.run(db, record_id=record.id, raw_text=text)

    clinical = state.get("clinical") or {}
    coding = state.get("coding") or {}
    validation = state.get("validation") or {}
    errors = state.get("errors") or {}
    svm = state.get("svm") or {}
    governance = state.get("governance") or {}
    if errors:
        raise HTTPException(status_code=422, detail={"record_id": record.id, "errors": errors})

    clinical_conf = float((clinical or {}).get("confidence") or 0.0)
    coding_conf = float((coding or {}).get("confidence") or 0.0)
    rule_conf = float((validation or {}).get("confidence") or 0.0)
    total = 0.0
    n = 0
    for v in [clinical_conf, coding_conf, rule_conf]:
        if v:
            total += float(v)
            n += 1
    workflow_confidence = (total / n) if n else 0.0

    out = _explain.build_and_store(
        db,
        record_id=record.id,
        raw_text=text,
        clinical=clinical if isinstance(clinical, dict) else {},
        coding=coding if isinstance(coding, dict) else {},
        validation=validation if isinstance(validation, dict) else {},
        svm=svm if isinstance(svm, dict) else {},
        governance=governance if isinstance(governance, dict) else {},
        workflow_confidence=workflow_confidence,
    )
    return ProcessExplainOut(**out)


@router.get("/process/explain/audit/{audit_id}", response_model=ExplainabilityAuditOut)
def get_explainability_audit(audit_id: str, db: Session = Depends(get_db)) -> ExplainabilityAuditOut:
    aid = str(audit_id or "").strip()
    if not aid:
        raise HTTPException(status_code=400, detail="Missing audit_id")

    row = db.query(ExplainabilityAuditTrail).filter(ExplainabilityAuditTrail.audit_id == aid).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit not found")

    created_at = None
    try:
        created_at = row.created_at.isoformat() if row.created_at else None
    except Exception:
        created_at = None

    return ExplainabilityAuditOut(
        audit_id=str(row.audit_id),
        record_id=str(row.record_id),
        trace_id=str(row.trace_id or ""),
        decision=str(row.decision or ""),
        confidence=float(row.confidence or 0.0),
        raw_input=row.raw_input or {},
        agent_outputs=row.agent_outputs or {},
        svm_results=row.svm_results or {},
        policy=row.policy or {},
        final=row.final or {},
        explanations=row.explanations or [],
        trace=row.trace or {},
        confidence_breakdown=row.confidence_breakdown or {},
        formatting_version=str(row.formatting_version or ""),
        rules_version=str(row.rules_version or ""),
        human_summary=str(row.human_summary or ""),
        created_at=created_at,
    )


@router.post("/process/oneclick/start", response_model=OneClickStartOut)
def start_oneclick(payload: OneClickStartIn, background: BackgroundTasks) -> OneClickStartOut:
    rid = str(uuid.uuid4())
    _oneclick_set(rid, status="queued", step="queued", events=[], output={})
    background.add_task(_run_oneclick_background, run_id=rid, payload=payload)
    return OneClickStartOut(run_id=rid, status="queued", step="queued")


@router.get("/process/oneclick/{run_id}", response_model=OneClickStatusOut)
def get_oneclick(run_id: str) -> OneClickStatusOut:
    rid = str(run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="Missing run_id")
    snap = _oneclick_snapshot(rid)
    if not snap:
        raise HTTPException(status_code=404, detail="Run not found")
    return OneClickStatusOut(
        run_id=rid,
        status=str(snap.get("status") or "unknown"),
        step=str(snap.get("step") or "unknown"),
        record_id=snap.get("record_id"),
        claim_id=snap.get("claim_id"),
        denial_event_id=snap.get("denial_event_id"),
        call_id=snap.get("call_id"),
        decision=snap.get("decision"),
        output=snap.get("output") if isinstance(snap.get("output"), dict) else {},
        events=list(snap.get("events") or []),
    )
