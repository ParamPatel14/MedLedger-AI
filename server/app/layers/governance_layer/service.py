from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.layers.governance_layer.config import get_governance_policies, get_governance_rules, get_governance_thresholds
from app.layers.governance_layer.decision_governor import DecisionGovernor
from app.layers.governance_layer.edge_cases import EdgeCaseEngine
from app.layers.governance_layer.evaluation import DecisionInputs
from app.layers.governance_layer.escalation import EscalationSystem
from app.layers.governance_layer.policy_engine import PolicyEngine
from app.layers.governance_layer.refusal import RefusalSystem
from app.models.governance import GovernanceAuditLog


logger = logging.getLogger(__name__)


def _as_issues(v: Any) -> List[dict]:
    if not isinstance(v, list):
        return []
    out: List[dict] = []
    for it in v:
        if isinstance(it, dict):
            out.append(it)
    return out


class GovernanceLayer:
    def __init__(self) -> None:
        self._policy_engine = PolicyEngine()
        self._edge_engine = EdgeCaseEngine()
        self._governor = DecisionGovernor()
        self._refusal = RefusalSystem()
        self._escalation = EscalationSystem()

    def evaluate_and_decide(
        self,
        db: Session,
        *,
        record_id: str,
        raw_text: str,
        clinical: Dict[str, Any],
        coding: Dict[str, Any],
        validation: Dict[str, Any],
        svm: Dict[str, Any],
        workflow_confidence: float,
    ) -> Dict[str, Any]:
        policies_cfg = get_governance_policies()
        thresholds_cfg = get_governance_thresholds()
        rules_cfg = get_governance_rules()

        ctx: Dict[str, Any] = {
            "record_id": record_id,
            "raw_text": raw_text,
            "clinical": clinical or {},
            "coding": coding or {},
            "validation": validation or {},
            "svm": svm or {},
            "workflow_confidence": float(workflow_confidence or 0.0),
            "thresholds": thresholds_cfg or {},
            "policies": policies_cfg or {},
            "rules": rules_cfg or {},
        }

        external_issues = _as_issues((validation or {}).get("issues") or [])
        policy_issues = self._policy_engine.evaluate(ctx=ctx, policies_cfg=policies_cfg).issues

        base_inputs = DecisionInputs(
            raw_text=str(raw_text or ""),
            workflow_confidence=float(workflow_confidence or 0.0),
            svm=svm if isinstance(svm, dict) else {},
            policy_issues=policy_issues,
            edge_issues=[],
            external_issues=external_issues,
        )
        edge_issues = self._edge_engine.evaluate(ctx=ctx, rules_cfg=rules_cfg, decision_inputs=base_inputs).issues

        decision_inputs = DecisionInputs(
            raw_text=base_inputs.raw_text,
            workflow_confidence=base_inputs.workflow_confidence,
            svm=base_inputs.svm,
            policy_issues=policy_issues,
            edge_issues=edge_issues,
            external_issues=external_issues,
        )

        refusal = self._refusal.evaluate(ctx=ctx, rules_cfg=rules_cfg, decision_inputs=decision_inputs)
        decision = self._governor.decide(ctx=ctx, thresholds_cfg=thresholds_cfg, decision_inputs=decision_inputs)

        escalation: Optional[dict] = None
        if decision.decision == "ESCALATE":
            esc = self._escalation.evaluate(ctx=ctx, rules_cfg=rules_cfg, decision_inputs=decision_inputs)
            escalation = esc.payload if esc.escalated else {"status": "escalated", "reason": decision.reason, "queue": str((rules_cfg.get("escalation") or {}).get("queue") or "human_review")}

        refusal_payload = refusal.payload if refusal.refused else None
        combined_issues = [*policy_issues, *edge_issues, *external_issues]

        out: Dict[str, Any] = {
            "decision": decision.decision,
            "confidence": float(decision.confidence),
            "reason": decision.reason,
            "issues": combined_issues,
            "refusal": refusal_payload,
            "escalation": escalation,
            "policy_issues": policy_issues,
            "edge_issues": edge_issues,
            "external_issues": external_issues,
            "matched_rule_id": decision.matched_rule_id,
            "refusal_rule_id": refusal.matched_rule_id,
        }

        row = GovernanceAuditLog(
            record_id=str(record_id),
            decision=str(decision.decision),
            confidence=float(decision.confidence),
            reason=str(decision.reason),
            issues=combined_issues,
            payload={
                "governance": out,
                "clinical": clinical or {},
                "coding": coding or {},
                "validation": validation or {},
                "svm": svm or {},
                "config_versions": {
                    "policies": str((policies_cfg or {}).get("version") or ""),
                    "thresholds": str((thresholds_cfg or {}).get("version") or ""),
                    "rules": str((rules_cfg or {}).get("version") or ""),
                },
            },
        )
        db.add(row)
        db.commit()

        out["audit_id"] = row.audit_id
        logger.info("governance_decision record_id=%s audit_id=%s decision=%s confidence=%.3f", record_id, row.audit_id, decision.decision, decision.confidence)
        return out
