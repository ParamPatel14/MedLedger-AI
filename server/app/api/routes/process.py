from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.workflow_layer.agents import ClinicalUnderstandingAgent, CodingAgent, PayerRuleAgent
from app.layers.workflow_layer.orchestrator import LangGraphOrchestrator
from app.models.workflow import WorkflowRecord, WorkflowState
from app.schemas.process import (
    AgentFlowStepOut,
    ClinicalAgentOut,
    CodingAgentOut,
    PayerAgentOut,
    ProcessIn,
    ProcessOut,
    ProcessTraceOut,
    ValidationOut,
)


router = APIRouter(tags=["process"])


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
    )
    state = orchestrator.run(db, record_id=record.id, raw_text=text)

    clinical = state.get("clinical") or {}
    coding = state.get("coding") or {}
    validation = state.get("validation") or {}
    errors = state.get("errors") or {}

    if errors:
        raise HTTPException(status_code=422, detail={"record_id": record.id, "errors": errors})

    out = ProcessOut(
        diagnosis=list(clinical.get("diagnosis") or []),
        icd_codes=list(coding.get("icd_codes") or []),
        validation=ValidationOut(
            is_valid=bool(validation.get("is_valid")),
            issues=list(validation.get("issues") or []),
            confidence=float(validation.get("confidence") or 0.0),
        ),
        confidence=float(state.get("confidence") or 0.0),
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
    )
    state = orchestrator.run(db, record_id=record.id, raw_text=text)

    clinical = state.get("clinical") or {}
    coding = state.get("coding") or {}
    validation = state.get("validation") or {}
    errors = state.get("errors") or {}
    if errors:
        raise HTTPException(status_code=422, detail={"record_id": record.id, "errors": errors})

    flow = [
        AgentFlowStepOut(agent="clinical", status="ok" if clinical else "skipped"),
        AgentFlowStepOut(agent="coding", status="ok" if coding else "skipped"),
        AgentFlowStepOut(agent="rule", status="ok" if validation else "skipped"),
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
    )
