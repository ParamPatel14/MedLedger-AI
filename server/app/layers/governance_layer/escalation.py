from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition


@dataclass(frozen=True)
class EscalationResult:
    escalated: bool
    payload: Optional[Dict[str, Any]]
    matched_rule_id: str


class EscalationSystem:
    def evaluate(self, *, ctx: Dict[str, Any], rules_cfg: Dict[str, Any], decision_inputs: DecisionInputs) -> EscalationResult:
        esc = rules_cfg.get("escalation") or {}
        if not isinstance(esc, dict) or not bool(esc.get("enabled", True)):
            return EscalationResult(escalated=False, payload=None, matched_rule_id="")
        queue = str(esc.get("queue") or "human_review").strip()
        rules = esc.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        for r in rules:
            if not isinstance(r, dict):
                continue
            when = r.get("when") or {}
            if not isinstance(when, dict):
                continue
            if not evaluate_condition(when, ctx=ctx, decision_inputs=decision_inputs):
                continue
            reason = str(r.get("reason") or "Escalated").strip()
            rid = str(r.get("id") or "").strip()
            return EscalationResult(escalated=True, payload={"status": "escalated", "reason": reason, "queue": queue}, matched_rule_id=rid)

        return EscalationResult(escalated=False, payload=None, matched_rule_id="")

