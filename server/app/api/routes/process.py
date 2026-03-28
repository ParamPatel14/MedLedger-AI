from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.explainability_layer.service import ExplainabilityService
from app.layers.governance_layer.service import GovernanceLayer
from app.layers.svm_layer.service import SvmMiddleware
from app.layers.workflow_layer.agents import ClinicalUnderstandingAgent, CodingAgent, PayerRuleAgent
from app.layers.workflow_layer.orchestrator import LangGraphOrchestrator
from app.models.workflow import WorkflowRecord, WorkflowState
from app.models.explainability import ExplainabilityAuditTrail
from app.schemas.process import (
    AgentFlowStepOut,
    ClinicalAgentOut,
    CodingAgentOut,
    ExplainabilityAuditOut,
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
