from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition


@dataclass(frozen=True)
class RefusalResult:
    refused: bool
    payload: Optional[Dict[str, Any]]
    matched_rule_id: str


class RefusalSystem:
    def evaluate(self, *, ctx: Dict[str, Any], rules_cfg: Dict[str, Any], decision_inputs: DecisionInputs) -> RefusalResult:
        refusal = rules_cfg.get("refusal") or {}
        if not isinstance(refusal, dict) or not bool(refusal.get("enabled", True)):
            return RefusalResult(refused=False, payload=None, matched_rule_id="")
        rules = refusal.get("rules") or []
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
            msg = str(r.get("message") or "Insufficient information. Cannot proceed.").strip()
            rid = str(r.get("id") or "").strip()
            return RefusalResult(refused=True, payload={"status": "refused", "message": msg}, matched_rule_id=rid)

        return RefusalResult(refused=False, payload=None, matched_rule_id="")

