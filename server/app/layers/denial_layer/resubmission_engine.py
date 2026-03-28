from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.layers.governance_layer.service import GovernanceLayer
from app.models.workflow import WorkflowRecord


@dataclass(frozen=True)
class ResubmissionResult:
    status: str
    validation: Dict[str, Any]
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "validation": self.validation, "confidence": float(self.confidence)}


class ResubmissionEngine:
    def __init__(self) -> None:
        self._governance = GovernanceLayer()

    def resubmit(
        self,
        db: Session,
        *,
        claim_record_id: Optional[str],
        updated_claim_data: Dict[str, Any],
        thresholds_cfg: Dict[str, Any],
        rules_cfg: Dict[str, Any],
        workflow_confidence: float,
    ) -> ResubmissionResult:
        resub_cfg = rules_cfg.get("resubmission") or {}
        rerun_governance = bool(resub_cfg.get("rerun_governance", True))
        validation: Dict[str, Any] = {}
        confidence = float(workflow_confidence or 0.0)
        status = "resubmitted"

        if rerun_governance and claim_record_id:
            rec = db.query(WorkflowRecord).filter(WorkflowRecord.id == claim_record_id).first()
            raw_text = str(getattr(rec, "raw_text", "") or "")
            clinical = updated_claim_data.get("clinical") if isinstance(updated_claim_data.get("clinical"), dict) else {}
            coding = updated_claim_data.get("coding") if isinstance(updated_claim_data.get("coding"), dict) else {}
            payer_validation = updated_claim_data.get("validation") if isinstance(updated_claim_data.get("validation"), dict) else {}
            svm = updated_claim_data.get("svm") if isinstance(updated_claim_data.get("svm"), dict) else {}
            gov = self._governance.evaluate_and_decide(
                db,
                record_id=claim_record_id,
                raw_text=raw_text,
                clinical=clinical,
                coding=coding,
                validation=payer_validation,
                svm=svm,
                workflow_confidence=float(workflow_confidence or 0.0),
            )
            validation["governance"] = gov
            try:
                confidence = float(gov.get("confidence") or confidence)
            except Exception:
                confidence = confidence

        thr = (thresholds_cfg.get("thresholds") or {}) if isinstance(thresholds_cfg.get("thresholds"), dict) else {}
        min_resub_conf = float(thr.get("min_resubmission_confidence", 0.0) or 0.0)
        if confidence < min_resub_conf:
            status = "needs_review"
        return ResubmissionResult(status=status, validation=validation, confidence=confidence)

