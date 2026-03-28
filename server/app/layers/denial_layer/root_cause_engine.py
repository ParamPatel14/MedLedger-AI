from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition


@dataclass(frozen=True)
class RootCauseResult:
    root_cause: str
    category: str
    confidence: float
    matched_rule_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_cause": self.root_cause,
            "category": self.category,
            "confidence": float(self.confidence),
            "matched_rule_id": self.matched_rule_id,
        }


class RootCauseEngine:
    def analyze(
        self,
        *,
        rules_cfg: Dict[str, Any],
        thresholds_cfg: Dict[str, Any],
        ctx: Dict[str, Any],
        denial_reason_types: List[str],
        workflow_confidence: float,
        raw_text: str,
    ) -> RootCauseResult:
        rc_rules = rules_cfg.get("root_cause_rules") or []
        if not isinstance(rc_rules, list):
            rc_rules = []

        external_issues = [{"type": t, "severity": "info"} for t in denial_reason_types if str(t or "").strip()]
        decision_inputs = DecisionInputs(
            raw_text=str(raw_text or ""),
            workflow_confidence=float(workflow_confidence or 0.0),
            svm=ctx.get("svm") if isinstance(ctx.get("svm"), dict) else {},
            policy_issues=[],
            edge_issues=[],
            external_issues=external_issues,
        )

        best: Optional[RootCauseResult] = None
        for r in rc_rules:
            if not isinstance(r, dict):
                continue
            cond = r.get("when") or {}
            if not isinstance(cond, dict):
                continue
            if not evaluate_condition(cond, ctx={"thresholds": thresholds_cfg, **ctx}, decision_inputs=decision_inputs):
                continue
            matched = RootCauseResult(
                root_cause=str(r.get("root_cause") or "").strip(),
                category=str(r.get("category") or "").strip(),
                confidence=float(r.get("confidence") or 0.0),
                matched_rule_id=str(r.get("id") or "").strip(),
            )
            if best is None or matched.confidence > best.confidence:
                best = matched

        if best is None:
            return RootCauseResult(root_cause="Unknown", category="unknown", confidence=0.0, matched_rule_id="")
        return best

