from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition


@dataclass(frozen=True)
class GovernanceDecision:
    decision: str
    confidence: float
    reason: str
    matched_rule_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": float(self.confidence),
            "reason": self.reason,
            "matched_rule_id": self.matched_rule_id,
        }


def _clamp01(x: float) -> float:
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def _resolve_confidence(*, ctx: Dict[str, Any], thresholds_cfg: Dict[str, Any]) -> float:
    c_cfg = thresholds_cfg.get("confidence") or {}
    if not isinstance(c_cfg, dict):
        c_cfg = {}
    source = str(c_cfg.get("source") or "workflow").strip().lower()
    if source == "svm":
        svm = ctx.get("svm") or {}
        stages = c_cfg.get("svm_stages") or []
        if not isinstance(stages, list):
            stages = []
        values: List[float] = []
        if isinstance(svm, dict):
            for stage in stages:
                key = str(stage or "")
                v = svm.get(key)
                if isinstance(v, dict):
                    try:
                        values.append(float(v.get("confidence") or 0.0))
                    except Exception:
                        continue
        if not values:
            return _clamp01(float(ctx.get("workflow_confidence") or 0.0))
        agg = str(c_cfg.get("svm_aggregation") or "min").strip().lower()
        if agg == "avg":
            return _clamp01(sum(values) / len(values))
        return _clamp01(min(values))
    return _clamp01(float(ctx.get("workflow_confidence") or 0.0))


class DecisionGovernor:
    def decide(self, *, ctx: Dict[str, Any], thresholds_cfg: Dict[str, Any], decision_inputs: DecisionInputs) -> GovernanceDecision:
        decision_rules = thresholds_cfg.get("decision_rules") or []
        if not isinstance(decision_rules, list):
            decision_rules = []

        confidence = _resolve_confidence(ctx=ctx, thresholds_cfg=thresholds_cfg)
        di = DecisionInputs(
            raw_text=decision_inputs.raw_text,
            workflow_confidence=confidence,
            svm=decision_inputs.svm,
            policy_issues=decision_inputs.policy_issues,
            edge_issues=decision_inputs.edge_issues,
            external_issues=decision_inputs.external_issues,
        )
        for r in decision_rules:
            if not isinstance(r, dict):
                continue
            when = r.get("when") or {}
            if not isinstance(when, dict):
                continue
            if not evaluate_condition(when, ctx=ctx, decision_inputs=di):
                continue
            decision = str(r.get("decision") or "").strip().upper() or "APPROVE"
            reason = str(r.get("reason") or "").strip() or "Decision rule matched"
            rule_id = str(r.get("id") or "").strip()
            return GovernanceDecision(decision=decision, confidence=confidence, reason=reason, matched_rule_id=rule_id)

        return GovernanceDecision(decision="APPROVE", confidence=confidence, reason="Default approve", matched_rule_id="default")
