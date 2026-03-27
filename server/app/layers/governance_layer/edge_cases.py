from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition


@dataclass(frozen=True)
class EdgeCaseResult:
    issues: List[dict]


class EdgeCaseEngine:
    def evaluate(self, *, ctx: Dict[str, Any], rules_cfg: Dict[str, Any], decision_inputs: DecisionInputs) -> EdgeCaseResult:
        edge = rules_cfg.get("edge_cases") or {}
        if not isinstance(edge, dict) or not bool(edge.get("enabled", True)):
            return EdgeCaseResult(issues=[])
        detectors = edge.get("detectors") or []
        if not isinstance(detectors, list):
            detectors = []

        issues: List[dict] = []
        for d in detectors:
            if not isinstance(d, dict):
                continue
            when = d.get("when") or {}
            if not isinstance(when, dict):
                continue
            if not evaluate_condition(when, ctx=ctx, decision_inputs=decision_inputs):
                continue
            issues.append(
                {
                    "type": str(d.get("type") or "edge_case"),
                    "severity": str(d.get("severity") or "warning").lower(),
                    "message": str(d.get("message") or "Edge case detected"),
                    "detector_id": str(d.get("id") or ""),
                }
            )
        return EdgeCaseResult(issues=issues)

