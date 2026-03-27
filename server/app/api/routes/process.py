from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.workflow_layer.agents import ClinicalUnderstandingAgent, CodingAgent, PayerRuleAgent
from app.layers.workflow_layer.orchestrator import LangGraphOrchestrator
from app.models.workflow import WorkflowRecord, WorkflowState
from app.schemas.process import ProcessIn, ProcessOut, ValidationOut


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
