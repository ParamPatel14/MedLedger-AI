from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.governance import GovernanceAuditLog
from app.models.svm import SvmAuditLog
from app.models.workflow import AgentOutput, WorkflowRecord


def _iso(dt: Any) -> Optional[str]:
    try:
        return dt.isoformat()
    except Exception:
        return None


class DecisionTraceEngine:
    def build_trace(self, db: Session, *, record_id: str) -> Dict[str, Any]:
        rid = str(record_id or "").strip()
        record = db.query(WorkflowRecord).filter(WorkflowRecord.id == rid).first()
        created_at = _iso(getattr(record, "created_at", None))

        agent_rows = db.query(AgentOutput).filter(AgentOutput.record_id == rid).order_by(AgentOutput.created_at.asc()).all()
        svm_rows = db.query(SvmAuditLog).filter(SvmAuditLog.record_id == rid).order_by(SvmAuditLog.created_at.asc()).all()
        gov_row = db.query(GovernanceAuditLog).filter(GovernanceAuditLog.record_id == rid).order_by(GovernanceAuditLog.created_at.desc()).first()

        steps: List[Dict[str, Any]] = []
        steps.append({"stage": "start", "status": "ok" if record else "missing", "timestamp": created_at})

        for a in agent_rows:
            steps.append({"stage": str(a.agent_name or ""), "status": "ok", "timestamp": _iso(a.created_at)})

        for s in svm_rows:
            steps.append({"stage": str(s.stage or ""), "status": str(s.status or ""), "timestamp": _iso(s.created_at)})

        if gov_row is not None:
            steps.append({"stage": "governance", "status": "ok", "timestamp": _iso(gov_row.created_at)})

        return {"trace_id": rid, "steps": steps}

